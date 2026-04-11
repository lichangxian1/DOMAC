# domac_utils.py
import torch
import numpy as np
from collections import Counter

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
    """
    [DOMAC 终极架构] 任意位宽无符号 Radix-4 Booth 编码画布生成器
    动态模拟点阵分布，保证与 Verilog RTL 拓扑 100% 对齐。
    """
    print(f"\n[Canvas Generator] 动态推演 {bit_width}x{bit_width} 无符号 Radix-4 Booth 乘法器画布...")
    G = (bit_width + 2) // 2 
    max_cols = bit_width * 2
    
    # 不再只存数量，而是存每个点的具体延迟！
    # pp_matrix[col] = [delay1, delay2, ...]
    pp_matrix = [[] for _ in range(max_cols)]
    
    # 根据 28nm 工艺设定的真实到达时间基准 (ns)
    DELAY_NORMAL = 0.08  # 基础数据位 (混合了 +A, -A 的均值)
    DELAY_NEG    = 0.11  # 进位/符号控制位 (最慢)
    DELAY_CONST  = 0.00  # 常数 1 (最快)
    
    for i in range(G):
        start_col = i * 2
        
        # 1. 基础部分积数据位
        for j in range(bit_width + 1):
            col = start_col + j
            if col < max_cols:
                pp_matrix[col].append(DELAY_NORMAL)
                
        # 2. 负数补码的 +1 补偿位
        if start_col < max_cols:
            pp_matrix[start_col].append(DELAY_NEG)
            
        # 3. 符号位扩展技巧 (修改型扩展 - 修复版)
        sign_col = start_col + bit_width + 1
        if i == 0:
            if sign_col < max_cols:
                pp_matrix[sign_col].append(DELAY_NEG)   # ~neg_0
                pp_matrix[sign_col].append(DELAY_CONST) # 常数1
            if sign_col + 1 < max_cols:
                pp_matrix[sign_col + 1].append(DELAY_CONST) # 补偿的常数1
        elif i < G - 1:
            if sign_col < max_cols:
                pp_matrix[sign_col].append(DELAY_NEG)   # ~neg_i
            if sign_col + 1 < max_cols:
                pp_matrix[sign_col + 1].append(DELAY_CONST) # 常数1

    # 展开为 DOMAC 引擎所需的 1D 列表
    pp_cols = []
    pp_at_init = []
    
    for col in range(max_cols):
        for delay in pp_matrix[col]:
            pp_cols.append(col)
            pp_at_init.append(delay)

    print(f" -> Booth 编码组数: {G}")
    print(f" -> 动态分配的初始 PP 节点总数: {len(pp_cols)}")

    # ---------------------------------------------------------
    # Dadda 树目标高度推演与压缩分配 (自适应高度)
    # ---------------------------------------------------------
    dots_in_col = [len(col_dots) for col_dots in pp_matrix]
    
    dadda_seq = [2]
    while dadda_seq[-1] < max(dots_in_col):
        dadda_seq.append(int(dadda_seq[-1] * 1.5))
    dadda_seq.reverse() 
    
    targets = [t for t in dadda_seq if t < max(dots_in_col)]
    print(f" -> 动态 Dadda 收敛序列: {targets}")
    
    comp_cols_raw = []
    c_types_raw = []
    current_dots = list(dots_in_col)
    
    for stage_idx, target in enumerate(targets):
        current_len = len(current_dots)
        next_dots = [0] * current_len
        carry_from_prev = 0
        
        for col in range(current_len):
            V = current_dots[col]
            allowed_output = target - carry_from_prev
            
            if V > allowed_output:
                reduction_needed = V - allowed_output
                f = reduction_needed // 2
                h = reduction_needed % 2
                
                for _ in range(f):
                    comp_cols_raw.append(col)
                    c_types_raw.append('FA')
                for _ in range(h):
                    comp_cols_raw.append(col)
                    c_types_raw.append('HA')
                    
                dots_stay = V - reduction_needed
                next_dots[col] = dots_stay + carry_from_prev
                carry_from_prev = f + h
            else:
                next_dots[col] = V + carry_from_prev
                carry_from_prev = 0
                
        if carry_from_prev > 0:
            if len(next_dots) < max_cols + 1:
                next_dots.append(carry_from_prev)
            else:
                next_dots[-1] += carry_from_prev
                
        current_dots = next_dots
        
    final_max = max(current_dots)
    print(f" -> 申请 {len(comp_cols_raw)} 个压缩器画布 ({c_types_raw.count('FA')} FA, {c_types_raw.count('HA')} HA)。\n")
    
    combined = sorted(zip(comp_cols_raw, c_types_raw), key=lambda x: x[0])
    comp_cols = [x[0] for x in combined]
    c_types = [x[1] for x in combined]

    return pp_cols, comp_cols, c_types, pp_at_init
    
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
    #  
    # for i in range(bit_width):
    #     for j in range(bit_width):
    #         signals[i+j].append(k)
    #         k += 1
    # [修复] 1. 动态感知 Booth 阵列的 PP 信号源节点
    for k, col in enumerate(pp_cols):
        signals[col].append(k)
            
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

