import torch
import torch.nn as nn
import torch.nn.functional as F
from .diff_sta import smooth_max_lse, diff_bilinear_interp

class DOMAC_CompressorTree(nn.Module):
    # 1. 在初始化参数中加入 device
    # def __init__(self, pp_cols, c_cols, fa_tensors, ha_tensors, c_types, req_time, device='cpu'):
    #     super(DOMAC_CompressorTree, self).__init__()
    def __init__(self, pp_cols, c_cols, fa_tensors, ha_tensors, c_types, req_time, device='cpu', init_m_logits=None, init_p_logits=None):
        super(DOMAC_CompressorTree, self).__init__()
        self.device = device  # <--- [核心新增] 记住目标设备
        self.pp_cols = pp_cols
        self.c_cols = c_cols
        self.num_pp = len(pp_cols)
        self.num_c = len(c_cols)
        self.c_types = c_types
        
        self.s_cols = c_cols
        self.co_cols = [col + 1 for col in c_cols] 
        self.node_cols = list(self.pp_cols) + list(self.s_cols) + list(self.co_cols)
        total_nodes = len(self.node_cols)
        
        self.num_fa_impls = len(fa_tensors)
        self.num_ha_impls = len(ha_tensors)
        self.max_impls = max(self.num_fa_impls, self.num_ha_impls)
        self.req_time = req_time
        
        self.pin_names = ['A', 'B', 'CI']
        self.num_pins_per_c = len(self.pin_names)
        
        # 预编译为 3D 张量的物理库 (现在会在解析时直接上 GPU)
        self.fa_areas, self.fa_caps, self.fa_arcs = self._parse_tensors(fa_tensors)
        self.ha_areas, self.ha_caps, self.ha_arcs = self._parse_tensors(ha_tensors)
        
        # ... 后续的 p_logits, dag_mask 等代码保持不变 ...
        # self.p_logits = nn.Parameter(torch.zeros(self.num_c, self.max_impls))
        if init_p_logits is not None:
            self.p_logits = nn.Parameter(init_p_logits.clone().to(device))
        else:
            self.p_logits = nn.Parameter(torch.zeros(self.num_c, self.max_impls, device=device))
        
        p_mask = torch.zeros(self.num_c, self.max_impls)
        active_pin_mask = torch.zeros(self.num_c * self.num_pins_per_c)
        
        for j, c_type in enumerate(self.c_types):
            if c_type == 'FA':
                p_mask[j, self.num_fa_impls:] = float('-inf')
                active_pin_mask[j*3 : j*3+3] = 1.0
            else:
                p_mask[j, self.num_ha_impls:] = float('-inf')
                active_pin_mask[j*3 : j*3+2] = 1.0
                active_pin_mask[j*3+2] = 0.0
                
        self.register_buffer('p_mask', p_mask)
        self.register_buffer('active_pin_mask', active_pin_mask)
        
        # total_target_pins = self.num_c * self.num_pins_per_c 
        # self.m_logits = nn.Parameter(torch.zeros(total_nodes, total_target_pins + 1))
        total_target_pins = self.num_c * self.num_pins_per_c 
        if init_m_logits is not None:
            # 采用传入的热启动矩阵
            self.m_logits = nn.Parameter(init_m_logits.clone().to(device))
        else:
            # 原本的白板初始化
            self.m_logits = nn.Parameter(torch.zeros(total_nodes, total_target_pins + 1, device=device))
            
        dag_mask = torch.full((total_nodes, total_target_pins + 1), float('-inf'))
        for i in range(total_nodes):
            for j in range(self.num_c):
                if i < self.num_pp:
                    is_downstream = True
                elif i < self.num_pp + self.num_c:
                    is_downstream = (i - self.num_pp) < j
                else:
                    is_downstream = (i - self.num_pp - self.num_c) < j

                if is_downstream and (self.node_cols[i] == self.c_cols[j]):
                    for p_idx in range(self.num_pins_per_c):
                        if self.active_pin_mask[j * 3 + p_idx] > 0.5:
                            dag_mask[i, j * self.num_pins_per_c + p_idx] = 0.0
            dag_mask[i, total_target_pins] = 0.0 
            
        self.register_buffer('dag_mask', dag_mask)

    def _parse_tensors(self, tensors):
        areas, caps = [], []
        stacked_arcs = {'S': {}, 'CO': {}}
        for p in self.pin_names:
            stacked_arcs['S'][p] = {'delay_lut': [], 'slew_lut': []}
            stacked_arcs['CO'][p] = {'delay_lut': [], 'slew_lut': []}
        
        ref_arc = None
        for ct in tensors:
            for out_p in ['S', 'CO']:
                for in_p in self.pin_names:
                    if ct.get(out_p, {}).get(in_p):
                        ref_arc = ct[out_p][in_p]
                        break
                if ref_arc: break
            if ref_arc: break
            
        index_1_slew = ref_arc['index_1_slew']
        index_2_load = ref_arc['index_2_load']

        # for ct in tensors:
        #     areas.append(ct.get('cell_area', 1.0))
        #     p_caps = [ct.get('pin_cap', {}).get(p, 0.001) for p in self.pin_names]
        #     caps.append(p_caps)

        #     for out_p in ['S', 'CO']:
        #         for in_p in self.pin_names:
        #             arc = ct.get(out_p, {}).get(in_p)
        #             if arc:
        #                 stacked_arcs[out_p][in_p]['delay_lut'].append(arc['delay_lut'])
        #                 stacked_arcs[out_p][in_p]['slew_lut'].append(arc['slew_lut'])
        #             else:
        #                 stacked_arcs[out_p][in_p]['delay_lut'].append(torch.full((7,7), 10.0))
        #                 stacked_arcs[out_p][in_p]['slew_lut'].append(torch.full((7,7), 10.0))
        for ct_idx, ct in enumerate(tensors):
            # ==========================================================
            # 1. 严格面积审查 (拒绝默认值 1.0)
            # ==========================================================
            if 'cell_area' not in ct:
                raise ValueError(f"[Fatal] 物理库审查失败: 传入的第 {ct_idx} 个单元缺失面积(cell_area)数据！")
            areas.append(ct['cell_area'])
            
            # ==========================================================
            # 2. 严格电容审查 (拒绝默认值 0.001)
            # ==========================================================
            p_caps = []
            for p in self.pin_names:
                if p not in ct.get('pin_cap', {}):
                    # 如果是 CI 引脚缺失，且当前单元可能是半加器(HA)，合法，用 0.0 填充
                    if p == 'CI':
                        p_caps.append(0.0)
                    else:
                        raise ValueError(f"[Fatal] 物理库审查失败: 单元缺失必须引脚 '{p}' 的电容数据！")
                else:
                    p_caps.append(ct['pin_cap'][p])
            caps.append(p_caps)

            # ==========================================================
            # 3. 严格时序弧审查 (拒绝伪造 10.0ns 的惩罚延迟)
            # ==========================================================
            for out_p in ['S', 'CO']:
                for in_p in self.pin_names:
                    arc = ct.get(out_p, {}).get(in_p)
                    if arc:
                        stacked_arcs[out_p][in_p]['delay_lut'].append(arc['delay_lut'])
                        stacked_arcs[out_p][in_p]['slew_lut'].append(arc['slew_lut'])
                    else:
                        # 物理上确实不存在的路径 (例如 HA 的 CI->S)，填入全 0 张量。
                        # 在 forward 时，这些路径会被 active_pin_mask 屏蔽，所以填 0 是物理合法的
                        dummy_lut = torch.zeros((7,7))
                        stacked_arcs[out_p][in_p]['delay_lut'].append(dummy_lut)
                        stacked_arcs[out_p][in_p]['slew_lut'].append(dummy_lut)
        # =========================================================================
        # [核弹级显存挂载] 强行把嵌套在字典里的 3D 物理矩阵全部搬运到 GPU 显存上！
        for out_p in ['S', 'CO']:
            for in_p in self.pin_names:
                stacked_arcs[out_p][in_p]['delay_lut'] = torch.stack(stacked_arcs[out_p][in_p]['delay_lut']).to(self.device)
                stacked_arcs[out_p][in_p]['slew_lut'] = torch.stack(stacked_arcs[out_p][in_p]['slew_lut']).to(self.device)
                stacked_arcs[out_p][in_p]['index_1_slew'] = index_1_slew.to(self.device)
                stacked_arcs[out_p][in_p]['index_2_load'] = index_2_load.to(self.device)

        return torch.tensor(areas, dtype=torch.float32, device=self.device), torch.tensor(caps, dtype=torch.float32, device=self.device), stacked_arcs

    # def forward(self, pp_at, pp_slew):
    #     P_c = F.softmax(self.p_logits + self.p_mask, dim=-1) 
    #     M_full = F.softmax(self.m_logits + self.dag_mask, dim=-1) 
    #     M_internal = M_full[:, :-1] 
    def forward(self, pp_at, pp_slew, tau=1.0):
        # 【核心修改】将 logits 除以温度 tau，tau 越小，概率越向 0/1 极化！
        P_c = F.softmax((self.p_logits + self.p_mask) / tau, dim=-1) 
        M_full = F.softmax((self.m_logits + self.dag_mask) / tau, dim=-1) 
        M_internal = M_full[:, :-1]
            
        expected_area = 0.0
        expected_pin_caps_list = []

        for j, c_type in enumerate(self.c_types):
            is_fa = (c_type == 'FA')
            lib_areas = self.fa_areas if is_fa else self.ha_areas
            lib_caps = self.fa_caps if is_fa else self.ha_caps
            
            p_j = P_c[j, :self.num_fa_impls] if is_fa else P_c[j, :self.num_ha_impls]
            expected_area = expected_area + torch.sum(p_j * lib_areas.to(P_c.device))
            
            c_caps = p_j @ lib_caps.to(P_c.device)
            expected_pin_caps_list.append(c_caps)
            
        flat_expected_pin_caps = torch.cat(expected_pin_caps_list)
        # ================= [核心物理修复：引入线负载模型 WLM] =================
        # 假设 TSMC 28nm 下，一根跨 Cell 互连线的平均寄生电容约为 0.003 pF (3 fF)
        # 你可以根据实际库的情况微调这个值
        WIRE_CAP_PER_NET = 0.000 
        
        # 原逻辑：loads = M_internal @ flat_expected_pin_caps
        # 新逻辑：只要存在连线（M_internal），就必须附加上导线的寄生电容！
        # loads = M_internal @ flat_expected_pin_caps + M_internal * WIRE_CAP_PER_NET
        # 修改 src/core/compressor_tree.py 第 201 行左右
        loads = M_internal @ (flat_expected_pin_caps + WIRE_CAP_PER_NET)
        # ====================================================================
        # loads = M_internal @ flat_expected_pin_caps 
        
        # =========================================================================
        # [Dr. Gemini 降维打击：Push 前向广播范式]
        # 1. 初始时刻：只利用外部输入的 PP 信号，一波推给压缩树的所有引脚进行打底！
        m_pp_all = M_internal[:self.num_pp, :]
        pin_ats_all = pp_at @ m_pp_all
        pin_slews_all = pp_slew @ m_pp_all
        # =========================================================================

        s_ats, s_slews = [], []
        co_ats, co_slews = [], []

        for j in range(self.num_c):
            col_start = j * self.num_pins_per_c
            col_end = col_start + self.num_pins_per_c
            
            # 2. 坐享其成：当前压缩器的输入引脚时序，早已被前面的兄弟计算好并推送过来了！
            # 彻底消灭了 O(N^2) 的 torch.stack 和切片！
            pin_ats = pin_ats_all[col_start:col_end]
            pin_slews = pin_slews_all[col_start:col_end]

            s_load = loads[self.num_pp + j]
            co_load = loads[self.num_pp + self.num_c + j]
            
            is_fa = (self.c_types[j] == 'FA')
            cell_arcs = self.fa_arcs if is_fa else self.ha_arcs
            P_j = P_c[j, :self.num_fa_impls] if is_fa else P_c[j, :self.num_ha_impls]
            
            s_paths_at, s_paths_slew = [], []
            co_paths_at, co_paths_slew = [], []
            
            for p_idx, p_name in enumerate(self.pin_names):
                if self.active_pin_mask[j * 3 + p_idx] > 0.5:
                    
                    arc_S = cell_arcs['S'][p_name]
                    delays_S = diff_bilinear_interp(pin_slews[p_idx], s_load, arc_S['index_1_slew'], arc_S['index_2_load'], arc_S['delay_lut'])
                    slews_S = diff_bilinear_interp(pin_slews[p_idx], s_load, arc_S['index_1_slew'], arc_S['index_2_load'], arc_S['slew_lut'])
                    
                    s_paths_at.append(pin_ats[p_idx] + torch.sum(P_j * delays_S))
                    s_paths_slew.append(torch.sum(P_j * slews_S))
                    
                    arc_CO = cell_arcs['CO'][p_name]
                    delays_CO = diff_bilinear_interp(pin_slews[p_idx], co_load, arc_CO['index_1_slew'], arc_CO['index_2_load'], arc_CO['delay_lut'])
                    slews_CO = diff_bilinear_interp(pin_slews[p_idx], co_load, arc_CO['index_1_slew'], arc_CO['index_2_load'], arc_CO['slew_lut'])
                    
                    co_paths_at.append(pin_ats[p_idx] + torch.sum(P_j * delays_CO))
                    co_paths_slew.append(torch.sum(P_j * slews_CO))

            # expected_s_at = smooth_max_lse(s_paths_at, gamma=0.01) if s_paths_at else torch.tensor(10.0, device=P_c.device)
            # expected_s_slew = smooth_max_lse(s_paths_slew, gamma=0.01) if s_paths_at else torch.tensor(10.0, device=P_c.device)
            # expected_co_at = smooth_max_lse(co_paths_at, gamma=0.01) if co_paths_at else torch.tensor(10.0, device=P_c.device)
            # expected_co_slew = smooth_max_lse(co_paths_slew, gamma=0.01) if co_paths_at else torch.tensor(10.0, device=P_c.device)
            # 如果某输出引脚没有任何合法输入路径，到达时间应当是 0.0 而不是惩罚性的 10.0ns
            expected_s_at = smooth_max_lse(s_paths_at, gamma=0.01) if s_paths_at else torch.tensor(0.0, device=P_c.device)
            expected_s_slew = smooth_max_lse(s_paths_slew, gamma=0.01) if s_paths_slew else torch.tensor(0.0, device=P_c.device)
            expected_co_at = smooth_max_lse(co_paths_at, gamma=0.01) if co_paths_at else torch.tensor(0.0, device=P_c.device)
            expected_co_slew = smooth_max_lse(co_paths_slew, gamma=0.01) if co_paths_slew else torch.tensor(0.0, device=P_c.device)
            # =========================================================================
            # 3. [核弹级推送] 本节点算完后，直接通过 M_internal 一波推给所有未来的潜在下游引脚！
            # a = a + b 是安全的 out-of-place 加法，完美保留 Autograd 梯度！
            pin_ats_all = pin_ats_all + expected_s_at * M_internal[self.num_pp + j, :]
            pin_slews_all = pin_slews_all + expected_s_slew * M_internal[self.num_pp + j, :]
            
            pin_ats_all = pin_ats_all + expected_co_at * M_internal[self.num_pp + self.num_c + j, :]
            pin_slews_all = pin_slews_all + expected_co_slew * M_internal[self.num_pp + self.num_c + j, :]
            # =========================================================================
            
            s_ats.append(expected_s_at)
            s_slews.append(expected_s_slew)
            co_ats.append(expected_co_at)
            co_slews.append(expected_co_slew)
            
        # 完美拼接，彻底消灭 list of tensors 导致的 O(N) 性能雪崩
        s_ats_t = torch.stack(s_ats)
        co_ats_t = torch.stack(co_ats)
        all_ats_tensor = torch.cat([pp_at, s_ats_t, co_ats_t])
        
        slacks = self.req_time - all_ats_tensor

        # # =========================================================================
        # # 🚀 [核弹级物理修复：可微 CPA 代理模型 (Differentiable CPA Proxy)]
        # # =========================================================================
        # # 1. 计算每个节点流向外部 CPA (Sink) 的连续概率
        # sink_probs = 1.0 - torch.sum(M_internal, dim=1)
        # sink_probs = torch.clamp(sink_probs, min=0.0, max=1.0)
        
        # # 2. 假设 28nm 工艺下，CPA 内部每经过 1 bit 的进位延迟约为 0.035 ns
        # # 你可以根据实际库的 FA CI->CO 延迟微调这个值
        # CPA_CARRY_DELAY_PER_BIT = 0.035 
        # max_col = max(self.node_cols)
        
        # # 3. 构造与所有节点对应的列权重张量，并送入 GPU
        # cols_tensor = torch.tensor(self.node_cols, dtype=torch.float32, device=all_ats_tensor.device)
        
        # # 4. 计算每个节点的 CPA 进位惩罚：
        # # 如果你处于第 c 列，且流向了 Sink，那么你必须为后续的 (max_col - c) 个进位链买单！
        # distance_to_msb = max_col - cols_tensor
        # cpa_penalty = distance_to_msb * CPA_CARRY_DELAY_PER_BIT * sink_probs
        
        # # 5. [核心] 带有 CPA 视野的全局有效到达时间
        # effective_ats_tensor = all_ats_tensor + cpa_penalty
        
        # # 使用引入了 CPA 惩罚的 AT 来计算 Slack
        # slacks = self.req_time - effective_ats_tensor
        # # =========================================================================
        # =========================================================================
        # 🚀 [真实物理校准：可切换架构的 CPA 代理模型]
        # =========================================================================
        # 1. 计算每个节点流向外部 CPA (Sink) 的连续概率
        sink_probs = 1.0 - torch.sum(M_internal, dim=1)
        sink_probs = torch.clamp(sink_probs, min=0.0, max=1.0)
        
        # 2. 基于 2026-03 DC 综合报告提取的绝对真实参数
        CPA_BIT_DELAY_RCA = 0.040      # 从报告得出: CI->CO 稳定在 0.04ns
        CPA_BASE_DELAY_RCA = 0.090     # 首位 HA + 末位 S 输出的固定开销
        
        CPA_TREE_STAGE_DELAY = 0.035   # 高速前缀树(Kogge-Stone)单级延迟预估
        CPA_BASE_DELAY_TREE = 0.055    # 树形加法器的基础进入延迟

        max_col = max(self.node_cols)
        cols_tensor = torch.tensor(self.node_cols, dtype=torch.float32, device=all_ats_tensor.device)
        distance_to_msb = max_col - cols_tensor
        
        # =======================================================
        # 模式切换开关：目前你的 DC 综合出的是 RCA，所以我们先用 RCA 模式训练！
        # 如果你未来在 DC 里开出了前缀树，请把这里改成 'PREFIX_TREE'
        # =======================================================
        CPA_ARCHITECTURE = 'RCA' 
        
        if CPA_ARCHITECTURE == 'RCA':
            # O(N) 线性惩罚模型，完美契合你刚刚贴出的 DC 综合网表！
            cpa_latency = CPA_BASE_DELAY_RCA + distance_to_msb * CPA_BIT_DELAY_RCA
        else:
            # O(log2(N)) 对数模型，代表 DesignWare 里的顶级综合结果
            cpa_latency = CPA_BASE_DELAY_TREE + CPA_TREE_STAGE_DELAY * torch.log2(distance_to_msb + 1.0)
            
        # 计算 CPA 综合惩罚
        cpa_penalty = cpa_latency * sink_probs
        
        # 3. 融合 CPA 惩罚后的全局有效到达时间
        effective_ats_tensor = all_ats_tensor + cpa_penalty
        
        # 4. 利用全链路时序计算最终的 Slack
        slacks = self.req_time - effective_ats_tensor
        # =========================================================================
        

