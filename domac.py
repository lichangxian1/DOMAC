import os
import sys
import torch
import time
import subprocess

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
    

def main():
    print("="*60)
    print(" [DOMAC 净室复现] TSMC 28nm 节点可微 STA 优化框架")
    print("="*60)
    
    TARGET_CELLS = [
        'FA1D0BWP12T40P140', 'FA1D1BWP12T40P140', 'FA1D2BWP12T40P140', 'FA1D4BWP12T40P140',
        'HA1D0BWP12T40P140', 'HA1D1BWP12T40P140', 'HA1D2BWP12T40P140', 'HA1D4BWP12T40P140'
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
    pp_at = torch.linspace(0.0, 0.1, NUM_PP, device=device) 
    pp_slew = torch.full((NUM_PP,), 0.02, device=device)
    REQ_TIME = 0 
    print("REQ_TIME：" + str(REQ_TIME))

    print(f"\n[Engine] 构建异构可微压缩树...")
    # 2. 传递 device 给模型，并强制模型所有 Parameter 和 Buffer 上 GPU
    model = DOMAC_CompressorTree(PP_COLS, COMP_COLS, fa_tensors, ha_tensors, C_TYPES, REQ_TIME, device=device).to(device)

    # loss_engine = DOMACLossFunction()
    # 将动态约束传入 Loss 引擎
    loss_engine = DOMACLossFunction(target_sink_count=TARGET_SINK_COUNT)
    trainer = DOMACTrainer(model, loss_engine, lr=0.05)
    
    print("\n[Engine] 物理映射与梯度反向传播开始...")
    
    start_time = time.time()
    final_M, final_P = trainer.train(pp_at, pp_slew, max_epochs=300)
    
    print("\n[System] 优化执行完毕！网表拓扑已坍缩至离散界限附近。")
    
    # ================= [新增联调区块：全自动生成网表] =================
    
    # 1. 启动合法化器 (离散坍缩)
    legalizer = DOMACLegalizer()
    discrete_M, discrete_P = legalizer.legalize(final_M, final_P, C_TYPES, model.dag_mask)
    
    # # ================= [新增：Dr. Gemini 的矩阵透视镜] =================
    # # 临时修改 PyTorch 的打印选项，防止矩阵被折叠省略，保留 4 位小数以便观察概率分布
    # torch.set_printoptions(precision=4, sci_mode=False, linewidth=150, profile="full")
    
    # print("\n" + "="*60)
    # print(" 🔍 [矩阵透视] 连续概率态 vs 物理离散态")
    # print("="*60)
    
    # print(f"\n1. [连续概率态] 物理实现矩阵 P_c (Shape: {final_P.shape}):")
    # print("   (行代表 6 台压缩器，列代表 8 种物理门选项的选中概率)")
    # print(final_P)
    
    # print("\n2. [离散坍缩态] 最终选定的物理门索引 P_discrete:")
    # print(f"   {discrete_P}")
    
    # print(f"\n3. [连续概率态] 互连拓扑矩阵 M_internal (Shape: {final_M.shape}):")
    # print("   (行代表 28 个物理节点，列代表 18 个压缩器靶点引脚的连线概率)")
    # print(final_M)
    
    # print(f"\n4. [离散坍缩态] 合法化后的纯 0/1 拓扑矩阵 discrete_M (Shape: {discrete_M.shape}):")
    # print("   (这就是最终喂给 Verilog 的纯血 EDA 布线图)")
    # print(discrete_M)
    
    # print("="*60 + "\n")
    # # 恢复 PyTorch 默认打印截断（可选）
    # torch.set_printoptions(profile="default")
    # # ===================================================================

    # 2. 启动 Verilog 打印机
    # 确保输出目录存在
    os.makedirs("output/netlists", exist_ok=True)
    
    v_gen = VerilogGenerator(
        pp_cols=PP_COLS,       # <--- 新增传入参数
        c_cols=COMP_COLS,      # <--- 新增传入参数
        c_types=C_TYPES,
        fa_cell_names=fa_names,
        ha_cell_names=ha_names
    )
    
    netlist_path = "output/netlists/domac_result.v"
    tb_path = "output/netlists/tb_domac.v"
    
    v_gen.generate(discrete_M, discrete_P, output_file=netlist_path)
    v_gen.generate_testbench(tb_file=tb_path, netlist_file=netlist_path)
    # ================= [新增模块组装] =================
    top_path = "output/netlists/domac_multiplier_top.v"
    v_gen.generate_multiplier_top(
        bit_width=BIT_WIDTH, 
        top_file=top_path, 
        ct_module_name="domac_compressor_tree"
    )

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