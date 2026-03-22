import os
import sys
import torch
import time
import subprocess
import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.parser.lib_parser import NLDMParser
from src.core.compressor_tree import DOMAC_CompressorTree
from src.core.objectives import DOMACLossFunction
from src.optimizer.train import DOMACTrainer
from src.optimizer.legalizer import DOMACLegalizer
from src.export.verilog_gen import VerilogGenerator

def create_physical_tensor_mock():
    idx_slew = torch.tensor([0.005, 0.01, 0.02, 0.04, 0.08, 0.16, 0.32], dtype=torch.float32)
    idx_load = torch.tensor([0.001, 0.002, 0.004, 0.008, 0.016, 0.032, 0.064], dtype=torch.float32)
    
    fa_delay_lut = torch.linspace(0.05, 0.20, 49).view(7, 7) 
    ha_delay_lut = torch.linspace(0.03, 0.15, 49).view(7, 7) 
    slew_lut = torch.linspace(0.01, 0.10, 49).view(7, 7)
    
    fa_base = {'cell_area': 2.5, 'S': {'A': {'index_1_slew': idx_slew, 'index_2_load': idx_load, 'delay_lut': fa_delay_lut, 'slew_lut': slew_lut}}, 'CO': {'A': {'index_1_slew': idx_slew, 'index_2_load': idx_load, 'delay_lut': fa_delay_lut, 'slew_lut': slew_lut}}}
    ha_base = {'cell_area': 1.8, 'S': {'A': {'index_1_slew': idx_slew, 'index_2_load': idx_load, 'delay_lut': ha_delay_lut, 'slew_lut': slew_lut}}, 'CO': {'A': {'index_1_slew': idx_slew, 'index_2_load': idx_load, 'delay_lut': ha_delay_lut, 'slew_lut': slew_lut}}}
    
    # 模拟返回多个物理实现的库：3种FA，2种HA
    return [fa_base, fa_base, fa_base], [ha_base, ha_base]

def generate_multiplier_canvas(bit_width):
    print(f"\n[Canvas Generator] 自动推演 {bit_width}x{bit_width} 乘法器画布 (严格 Dadda Tree 算法)...")
    pp_cols = []
    max_cols = bit_width * 2 - 1
    dots_in_col = [0] * max_cols
    
    # 1. 生成初始部分积 (Partial Products) 矩阵
    for i in range(bit_width):
        for j in range(bit_width):
            col = i + j
            pp_cols.append(col)
            dots_in_col[col] += 1
            
    print(f" -> 共 {len(pp_cols)} 个 PP 节点。初始点数分布:\n    {dots_in_col}")
    
    # 2. 计算 Dadda 树的目标高度序列 (2, 3, 4, 6, 9, 13, 19, 28...)
    dadda_seq = [2]
    while dadda_seq[-1] < bit_width:
        dadda_seq.append(int(dadda_seq[-1] * 1.5))
    dadda_seq.reverse() 
    
    # 过滤掉大于等于当前最大高度的目标，只保留真正需要压缩的阶段
    targets = [t for t in dadda_seq if t < max(dots_in_col)]
    print(f" -> Dadda 目标高度收敛序列: {targets}")
    
    comp_cols_raw = []
    c_types_raw = []
    current_dots = list(dots_in_col)
    
    # 3. 按目标高度逐级扫荡压缩
    for stage_idx, target in enumerate(targets):
        current_len = len(current_dots)
        next_dots = [0] * current_len
        carry_from_prev = 0
        
        for col in range(current_len):
            V = current_dots[col]
            # 当前列在下一级期望达到的高度边界 (扣除上一列传来的进位后，本列允许留下的节点数)
            allowed_output = target - carry_from_prev
            
            if V > allowed_output:
                # 需要通过引入压缩器来削减的点数
                reduction_needed = V - allowed_output
                
                # 贪心分配：1 个 FA 削减 2 个高度，1 个 HA 削减 1 个高度
                f = reduction_needed // 2
                h = reduction_needed % 2
                
                for _ in range(f):
                    comp_cols_raw.append(col)
                    c_types_raw.append('FA')
                for _ in range(h):
                    comp_cols_raw.append(col)
                    c_types_raw.append('HA')
                    
                # 本列保留的点数 = 原有数量 - 削减的高度
                dots_stay = V - reduction_needed
                next_dots[col] = dots_stay + carry_from_prev
                carry_from_prev = f + h
            else:
                # 不需要压缩，全部透传，加上进位
                next_dots[col] = V + carry_from_prev
                carry_from_prev = 0
                
        # 最后一个进位如果存在，顺延到最高位的下一列
        if carry_from_prev > 0:
            next_dots.append(carry_from_prev)
            
        current_dots = next_dots
        
    final_max = max(current_dots)
    print(f" -> 压缩完毕！最终最大高度: {final_max}。")
    print(f" -> 申请 {len(comp_cols_raw)} 个压缩器画布 ({c_types_raw.count('FA')} FA, {c_types_raw.count('HA')} HA)。")
    
    if final_max > 2:
        print("\n[致命警告] Dadda 树未能将高度压缩至 2！请检查位宽逻辑。")
        
    # 4. [高危漏洞修复] 安全地将坑位和物理类型进行联合排序 (Zip Sort)
    # 确保无论 Stage 怎么穿插，列索引和分配给该列的门类型永远死死绑定
    combined = sorted(zip(comp_cols_raw, c_types_raw), key=lambda x: x[0])
    comp_cols = [x[0] for x in combined]
    c_types = [x[1] for x in combined]

    return pp_cols, comp_cols, c_types
    
