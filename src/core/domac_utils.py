# domac_utils.py
import torch
import numpy as np

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
    node_cols = model.virtual_node_cols

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
def probe_post_legalization_eval(model, loss_engine, trainer_hyperparams, discrete_local_M, discrete_P, final_P, pp_at, pp_slew, REQ_TIME, PP_COLS, COMP_COLS):
    print("\n[Evaluator] 正在对坍缩后的 0/1 离散硬连线进行最终物理时序与毛刺功耗核算...")
    with torch.no_grad():
        # 1. 构造离散化物理尺寸的 One-Hot 张量
        discrete_P_tensor = torch.zeros_like(final_P)
        for i, idx in enumerate(discrete_P):
            discrete_P_tensor[i, idx] = 1.0

        # 2. 备份原本训练结束时的模糊 logits，防止污染模型状态
        orig_local_m_logits = [m.clone() for m in model.local_m_logits]
        orig_p_logits = model.p_logits.clone()

        # 3. [核心技巧] 注入极端 Logits 强制网络走硬连线 (局部矩阵版)
        for m_param, m_disc in zip(model.local_m_logits, discrete_local_M):
            new_m = torch.full_like(m_param, -1e4)
            new_m[m_disc == 1.0] = 1e4
            m_param.copy_(new_m)

        new_p = torch.full_like(orig_p_logits, -1e4)
        new_p[discrete_P_tensor == 1.0] = 1e4
        model.p_logits.copy_(new_p)

        # 4. 执行一次纯净的前向传播与 Loss 计算
        eval_wns, eval_tns, eval_area, eval_glitch, eval_local_M, eval_P = model(pp_at, pp_slew, tau=1.0)
        
        eval_loss, eval_dict = loss_engine(
            eval_wns, eval_tns, eval_area, eval_glitch, eval_local_M, eval_P, 
            trainer_hyperparams, model.local_meta
        )

        print(f" -> [坍缩后真实指标] WNS: {eval_dict['wns'].item():.4f} ns | "
              f"Area: {eval_dict['area'].item():.4f} μm² | "
              f"Glitch (Var): {eval_dict['glitch'].item():.6f} | "
              f"L_BM: {eval_dict['l_bm'].item():.4f} | "
              f"Total Loss: {eval_loss.item():.4f}")
        
        # ================= [WNS 计算过程溯源探针] =================
        print("\n" + "="*60)
        print(" 🧮 [DOMAC 探针] 离散化网表 WNS 内部计算逻辑核对")
        print("="*60)
        
        # 1. 提取离散化评估后的全图所有虚拟节点的 AT (到达时间)
        all_ats = model._probe_node_ats.detach().cpu().numpy()
        req_time = REQ_TIME 
        
        # 2. 计算每个节点的 Slack (容限)
        slacks = req_time - all_ats
        
        # 3. 找出全图 Slack 最差的节点 (即 AT 最大的节点)
        worst_idx = np.argmin(slacks)
        worst_at = all_ats[worst_idx]
        worst_slack = slacks[worst_idx]
        
        # 4. 翻译这个“罪魁祸首”节点的物理身份 (已适配 Bypass 虚拟线)
        num_pp = len(PP_COLS)
        num_c = len(COMP_COLS)
        if worst_idx < num_pp:
            node_name = f"原始输入信号 PP_in_{worst_idx}"
        elif worst_idx < num_pp + num_c:
            c_idx = worst_idx - num_pp
            node_name = f"压缩器 U_comp_{c_idx} 的 S (Sum) 输出引脚"
        elif worst_idx < num_pp + 2 * num_c:
            c_idx = worst_idx - num_pp - num_c
            node_name = f"压缩器 U_comp_{c_idx} 的 CO (Carry-Out) 输出引脚"
        else:
            node_name = f"虚拟透传线 (Bypass Wire) ID_{worst_idx}"
            
        print(f" -> 1. 设定的目标到达时间 (REQ_TIME) : {req_time:.4f} ns")
        print(f" -> 2. 全局最慢的关键节点判定为     : {node_name}")
        print(f" -> 3. 查表计算的该节点实际 AT      : {worst_at:.4f} ns")
        print(f" -> 4. 原始负超额 (Negative Slack)  : {min(0.0, worst_slack):.4f} ns")
        print(f" -> 5. AI 最终汇报的平滑 eval_wns   : {eval_wns.item():.4f} ns")
        print("="*60 + "\n")

        # 5. 恢复原本的 logits (保持代码状态安全)
        for m_param, orig_m in zip(model.local_m_logits, orig_local_m_logits):
            m_param.copy_(orig_m)
        model.p_logits.copy_(orig_p_logits)
        