# # =========================================================================
#         # 🚀 [真实物理校准：可切换架构的 CPA 代理模型 (DOMAC 28nm 精确版)]
#         # =========================================================================
#         # 1. 计算每个节点流向外部 CPA (Sink) 的连续概率
#         # M_internal 形状为 [num_nodes, total_comp_pins]
#         # 如果一个节点没有100%连接到压缩器，剩余的概率视作流向了底部的 CPA
#         sink_probs = 1.0 - torch.sum(M_internal, dim=1)
#         sink_probs = torch.clamp(sink_probs, min=0.0, max=1.0)
        
#         # 2. 基于 2026-03 DC 综合报告提取的绝对真实参数 (TSMC 28nm ZeroWireload)
#         # --- 行波进位 (RCA) 模式 ---
#         CPA_BIT_DELAY_RCA = 0.040      # 从报告得出: FA 的 CI->CO 稳定在 0.04ns
#         CPA_BASE_DELAY_RCA = 0.100     # 注入端(A->CO 0.06ns) + 提取端(S+MUX 0.04ns) = 0.10ns
        
#         # --- 前缀树 (Prefix Tree) 模式 ---
#         CPA_TREE_STAGE_DELAY = 0.035   # 高速前缀树(Kogge-Stone)单级复合门延迟预估
#         CPA_BASE_DELAY_TREE = 0.060    # 树形加法器的基础进出延迟