def generate_dadda_init_matrix(bit_width, pp_cols, c_cols, c_types):
    """
    [Dr. Gemini 热启动引擎] 提取纯血 Dadda 树的硬连线逻辑，
    并转化为 DOMAC 连续概率矩阵的初始 Logits。
    """
    print(f"\n[Warm Start] 正在提取 Dadda 拓扑作为先验知识，初始化拓扑概率矩阵...")
    num_pp = len(pp_cols)
    num_c = len(c_cols)
    total_nodes = num_pp + 2 * num_c
    total_target_pins = num_c * 3
    
    # 初始化全 0 矩阵 (Logits)。之后会被 Softmax 转化为概率。
    m_logits = torch.zeros((total_nodes, total_target_pins + 1))
    
    max_cols = bit_width * 2 - 1
    signals = [[] for _ in range(max_cols)]
    
    # 1. 初始化 PP 信号源节点 ID (0 到 num_pp-1)
    k = 0
    for i in range(bit_width):
        for j in range(bit_width):
            signals[i+j].append(k)
            k += 1
            
    dadda_seq = [2]
    while dadda_seq[-1] < bit_width:
        dadda_seq.append(int(dadda_seq[-1] * 1.5))
    dadda_seq.reverse()
    targets = [t for t in dadda_seq if t < max([len(col) for col in signals])]
    
    # 2. 建立反向映射表：DOMAC 的压缩器是按列(col)排好序的，
    # 我们必须把 Dadda 生成过程中的压缩器准确映射到 DOMAC 的绝对索引 j 上。
    comp_index_map = {col: {'FA': [], 'HA': []} for col in range(max_cols)}
    for j, (col, c_type) in enumerate(zip(c_cols, c_types)):
        comp_index_map[col][c_type].append(j)
        
    comp_usage = {col: {'FA': 0, 'HA': 0} for col in range(max_cols)}
    
    # 3. 严格遵循 Dadda 算法，但这次我们记录连线索引！
    for stage_idx, target in enumerate(targets):
        next_signals = [[] for _ in range(max_cols + 1)]
        carry_from_prev = []
        
        for col in range(len(signals)):
            current_sigs = signals[col] + carry_from_prev
            V = len(current_sigs)
            
            if V > target:
                reduction_needed = V - target
                f = reduction_needed // 2
                h = reduction_needed % 2
                
                carries_generated = []
                
                for _ in range(f):
                    s1, s2, s3 = current_sigs.pop(), current_sigs.pop(), current_sigs.pop()
                    # 获取该 FA 在 DOMAC 体系下的绝对索引
                    j = comp_index_map[col]['FA'][comp_usage[col]['FA']]
                    comp_usage[col]['FA'] += 1
                    
                    # [注入先验偏置] 给 Dadda 的目标连线施加 10.0 的极高初始权重
                    m_logits[s1, j * 3 + 0] = 10.0
                    m_logits[s2, j * 3 + 1] = 10.0
                    m_logits[s3, j * 3 + 2] = 10.0
                    
                    # 生成下一级的节点 ID
                    next_signals[col].append(num_pp + j)       # S 输出
                    carries_generated.append(num_pp + num_c + j) # CO 输出
                    
                for _ in range(h):
                    s1, s2 = current_sigs.pop(), current_sigs.pop()
                    j = comp_index_map[col]['HA'][comp_usage[col]['HA']]
                    comp_usage[col]['HA'] += 1
                    
                    m_logits[s1, j * 3 + 0] = 10.0
                    m_logits[s2, j * 3 + 1] = 10.0
                    
                    next_signals[col].append(num_pp + j)
                    carries_generated.append(num_pp + num_c + j)
                    
                next_signals[col].extend(current_sigs)
                carry_from_prev = carries_generated
            else:
                next_signals[col].extend(current_sigs)
                carry_from_prev = []
                
        if carry_from_prev:
            if len(signals) >= len(next_signals):
                next_signals.append([])
            next_signals[len(signals)].extend(carry_from_prev)
            
        signals = next_signals

    # 4. 处理最终流向 CPA (Sink) 的剩余信号
    for i in range(total_nodes):
        # 如果某个节点没有任何一根引脚指向压缩器（最高 Logit 小于 5.0），说明它直接通向 Sink
        if torch.max(m_logits[i, :-1]) < 5.0:
            m_logits[i, -1] = 10.0
            
    print(f" -> Dadda 知识蒸馏完毕！已将 {int(torch.sum(m_logits == 10.0).item())} 根硬连线转化为高斯先验。")
    return m_logits