# ================= [探针 1：列高溢出探针] =================
def probe_column_height_overflow(model, discrete_M):
    """
    [DOMAC 探针] 最终输出到 CPA 的列高 (Column Height) 核查
    （原版保留了全部的注释与逻辑）
    """
    print("\n" + "="*60)
    print(" 🕵️ [DOMAC 探针] 最终输出到 CPA 的列高 (Column Height) 核查")
    print("="*60)

    # 1. 获取所有节点的列权重属性
    node_cols = model.node_cols

    # 2. 找出流向 Sink (下游 CPA) 的节点
    # 在 discrete_M 中，如果某一行全为 0，说明该节点没有连向任何内部压缩器引脚，必然流向了 Sink
    row_sums = torch.sum(discrete_M, dim=1)
    nodes_to_sink = torch.where(row_sums == 0)[0].tolist()

    # 3. 提取这些残余节点的列权重，并统计每一列的数量
    sink_weights = [node_cols[i] for i in nodes_to_sink]
    col_counts = Counter(sink_weights)
    
    overflow_detected = False
    for col, count in sorted(col_counts.items()):
        if count > 2:
            # 超过 2 个信号，必然触发 DC 综合工具的多重 CPA 级联雪崩！
            print(f" 🚨 [致命溢出] 第 {col:>2} 列: 残留了 {count} 个未压缩信号！")
            overflow_detected = True
        else:
            print(f" ✅ [正常]     第 {col:>2} 列: 残留 {count} 个信号")

    if overflow_detected:
        print("\n ⚠️ 结论：列压缩未彻底完成！")
        print("    下游 DC 综合工具将被迫把多余的信号强行跨接 (如 intadd_1 -> intadd_0)，导致 0.4ns+ 的时序雪崩！")
    else:
        print("\n 完美：所有列已严格压缩至 <= 2，完全符合进入单一高速 CPA 的条件。")
    print("="*60 + "\n")

# ================= [探针 2：离散化后硬连线物理评估 & WNS 溯源] =================
def probe_post_legalization_eval(model, loss_engine, trainer_hyperparams, discrete_M, discrete_P, final_P, pp_at, pp_slew, REQ_TIME, PP_COLS, COMP_COLS):
    print("\n[Evaluator] 正在对坍缩后的 0/1 离散硬连线进行最终物理时序与毛刺功耗核算...")
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
        new_m_logits = torch.full_like(orig_m_logits, -1e4)
        new_m_logits[discrete_M_full == 1.0] = 1e4
        model.m_logits.copy_(new_m_logits)

        new_p_logits = torch.full_like(orig_p_logits, -1e4)
        new_p_logits[discrete_P_tensor == 1.0] = 1e4
        model.p_logits.copy_(new_p_logits)

        # 5. 执行一次纯净的前向传播与 Loss 计算
        # 【修改点 1】增加 eval_glitch 接收毛刺功耗方差
        eval_wns, eval_tns, eval_area, eval_glitch, eval_M, eval_P = model(pp_at, pp_slew, tau=1.0)
        
        # 【修改点 2】将 eval_glitch 传给 loss_engine
        eval_loss, eval_dict = loss_engine(
            eval_wns, eval_tns, eval_area, eval_glitch, eval_M, eval_P, trainer_hyperparams, 
            model.active_pin_mask, model.c_types
        )

        # 【修改点 3】在最终评估报告中打印出 Glitch 的数值
        print(f" -> [坍缩后真实指标] WNS: {eval_dict['wns'].item():.4f} ns | "
              f"Area: {eval_dict['area'].item():.4f} μm² | "
              f"Glitch (Var): {eval_dict['glitch'].item():.6f} | "
              f"L_BM: {eval_dict['l_bm'].item():.4f} | "
              f"Total Loss: {eval_loss.item():.4f}")
        
        # ================= [WNS 计算过程溯源探针] =================
        print("\n" + "="*60)
        print(" 🧮 [DOMAC 探针] 离散化网表 WNS 内部计算逻辑核对")
        print("="*60)
        
        # 1. 提取离散化评估后的全图所有节点的 AT (到达时间)
        all_ats = model._probe_node_ats.detach().cpu().numpy()
        req_time = REQ_TIME 
        
        # 2. 计算每个节点的 Slack (容限)
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
        print(f" -> 5. AI 最终汇报的平滑 eval_wns   : {eval_wns.item():.4f} ns")
        print("="*60 + "\n")

        # 6. 恢复原本的 logits (保持代码状态安全)
        model.m_logits.copy_(orig_m_logits)
        model.p_logits.copy_(orig_p_logits)

# ================= [探针 3：波前到达时间 (Wavefront AT)] =================
def probe_wavefront_at(model, discrete_M):
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
        if col < 7 and max_at > 0.18:
            status = "🚨 危险 (波前倒置/低位滞后)"
        elif col >= 7 and max_at > 0.28:
            status = "⚠️ 偏高 (全局延迟瓶颈)"
        else:
            status = "✅ 优秀 (符合 CPA 期望)"
            
        print(f" Col {col:<10} | {max_at:.4f} ns{'':<16} | {status}")
        
    print("="*65 + "\n")