#         # 3. 计算到达 MSB 的物理距离 (决定了 Ripple Chain 的长度)
#         # 乘法器的最终 MSB (Highest Bit) 取决于位宽
#         max_col = max(self.node_cols) 
#         cols_tensor = torch.tensor(self.node_cols, dtype=torch.float32, device=all_ats_tensor.device)
        
#         # 距离 = MSB - 当前节点所在列 (clamp 确保安全，防止负数和 log2(0))
#         distance_to_msb = torch.clamp(max_col - cols_tensor, min=0.0)
        
#         # =======================================================
#         # 模式切换开关：如果未来综合脚本开启了超级前缀树，改为 'PREFIX_TREE'
#         # =======================================================
#         CPA_ARCHITECTURE = 'RCA' 
        
#         if CPA_ARCHITECTURE == 'RCA':
#             # O(N) 线性惩罚模型，完美契合目前网表生成的行波进位特征
#             cpa_latency = CPA_BASE_DELAY_RCA + distance_to_msb * CPA_BIT_DELAY_RCA
#         else:
#             # O(log2(N)) 对数模型，代表 DesignWare 里的顶级综合结果
#             cpa_latency = CPA_BASE_DELAY_TREE + CPA_TREE_STAGE_DELAY * torch.log2(distance_to_msb + 1.0)
            