def main():
    print("="*60)
    print(" [DOMAC 净室复现] TSMC 28nm 节点可微 STA 优化框架")
    print("="*60)
    
    # ================= [新增：全局优化策略配置] =================
    # 'dadda' : 从 Dadda 树先验知识热启动 (100% 对齐对照组)
    # 'blank' : 从等概率全零矩阵冷启动 (纯粹从零开始探索)
    INIT_MODE = 'blank'

    # TARGET_CELLS = [
    #     'FA1D0BWP12T40P140', 'FA1D1BWP12T40P140', 'FA1D2BWP12T40P140', 'FA1D4BWP12T40P140',
    #     'HA1D0BWP12T40P140', 'HA1D1BWP12T40P140', 'HA1D2BWP12T40P140', 'HA1D4BWP12T40P140'
    # ]
    
    TARGET_CELLS = [
        'FA1D1BWP12T40P140',
        'HA1D1BWP12T40P140',
    ]

    # 提前准备好物理名字，用于最终生成 Verilog
    fa_names = [c for c in TARGET_CELLS if c.startswith('FA')]
    ha_names = [c for c in TARGET_CELLS if c.startswith('HA')]
    
    try:
        lib_path = "/home/changxian/library/t28_official/tcbn28hpcplusbwp12t40p140tt0p9v25c.lib"
        if os.path.exists(lib_path):
            print("[System] 发现 PDK 物理库，启动解析...")
            parser = NLDMParser(lib_path, TARGET_CELLS)
            nldm_db = parser.parse()
        #    # ================= [新增：物理数据透明化打印 (全景引脚解析版)] =================
        #     print("\n" + "="*60)
        #     print(" 📊 [物理数据核对] 提取的 Area 与 Delay (Worst-case) 全景概览")
        #     print("="*60)
        #     for cell in TARGET_CELLS:
        #         if cell in nldm_db:
        #             area = nldm_db[cell].get('cell_area', 'N/A')
        #             print(f"[{cell}]")
        #             print(f"  -> 面积 (Area): {area} μm²")
                    
        #             # 遍历所有的输出引脚 (S, CO)
        #             for out_pin in ['S', 'CO']:
        #                 if out_pin in nldm_db[cell]:
        #                     # 遍历所有的输入引脚 (A, B, CI)
        #                     for in_pin in ['A', 'B', 'CI']:
        #                         if in_pin in nldm_db[cell][out_pin]:
        #                             arc_data = nldm_db[cell][out_pin][in_pin]
        #                             delay_lut = arc_data.get('delay_lut')
                                    
        #                             # 确保 LUT 存在且有数据
        #                             if delay_lut is not None and hasattr(delay_lut, 'min'):
        #                                 delay_min = delay_lut.min().item()
        #                                 delay_max = delay_lut.max().item()
        #                                 print(f"  -> {in_pin} -> {out_pin:<2} 延迟极限范围: {delay_min:.5f} ns ~ {delay_max:.5f} ns")
        #             print("-" * 40)
        #     print("="*60 + "\n")
        #     # ===================================================================
        # ================= [增强：物理数据透明化打印 (含电容验证)] =================
            print("\n" + "="*60)
            print(" 📊 [物理数据核对] 提取的 Area, Cap 与 Delay 全景概览")
            print("="*60)
            for cell in TARGET_CELLS:
                if cell in nldm_db:
                    area = nldm_db[cell].get('cell_area', 'N/A')
                    print(f"[{cell}]")
                    print(f"  -> 面积 (Area): {area} μm²")
                    
                    # --- [关键：输出引脚电容验证] ---
                    if 'pin_cap' in nldm_db[cell]:
                        print(f"  -> 引脚输入电容 (Input Capacitance):")
                        for pin, cap in nldm_db[cell]['pin_cap'].items():
                            # 28nm 下通常在 0.001 pF 左右
                            print(f"     * {pin:<3} : {cap:.6f} pF") 
                    else:
                        print(f"  -> [Warning] 未发现引脚电容数据！")
                    # -------------------------------
                    
                    # 遍历所有的输出引脚 (S, CO) 打印延迟范围
                    for out_pin in ['S', 'CO']:
                        if out_pin in nldm_db[cell]:
                            for in_pin in ['A', 'B', 'CI']:
                                if in_pin in nldm_db[cell][out_pin]:
                                    arc_data = nldm_db[cell][out_pin][in_pin]
                                    delay_lut = arc_data.get('delay_lut')
                                    if delay_lut is not None:
                                        print(f"  -> {in_pin} -> {out_pin:<2} 延迟极限: {delay_lut.min().item():.5f} ~ {delay_lut.max().item():.5f} ns")
                    print("-" * 40)
            print("="*60 + "\n")
            # ===================================================================
            fa_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('FA') and c in nldm_db]
            ha_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('HA') and c in nldm_db]
        else:
            raise FileNotFoundError(f"找不到指定的工艺库文件: {lib_path}")
    except Exception as e:
        # print(f"\n[System] PDK 异常，切换【物理对齐 Mock 模式】...")
        # fa_tensors, ha_tensors = create_physical_tensor_mock()
        # # Mock 模式下必须伪造同样数量的名字给 Verilog 生成器，否则会越界崩溃
        # fa_names = [f"Mock_FA_Impl_{i}" for i in range(len(fa_tensors))]
        # ha_names = [f"Mock_HA_Impl_{i}" for i in range(len(ha_tensors))]
        print(f"\n[Fatal Error] 系统初始化失败，拒绝以非严谨模式运行。原因: {e}")
        sys.exit(1)
        
    BIT_WIDTH = 8
    TARGET_SINK_COUNT = (BIT_WIDTH * 2 - 1) * 2
    PP_COLS, COMP_COLS, C_TYPES = generate_multiplier_canvas(BIT_WIDTH)
    NUM_PP = len(PP_COLS)
    NUM_COMPRESSORS = len(COMP_COLS)

    # pp_at = torch.linspace(0.0, 0.1, NUM_PP) 
    # pp_slew = torch.full((NUM_PP,), 0.05)
    # REQ_TIME = 0.1 
    # print("REQ_TIME：" + str(REQ_TIME))

    # print(f"\n[Engine] 构建异构可微压缩树...")
    # model = DOMAC_CompressorTree(PP_COLS, COMP_COLS, fa_tensors, ha_tensors, C_TYPES, REQ_TIME)

    # loss_engine = DOMACLossFunction()
    # trainer = DOMACTrainer(model, loss_engine, lr=0.05)
    
    # print("\n[Engine] 物理映射与梯度反向传播开始...")
    
    # start_time = time.time()
    # final_M, final_P = trainer.train(pp_at, pp_slew, max_epochs=300)
    # ================= [GPU 核动力点火] =================
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\n[System] 核心计算引擎将挂载至: {device}")
    if torch.cuda.is_available():
        print(f" -> 检测到显卡: {torch.cuda.get_device_name(0)}")
        # 为了极速性能，开启 CuDNN 基准测试加速
        torch.backends.cudnn.benchmark = True 

    # 1. 初始信号输入必须在显存上创建
    # pp_at = torch.linspace(0.0, 0.1, NUM_PP, device=device) 
    # pp_at = torch.zeros(NUM_PP, device=device) 
    pp_at = torch.full((NUM_PP,), 0.1, device=device)
    pp_slew = torch.full((NUM_PP,), 0.02, device=device)
    REQ_TIME = 0 
    print("REQ_TIME：" + str(REQ_TIME))

    print(f"\n[Engine] 构建异构可微压缩树...")
    # ================= [核心重构：初始态路由引擎] =================
    max_impls = max(len(fa_tensors), len(ha_tensors))
    
    # [修复1] 显式定义基准物理门索引 (1 代表使用 FA1D1)
    BASELINE_GATE_INDEX = 1 
    # 安全处理：如果库里只有一个尺寸，强制使用索引 0
    safe_gate_idx = BASELINE_GATE_INDEX if max_impls > BASELINE_GATE_INDEX else 0

    if INIT_MODE == 'dadda':
        print(f" -> [Init] 采用 Dadda 树先验知识热启动 (物理门初始尺寸: D{safe_gate_idx})")
        init_m = generate_dadda_init_matrix(BIT_WIDTH, PP_COLS, COMP_COLS, C_TYPES)
        
        init_p = torch.zeros((NUM_COMPRESSORS, max_impls))
        init_p[:, safe_gate_idx] = 10.0  
        
        # 从初始矩阵萃取 100% 对齐的 Baseline
        discrete_init_M = torch.zeros_like(init_m)
        discrete_init_M[:, :-1] = (init_m[:, :-1] == 10.0).float() 
        discrete_init_P = [safe_gate_idx] * NUM_COMPRESSORS

    elif INIT_MODE == 'blank':
        # print(f" -> [Init] 采用等概率全零矩阵冷启动 (无先验知识)")
        # total_nodes = NUM_PP + 2 * NUM_COMPRESSORS
        # total_target_pins = NUM_COMPRESSORS * 3
        # init_m = torch.zeros((total_nodes, total_target_pins + 1))
        # init_p = torch.zeros((NUM_COMPRESSORS, max_impls))
        
        print(f" -> [Init] 采用纯随机高斯噪声冷启动 (打破拓扑对称性)")
        total_nodes = NUM_PP + 2 * NUM_COMPRESSORS
        total_target_pins = NUM_COMPRESSORS * 3
        # 【致命修复】绝不能用 zeros！必须用正态分布噪声打破梯度对称性
        FIXED_SEED = 42 
        torch.manual_seed(FIXED_SEED)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(FIXED_SEED)
        init_m = torch.randn((total_nodes, total_target_pins + 1)) * 0.5
        init_p = torch.zeros((NUM_COMPRESSORS, max_impls))
        
        # 白板模式没有初始物理结构，无法生成 Baseline 网表
        discrete_init_M = None
        discrete_init_P = None
        
    else:
        raise ValueError(f"[Fatal] 未知的初始化模式: {INIT_MODE}")
        
    # ============================================================
    # 2. [修复2] 将 init_m 和 init_p 喂给模型，并上 GPU
    model = DOMAC_CompressorTree(
        PP_COLS, COMP_COLS, fa_tensors, ha_tensors, C_TYPES, REQ_TIME, 
        device=device,
        init_m_logits=init_m, 
        init_p_logits=init_p
    ).to(device)

    # 将动态约束传入 Loss 引擎
    loss_engine = DOMACLossFunction(target_sink_count=TARGET_SINK_COUNT)
    trainer = DOMACTrainer(model, loss_engine, lr=0.05)
    
    print("\n[Engine] 物理映射与梯度反向传播开始...")
    
    start_time = time.time()
    final_M, final_P = trainer.train(pp_at, pp_slew, max_epochs=300)
    
    print("\n[System] 优化执行完毕！网表拓扑已坍缩至离散界限附近。")
    
    # 1. 启动合法化器 (离散坍缩)
    legalizer = DOMACLegalizer()
    discrete_M, discrete_P = legalizer.legalize(final_M, final_P, C_TYPES, model.dag_mask)
    
    # # ================= [新增：列高溢出探针 (Column Height Probe)] =================
    # from collections import Counter
    # print("\n" + "="*60)
    # print(" 🕵️ [DOMAC 探针] 最终输出到 CPA 的列高 (Column Height) 核查")
    # print("="*60)

    # # 1. 获取所有节点的列权重属性
    # node_cols = model.node_cols

    # # 2. 找出流向 Sink (下游 CPA) 的节点
    # # 在 discrete_M 中，如果某一行全为 0，说明该节点没有连向任何内部压缩器引脚，必然流向了 Sink
    # row_sums = torch.sum(discrete_M, dim=1)
    # nodes_to_sink = torch.where(row_sums == 0)[0].tolist()

    # # 3. 提取这些残余节点的列权重，并统计每一列的数量
    # sink_weights = [node_cols[i] for i in nodes_to_sink]
    # col_counts = Counter(sink_weights)
    
    # overflow_detected = False
    # for col, count in sorted(col_counts.items()):
    #     if count > 2:
    #         # 超过 2 个信号，必然触发 DC 综合工具的多重 CPA 级联雪崩！
    #         print(f" 🚨 [致命溢出] 第 {col:>2} 列: 残留了 {count} 个未压缩信号！")
    #         overflow_detected = True
    #     else:
    #         print(f" ✅ [正常]     第 {col:>2} 列: 残留 {count} 个信号")

    # if overflow_detected:
    #     print("\n ⚠️ 结论：列压缩未彻底完成！")
    #     print("    下游 DC 综合工具将被迫把多余的信号强行跨接 (如 intadd_1 -> intadd_0)，导致 0.4ns+ 的时序雪崩！")
    # else:
    #     print("\n 完美：所有列已严格压缩至 <= 2，完全符合进入单一高速 CPA 的条件。")
    # print("="*60 + "\n")
    # # ==============================================================================

    # ================= [新增：离散化后硬连线物理评估 (Post-Legalization Eval)] =================
    print("\n[Evaluator] 正在对坍缩后的 0/1 离散硬连线进行最终物理时序核算...")
    with torch.no_grad():
        # 1. 构造离散化物理尺寸的 One-Hot 张量
        discrete_P_tensor = torch.zeros_like(final_P)
        for i, idx in enumerate(discrete_P):
            discrete_P_tensor[i, idx] = 1.0
            
        # 2. 构造包含 Sink (CPA) 列的完整离散连线矩阵
        discrete_M_full = torch.zeros_like(model.m_logits)
        discrete_M_full[:, :-1] = discrete_M
        # 匈牙利算法没有分给压缩树的引脚，必定全部流向了最后的 CPA (Sink)
        row_sums = torch.sum(discrete_M, dim=1)
        discrete_M_full[row_sums == 0, -1] = 1.0

        # 3. 备份原本训练结束时的模糊 logits
        orig_m_logits = model.m_logits.clone()
        orig_p_logits = model.p_logits.clone()

        # 4. [核心技巧] 注入极端 Logits 强制网络走硬连线
        # 将 1 映射为 10000.0，0 映射为 -10000.0，经过 Softmax 后就是绝对的 1.0 和 0.0
        new_m_logits = torch.full_like(orig_m_logits, -1e4)
        new_m_logits[discrete_M_full == 1.0] = 1e4
        model.m_logits.copy_(new_m_logits)

        new_p_logits = torch.full_like(orig_p_logits, -1e4)
        new_p_logits[discrete_P_tensor == 1.0] = 1e4
        model.p_logits.copy_(new_p_logits)

        # 5. 执行一次纯净的前向传播与 Loss 计算
        eval_wns, eval_tns, eval_area, eval_M, eval_P = model(pp_at, pp_slew, tau=1.0)
        eval_loss, eval_dict = loss_engine(
            eval_wns, eval_tns, eval_area, eval_M, eval_P, trainer.hyperparams, 
            model.active_pin_mask, model.c_types
        )

        print(f" -> [坍缩后真实指标] WNS: {eval_dict['wns'].item():.4f} ns | "
              f"Area: {eval_dict['area'].item():.4f} μm² | "
              f"L_BM: {eval_dict['l_bm'].item():.4f} | "
              f"Total Loss: {eval_loss.item():.4f}")
        
        # ================= [新增：WNS 计算过程溯源探针] =================
        print("\n" + "="*60)
        print(" 🧮 [DOMAC 探针] 离散化网表 WNS 内部计算逻辑核对")
        print("="*60)
        
        # 1. 提取离散化评估后的全图所有节点的 AT (到达时间)
        all_ats = model._probe_node_ats.detach().cpu().numpy()
        req_time = REQ_TIME # 你设定的目标时间 (当前是 0.0)
        
        # 2. 计算每个节点的 Slack (容限)
        # Slack = 要求到达时间 - 实际到达时间
        slacks = req_time - all_ats
        
        # 3. 找出全图 Slack 最差的节点 (即 AT 最大的节点)
        worst_idx = np.argmin(slacks)
        worst_at = all_ats[worst_idx]
        worst_slack = slacks[worst_idx]
        
        # 4. 翻译这个“罪魁祸首”节点的物理身份
        num_pp = len(PP_COLS)
        num_c = len(COMP_COLS)
        if worst_idx < num_pp:
            node_name = f"原始输入信号 PP_in_{worst_idx}"
        elif worst_idx < num_pp + num_c:
            c_idx = worst_idx - num_pp
            node_name = f"压缩器 U_comp_{c_idx} 的 S (Sum) 输出引脚"
        else:
            c_idx = worst_idx - num_pp - num_c
            node_name = f"压缩器 U_comp_{c_idx} 的 CO (Carry-Out) 输出引脚"
            
        print(f" -> 1. 设定的目标到达时间 (REQ_TIME) : {req_time:.4f} ns")
        print(f" -> 2. 全局最慢的关键节点判定为     : {node_name}")
        print(f" -> 3. 查表计算的该节点实际 AT      : {worst_at:.4f} ns")
        print(f" -> 4. 原始负超额 (Negative Slack)  : {min(0.0, worst_slack):.4f} ns")
        
        # 因为 DOMAC 使用了 smooth_max_lse (Log-Sum-Exp) 来保证导数连续，
        # 所以最终平滑出的 WNS 会比绝对最大值稍微大一点点 (gamma=0.01 产生的极小膨胀)
        print(f" -> 5. AI 最终汇报的平滑 eval_wns   : {eval_wns.item():.4f} ns")
        print(f"\n [对比 DC] 你的 DC 综合报告 Max Delay 为: 0.60 ns")
        
        if abs(worst_at - 0.60) < 0.08:
            print(" ✅ 结论: AI 内部的物理计算与 DC 高度吻合！AI 并没有算错！")
            print("    失败原因：优化器 (Optimizer) 梯度下降时，被困在了 S 引脚串联的死胡同里。")
        else:
            print(" ❌ 结论: AI 的延迟计算与 DC 存在较大脱节，需检查 LUT 插值。")
        print("="*60 + "\n")
        # ====================================================================

        # 6. 恢复原本的 logits (保持代码状态安全)
        model.m_logits.copy_(orig_m_logits)
        model.p_logits.copy_(orig_p_logits)
    # ================= [新增：离散化后硬连线物理评估 (Post-Legalization Eval)] =================