# ================= [探针 3：波前到达时间 (Wavefront AT)] =================
def probe_wavefront_at(model, discrete_M):
    print("\n" + "="*65)
    print(" 🌊 [DOMAC 探针] CPA 输入波前到达时间 (Wavefront AT) 剖析")
    print("="*65)
    
    # 提取离散化评估后，全图节点的真实物理到达时间
    node_ats = model._probe_node_ats.detach().cpu().numpy()
    node_cols = model.virtual_node_cols
    
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

def build_local_routing_graph(bit_width, pp_cols, c_cols, c_types):
    """
    生成局部 M_{i,j} 矩阵所需的层级化物理路由元数据 (严格同步画布逻辑修复版)
    """
    num_pp = len(pp_cols)
    num_c = len(c_cols)
    max_cols = bit_width * 2
    
    # 1. 初始化连线池 (记录全局 Wire ID)
    wires = [[] for _ in range(max_cols)]
    for k, col in enumerate(pp_cols):
        if col >= len(wires):
            # 应对极其罕见的溢出列
            wires.extend([[] for _ in range(col - len(wires) + 1)])
        wires[col].append(k) 
        
    dadda_seq = [2]
    while dadda_seq[-1] < bit_width:
        dadda_seq.append(int(dadda_seq[-1] * 1.5))
    dadda_seq.reverse()
    targets = [t for t in dadda_seq if t < max([len(w) for w in wires])]
    
    # 预分配压缩器 ID (使用 defaultdict 防越界)
    from collections import defaultdict
    comp_queue = defaultdict(lambda: {'FA': [], 'HA': []})
    for j, (col, c_type) in enumerate(zip(c_cols, c_types)):
        comp_queue[col][c_type].append(j)
    comp_usage = defaultdict(lambda: {'FA': 0, 'HA': 0})
    
    routing_stages = []
    next_wire_id = num_pp + 2 * num_c # Bypass 虚拟线的 ID 从这里开始分配
    
    # 2. 逐级生成局部矩阵元数据
    for target in targets:
        stage_meta = []
        next_wires = [[] for _ in range(len(wires))]
        carry_from_prev = []
        
        for col in range(len(wires)):
            # [核心修复]: Native Wires 才是决定是否需要增加压缩器的基准
            native_wires = wires[col]
            in_wires = native_wires + carry_from_prev
            
            V = len(native_wires)
            num_carries_in = len(carry_from_prev)
            
            # 为刚刚到来的进位预留位置
            allowed_output = target - num_carries_in
            
            if V > allowed_output:
                reduction_needed = V - allowed_output
                f = reduction_needed // 2
                h = reduction_needed % 2
                
                fa_ids, ha_ids, carries_gen, pin_global_indices = [], [], [], []
                
                # 分配全加器
                for _ in range(f):
                    c_id = comp_queue[col]['FA'][comp_usage[col]['FA']]
                    comp_usage[col]['FA'] += 1
                    fa_ids.append(c_id)
                    next_wires[col].append(num_pp + c_id)             # S 输出
                    carries_gen.append(num_pp + num_c + c_id)         # CO 输出
                    pin_global_indices.extend([c_id*3, c_id*3+1, c_id*3+2])
                    
                # 分配半加器
                for _ in range(h):
                    c_id = comp_queue[col]['HA'][comp_usage[col]['HA']]
                    comp_usage[col]['HA'] += 1
                    ha_ids.append(c_id)
                    next_wires[col].append(num_pp + c_id)
                    carries_gen.append(num_pp + num_c + c_id)
                    pin_global_indices.extend([c_id*3, c_id*3+1])
                    
                # 剩余的信号走透传 Bypass 通道
                num_bypass = len(in_wires) - (f * 3 + h * 2)
                out_bypass_ids = []
                for _ in range(num_bypass):
                    out_bypass_ids.append(next_wire_id)
                    next_wires[col].append(next_wire_id)
                    next_wire_id += 1
                    
                stage_meta.append({
                    'col': col, 'in_wires': in_wires, 'fa_ids': fa_ids, 'ha_ids': ha_ids,
                    'out_bypass_ids': out_bypass_ids, 'pin_global_indices': pin_global_indices
                })
                # 本列生成的进位传给下一列
                carry_from_prev = carries_gen
                
            else:
                # 如果不需要压缩，所有进来的信号 (原生 + 进位) 全部走 Bypass
                num_bypass = len(in_wires)
                out_bypass_ids = []
                for _ in range(num_bypass):
                    out_bypass_ids.append(next_wire_id)
                    next_wires[col].append(next_wire_id)
                    next_wire_id += 1
                    
                if num_bypass > 0:
                    stage_meta.append({
                        'col': col, 'in_wires': in_wires, 'fa_ids': [], 'ha_ids': [],
                        'out_bypass_ids': out_bypass_ids, 'pin_global_indices': []
                    })
                carry_from_prev = []
                
        # 处理最高位溢出的进位
        if carry_from_prev:
            next_wires.append(carry_from_prev)
            
        routing_stages.append(stage_meta)
        wires = next_wires
        
    return routing_stages, next_wire_id