#         # 4. 计算 CPA 综合惩罚 (软化处理)
#         # 只有真正流向 Sink 的那部分概率，才会被施加 CPA 的长路径惩罚
#         cpa_penalty = cpa_latency * sink_probs
        
#         # 5. 融合 CPA 惩罚后的全局有效到达时间 (Effective Arrival Time)
#         effective_ats_tensor = all_ats_tensor + cpa_penalty
        
#         # 6. 利用全链路时序计算最终的 Slack
#         slacks = self.req_time - effective_ats_tensor
#         # =========================================================================
        
        negative_slacks = torch.clamp(slacks, max=0.0)
        
        WNS = smooth_max_lse(-negative_slacks, gamma=0.01) 
        TNS = torch.sum(-negative_slacks)
        
        # ================= [新增：探针埋点] =================
        # 将当前周期的引脚期望AT和节点真实AT暂存，供训练探针解剖
        self._probe_pin_ats = pin_ats_all.detach()
        self._probe_node_ats = all_ats_tensor.detach()
        # ====================================================

        # =========================================================================
        # ⚡ [新增核弹级特性：全图可微毛刺功耗探针 (Glitch Power Profiler)]
        # =========================================================================
        # 1. 将铺平的引脚 AT 张量 reshape 为 [压缩器数量, 引脚数(3)]
        pin_ats_reshaped = pin_ats_all.view(self.num_c, self.num_pins_per_c)
        mask_reshaped = self.active_pin_mask.view(self.num_c, self.num_pins_per_c)
        
        # 2. 计算每个压缩器有效引脚的数量 (FA为3, HA为2)
        valid_pin_count = torch.sum(mask_reshaped, dim=1, keepdim=True)
        
        # 3. 计算每个压缩器的局部中心到达时间 (Mean AT)
        mean_ats = torch.sum(pin_ats_reshaped * mask_reshaped, dim=1, keepdim=True) / valid_pin_count
        
        # 4. 计算到达时间方差 (Variance) 
        glitch_variance = torch.sum(mask_reshaped * (pin_ats_reshaped - mean_ats)**2, dim=1)
        
        # 5. [核心优化] 转化为标准差 (Standard Deviation)，拉升数值量级！
        # ⚠️ 必须加上 1e-8 防止完美平衡时 torch.sqrt(0) 导致梯度爆炸产生 NaN！
        glitch_std = torch.sqrt(glitch_variance + 1e-8)
        
        # 6. 全图总毛刺代价 (标准差之和)
        expected_glitch = torch.sum(glitch_std)
        # =========================================================================
        
        # 在 return 列表中加上 expected_glitch
        return WNS, TNS, expected_area, expected_glitch, M_internal, P_c
    
        # return WNS, TNS, expected_area, M_internal, P_c