# ================= [新增：波前到达时间 (Wavefront AT) 探针] =================
    print("\n" + "="*65)
    print(" 🌊 [DOMAC 探针] CPA 输入波前到达时间 (Wavefront AT) 剖析")
    print("="*65)
    
    # 提取离散化评估后，全图节点的真实物理到达时间
    node_ats = model._probe_node_ats.detach().cpu().numpy()
    node_cols = model.node_cols
    
    # 找出流向 Sink 的节点 (行和为 0 的离散 M)
    row_sums = torch.sum(discrete_M, dim=1)
    nodes_to_sink = torch.where(row_sums == 0)[0].tolist()
    
    # 按照列(Column)分类收集这些节点的 AT
    col_to_ats = {}
    for idx in nodes_to_sink:
        col = node_cols[idx]
        at = node_ats[idx]
        if col not in col_to_ats:
            col_to_ats[col] = []
        col_to_ats[col].append(at)
        
    print(f"{'比特位 (Column)':<15} | {'交付给 CPA 的最晚时间 (Max AT)':<25} | {'波前状态诊断'}")
    print("-" * 65)
    
    for col in sorted(col_to_ats.keys()):
        max_at = max(col_to_ats[col])
        # 诊断逻辑：低位（如 0~6 列）如果不低于 0.18ns，说明严重挤占了 CPA 的进位跑道
        if col < 7 and max_at > 0.18:
            status = "🚨 危险 (波前倒置/低位滞后)"
        elif col >= 7 and max_at > 0.28:
            status = "⚠️ 偏高 (全局延迟瓶颈)"
        else:
            status = "✅ 优秀 (符合 CPA 期望)"
            
        print(f" Col {col:<10} | {max_at:.4f} ns{'':<16} | {status}")
        
    print("="*65 + "\n")
    print(" 💡 【波前理论解读】：")
    print(" 理想的压缩树输出，其 AT 应该呈现『阶梯上升』的斜坡形态 (LSB极早，MSB晚)。")
    print(" 如果上表中，低位(Col 0~6) 的延迟达到了 0.20ns+，CPA 的进位计算将被迫")
    print(" 拖延到此时才能起跑，导致最终 DC 综合的总体延迟发生雪崩！")
    # ==============================================================================

    # 2. 启动 Verilog 打印机
    os.makedirs("output/netlists", exist_ok=True)
    
    v_gen = VerilogGenerator(
        pp_cols=PP_COLS, 
        c_cols=COMP_COLS,
        c_types=C_TYPES,
        fa_cell_names=fa_names,
        ha_cell_names=ha_names
    )
    
    netlist_path = "output/netlists/domac_result.v"
    tb_path = "output/netlists/tb_domac.v"
    
    v_gen.generate(discrete_M, discrete_P, output_file=netlist_path)
    v_gen.generate_testbench(tb_file=tb_path, netlist_file=netlist_path)
    
    # [修复3] 删除了重复的 generate_multiplier_top
    top_path = "output/netlists/domac.v"
    v_gen.generate_multiplier_top(
        bit_width=BIT_WIDTH, 
        top_file=top_path, 
        ct_module_name="domac_compressor_tree", 
        top_module_name="domac"
    )

    # ================= [替换：基于配置动态生成 Baseline] =================
    if INIT_MODE == 'dadda' and discrete_init_M is not None:
        print(f"\n[BaselineGen] 正在直接从 AI 热启动矩阵中剥离 {INIT_MODE} 基准网表 (保证 100% 对齐)...")
        
        # 1. 临时征用生成器，改名为 baseline
        v_gen.module_name = f"{INIT_MODE}_baseline_ct"
        
        # 2. 将刚开局的 0/1 矩阵直接印成 RTL！
        v_gen.generate(discrete_init_M, discrete_init_P, output_file=f"output/netlists/{INIT_MODE}_baseline_ct.v")
        
        # 3. 封装 Baseline 的顶层
        v_gen.generate_multiplier_top(
            bit_width=BIT_WIDTH,
            top_file=f"output/netlists/{INIT_MODE}.v",
            ct_module_name=f"{INIT_MODE}_baseline_ct",
            top_module_name=f"{INIT_MODE}"
        )
        
        # 4. 恢复原名，保持工程整洁
        v_gen.module_name = "domac_compressor_tree"
    else:
        print(f"\n[BaselineGen] 当前为 '{INIT_MODE}' 冷启动模式，跳过生成基准对照组网表。")
    # =================================================================

    end_time = time.time()
    print("="*60)
    print(f" [任务完成] 全流程跑通，总耗时: {end_time - start_time:.2f} 秒")
    print(f" 请前往 output/netlists/domac_result.v 查看流片网表。")
    print("="*60)

