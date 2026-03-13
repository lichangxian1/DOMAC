import torch
import torch.nn as nn
import torch.nn.functional as F
# from .diff_sta import smooth_max_lse, compute_expected_timing
from .diff_sta import smooth_max_lse, diff_bilinear_interp

class DOMAC_CompressorTree(nn.Module):
    def __init__(self, pp_cols, comp_cols, cell_tensors, req_time):
        super(DOMAC_CompressorTree, self).__init__()
        self.pp_cols = pp_cols  # 部分积列权重列表
        self.comp_cols = comp_cols  # 压缩器列权重列表
        self.num_pp = len(pp_cols) # 部分积节点数
        self.num_c = len(comp_cols) # 压缩器数量
        self.num_impls = len(cell_tensors)  
        self.req_time = req_time
        
        # ================= [架构升格] =================
        # 节点总数 = 部分积(PP) + 压缩器Sum输出 + 压缩器Carry输出
        self.total_nodes = self.num_pp + 2 * self.num_c
        
        # 极度硬核：为所有节点打上列权重标签 (Bit-Weight)
        # 魔法就在这一行：Carry 输出的列权重自动 +1 ！！
        self.node_cols = pp_cols + comp_cols + [c + 1 for c in comp_cols]
        # ==============================================
        
        # 动态提取面积和电容 (保持原有代码逻辑)
        extracted_areas, extracted_caps = [], []
        for ct in cell_tensors:
            extracted_areas.append(ct.get('cell_area', 1.0))
            pin_caps = ct.get('pin_cap', {})
            extracted_caps.append(sum(pin_caps.values()) / len(pin_caps) if pin_caps else 0.001)
            
        self.area_lib = torch.tensor(extracted_areas, dtype=torch.float32)
        self.cap_in_lib = torch.tensor(extracted_caps, dtype=torch.float32)
        
        # ================= [双引脚物理融合] =================
        self.cell_worst_luts = []
        for cell_idx, ct in enumerate(cell_tensors):
            s_delays, s_slews = [], []
            co_delays, co_slews = [], []
            ref_idx1, ref_idx2 = None, None
            
            for out_p, in_dict in ct.items():
                if out_p in ['cell_area', 'pin_cap']: continue
                for in_p, arc_data in in_dict.items():
                    if ref_idx1 is None:
                        ref_idx1 = arc_data['index_1_slew']
                        ref_idx2 = arc_data['index_2_load']
                    # 按照 S 和 CO 进行分流融合！
                    if out_p == 'S':
                        s_delays.append(arc_data['delay_lut'])
                        s_slews.append(arc_data['slew_lut'])
                    elif out_p == 'CO':
                        co_delays.append(arc_data['delay_lut'])
                        co_slews.append(arc_data['slew_lut'])
                        
            # 将 S 和 CO 各自的 Worst-case 打包存放
            self.cell_worst_luts.append({
                'index_1_slew': ref_idx1, 'index_2_load': ref_idx2,
                'S_delay': torch.max(torch.stack(s_delays), dim=0)[0],
                'S_slew': torch.max(torch.stack(s_slews), dim=0)[0],
                'CO_delay': torch.max(torch.stack(co_delays), dim=0)[0],
                'CO_slew': torch.max(torch.stack(co_slews), dim=0)[0]
            })

        self.p_logits = nn.Parameter(torch.zeros(self.num_c, self.num_impls))
        self.m_logits = nn.Parameter(torch.zeros(self.total_nodes, self.num_c + 1))
        
        # ================= [算术列掩码 (Arithmetic Mask)] =================
        self.dag_mask = torch.full((self.total_nodes, self.num_c + 1), float('-inf'))
        
        # 规则定义：只有当源节点的列权重等于目标压缩器的列权重时，连接才合法
        # 这里的源节点包括 PP、Sum 和 Carry 三类，目标节点是 Sum 和 Carry
        def get_src_comp_idx(i):    
            if i < self.num_pp: return -1 # 是 PP
            if i < self.num_pp + self.num_c: return i - self.num_pp # 是 Sum
            return i - self.num_pp - self.num_c # 是 Carry
            
        for i in range(self.total_nodes):
            src_c = get_src_comp_idx(i)
            for j in range(self.num_c):
                # 规则1: 拓扑防环 (源节点的压缩器索引必须小于目标)
                if src_c < j:
                    # 规则2: 数学对齐 (源节点的列权重 必须等于 目标压缩器的列权重)
                    if self.node_cols[i] == self.comp_cols[j]:
                        self.dag_mask[i, j] = 0.0
                        
            self.dag_mask[i, self.num_c] = 0.0 # Sink通道开放

    def query_cell_worst_timing(self, cell_idx, out_pin, slew, load):
        """精准查询 S 或 CO 引脚的 Worst-case 包络"""
        lut_data = self.cell_worst_luts[cell_idx]
        delay = diff_bilinear_interp(slew, load, lut_data['index_1_slew'], lut_data['index_2_load'], lut_data[f'{out_pin}_delay'])
        out_slew = diff_bilinear_interp(slew, load, lut_data['index_1_slew'], lut_data['index_2_load'], lut_data[f'{out_pin}_slew'])
        return delay, out_slew
    
    def forward(self, pp_at, pp_slew):
        P_c = F.softmax(self.p_logits, dim=-1)
        M_full = F.softmax(self.m_logits + self.dag_mask, dim=-1)
        M_internal = M_full[:, :-1]
        
        expected_area = torch.sum(P_c @ self.area_lib)
        expected_node_caps = P_c @ self.cap_in_lib
        loads = M_internal @ expected_node_caps
        
        node_ats = [None] * self.total_nodes
        node_slews = [None] * self.total_nodes
        
        for i in range(self.num_pp):
            node_ats[i] = pp_at[i]
            node_slews[i] = pp_slew[i]
            
        gamma = 0.01 # LSE的平滑温度系数
            
        for j in range(self.num_c):
            in_probs = M_internal[:, j]
            arrival_paths_S, slew_paths_S = [], []
            arrival_paths_CO, slew_paths_CO = [], []
            
            # 为了防止 Slew 爆炸，计算实际汇入该节点的概率总和
            sum_in_probs = torch.sum(in_probs) + 1e-8 
            
            for i in range(self.total_nodes):
                prob_ij = in_probs[i]
                
                if self.dag_mask[i, j] == 0.0:
                    # S 路径
                    delay_fa_S, slew_fa_S = self.query_cell_worst_timing(0, 'S', node_slews[i], loads[i])
                    delay_ha_S, slew_ha_S = self.query_cell_worst_timing(1, 'S', node_slews[i], loads[i])
                    delay_ij_S = P_c[j][0] * delay_fa_S + P_c[j][1] * delay_ha_S
                    slew_ij_S = P_c[j][0] * slew_fa_S + P_c[j][1] * slew_ha_S
                    
                    # 修正1：必须乘以 gamma，才能在 Log-Space 中正确等效概率乘法
                    path_at_S = (node_ats[i] + delay_ij_S) + gamma * torch.log(prob_ij + 1e-8) 
                    arrival_paths_S.append(path_at_S)
                    # 修正2：Slew 计算必须按输入概率的相对占比进行归一化均值计算
                    slew_paths_S.append(slew_ij_S * (prob_ij / sum_in_probs))
                    
                    # CO 路径
                    delay_fa_CO, slew_fa_CO = self.query_cell_worst_timing(0, 'CO', node_slews[i], loads[i])
                    delay_ha_CO, slew_ha_CO = self.query_cell_worst_timing(1, 'CO', node_slews[i], loads[i])
                    delay_ij_CO = P_c[j][0] * delay_fa_CO + P_c[j][1] * delay_ha_CO
                    slew_ij_CO = P_c[j][0] * slew_fa_CO + P_c[j][1] * slew_ha_CO
                    
                    path_at_CO = (node_ats[i] + delay_ij_CO) + gamma * torch.log(prob_ij + 1e-8)
                    arrival_paths_CO.append(path_at_CO)
                    slew_paths_CO.append(slew_ij_CO * (prob_ij / sum_in_probs))
            
            # LSE 汇聚 AT
            node_ats[self.num_pp + j] = smooth_max_lse(arrival_paths_S, gamma=gamma) if arrival_paths_S else torch.tensor(0.0)
            node_ats[self.num_pp + self.num_c + j] = smooth_max_lse(arrival_paths_CO, gamma=gamma) if arrival_paths_CO else torch.tensor(0.0)
            
            # Slew 汇聚 (已归一化，直接 sum 即可代表期望 Slew)
            node_slews[self.num_pp + j] = sum(slew_paths_S) if slew_paths_S else torch.tensor(0.0)
            node_slews[self.num_pp + self.num_c + j] = sum(slew_paths_CO) if slew_paths_CO else torch.tensor(0.0)

        # ================= [全可微的 Sink 提取] =================
        sink_probs = M_full[:, -1]
        node_ats_tensor = torch.stack(node_ats)
        
        # 修正3：纯净的物理 Slack，不污染 AT 本身
        slacks = self.req_time - node_ats_tensor
        negative_slacks = torch.clamp(slacks, max=0.0)
        
        # TNS (Total Negative Slack): 用流向 Sink 的概率直接做 Mask
        TNS = -torch.sum(negative_slacks * sink_probs) 
        
        # WNS (Worst Negative Slack): 提取真正的全局最差 Sink AT
        # 这里复用 LSE，把 sink_probs 作为权重，完美提取 WNS
        tree_max_at = smooth_max_lse(node_ats_tensor + gamma * torch.log(sink_probs + 1e-8), gamma=gamma)
        WNS = torch.clamp(tree_max_at - self.req_time, min=0.0)
        
        return WNS, TNS, expected_area, M_internal, P_c