# ================= [新增：跨服一键发射模块] =================
    print("\n[System] 启动跨服传输，正在将网表发射至 GPU 仿真服务器...")
    
    # 构造 rsync 命令
    # 注意: output/netlists/ 末尾的斜杠表示同步文件夹内部的所有文件，而不是文件夹本身
    rsync_cmd = [
        "rsync", "-avzP",
        "output/netlists/", 
        "-e", "ssh -p 16822",
        "lchangxian@202.120.39.27:/home/lchangxian/powerSimPlatform/src/rtl/"
    ]
    
    try:
        # 启动子进程执行传输，保留终端的实时输出 (stdout/stderr)
        subprocess.run(rsync_cmd, check=True)
        print("="*60)
        print("[System] 🚀 跨服投递成功！")
        print("所有 RTL 网表已安全降落在 powerSimPlatform/src/rtl/ 目录下，准备好进行功耗评估！")
        print("="*60)
    except subprocess.CalledProcessError as e:
        print(f"\n[Fatal Error] 传输任务坠毁！rsync 返回了非零状态码: {e.returncode}")
        print("-> 建议检查: 1. 服务器网络是否畅通 2. SSH 端口和用户名是否正确。")
    except FileNotFoundError:
        print("\n[Fatal Error] 本地系统未找到 rsync 命令，请先运行 sudo apt install rsync 安装。")

if __name__ == "__main__":
    # 开启 PyTorch 的异常检测，用于排查任何可能的梯度断裂
    # torch.autograd.set_detect_anomaly(True)
    main()