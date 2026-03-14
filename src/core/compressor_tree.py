import torch
import torch.nn as nn
import torch.nn.functional as F
from .diff_sta import smooth_max_lse, diff_bilinear_interp

class DOMAC_CompressorTree(nn.Module):
    def __init__(self, pp_cols, c_cols, cell_tensors, req_time):
        super(DOMAC_CompressorTree, self).__init__()
        
        self.pp_cols = pp_cols
        self.c_cols = c_cols
        self.num_pp = len(pp_cols)
        self.num_c = len(c_cols)
        
        # [Dr. Gemini 核心修正 1]: 物理节点扩容！每个压缩器有 S 和 CO 两个输出节点
        self.s_cols = c_cols
        self.co_cols = [col + 1 for col in c_cols] # 进位必定去往下一列 (权重视为 2^(i+1))
        
        # 总节点数 = PP数量 + S节点数量 + CO节点数量
        self.node_cols = list(self.pp_cols) + list(self.s_cols) + list(self.co_cols)
        total_nodes = len(self.node_cols)
        
        self.num_impls = len(cell_tensors) 
        self.req_time = req_time
        
        self.pin_names = ['A', 'B', 'CI']
        self.num_pins_per_c = len(self.pin_names)
        
        self.cell_arcs = []
        self.pin_caps = []
        self.cell_areas = []
        
        for cell_idx, ct in enumerate(cell_tensors):
            self.cell_areas.append(ct.get('cell_area', 1.0))
            
            p_caps = []
            for p_name in self.pin_names:
                p_caps.append(ct.get('pin_cap', {}).get(p_name, 0.001))
            self.pin_caps.append(p_caps)
            
            arcs = {'S': {}, 'CO': {}}
            for in_p in self.pin_names:
                # [Dr. Gemini 核心修正 1]: 同时提取 S 和 CO 的时序弧
                arc_s = ct.get('S', {}).get(in_p)
                arc_co = ct.get('CO', {}).get(in_p)
                if arc_s is not None: arcs['S'][in_p] = arc_s
                if arc_co is not None: arcs['CO'][in_p] = arc_co
            self.cell_arcs.append(arcs)
            
        self.area_lib = torch.tensor(self.cell_areas, dtype=torch.float32)
        self.pin_caps_lib = torch.tensor(self.pin_caps, dtype=torch.float32)
        
        self.p_logits = nn.Parameter(torch.zeros(self.num_c, self.num_impls))
        
        total_target_pins = self.num_c * self.num_pins_per_c 
        self.m_logits = nn.Parameter(torch.zeros(total_nodes, total_target_pins + 1))
        
        # ================= [Dr. Gemini 核心修正 1]: 严格的 DAG 物理掩码 =================
        self.dag_mask = torch.full((total_nodes, total_target_pins + 1), float('-inf'))
        for i in range(total_nodes):
            for j in range(self.num_c):
                # 判断当前节点 i 是否在压缩器 j 之前 (防止组合逻辑环)
                if i < self.num_pp:
                    is_downstream = True # PP 永远在最上游
                elif i < self.num_pp + self.num_c:
                    is_downstream = (i - self.num_pp) < j # S 节点
                else:
                    is_downstream = (i - self.num_pp - self.num_c) < j # CO 节点

                # 严格的列对齐约束：信号只能连给同一列的压缩器引脚
                is_same_column = (self.node_cols[i] == self.c_cols[j])
                
                if is_downstream and is_same_column:
                    for p_idx in range(self.num_pins_per_c):
                        self.dag_mask[i, j * self.num_pins_per_c + p_idx] = 0.0
                        
            # 所有节点都允许连接到外部 Sink (作为最终加法器 CPA 的输入)
            self.dag_mask[i, total_target_pins] = 0.0 

    def forward(self, pp_at, pp_slew):
        P_c = F.softmax(self.p_logits, dim=-1) 
        M_full = F.softmax(self.m_logits + self.dag_mask, dim=-1) 
        M_internal = M_full[:, :-1] 
        
        expected_area = torch.sum(P_c @ self.area_lib)
        expected_pin_caps = P_c @ self.pin_caps_lib 
        flat_expected_pin_caps = expected_pin_caps.view(-1) 
        
        loads = M_internal @ flat_expected_pin_caps 
        
        node_ats = list(pp_at)
        node_slews = list(pp_slew)
        
        s_ats, s_slews = [], []
        co_ats, co_slews = [], []

        for j in range(self.num_c):
            pin_ats = []
            pin_slews = []
            
            for p_idx in range(self.num_pins_per_c):
                active_in_probs = M_internal[:len(node_ats), j * self.num_pins_per_c + p_idx]
                
                # [Dr. Gemini 核心修正 2]: 互连线延迟传播直接使用线性期望，绝不能用 LSE！
                # AT(v) = sum(P * AT(u))
                expected_pin_at = torch.sum(active_in_probs * torch.stack(node_ats))
                expected_pin_slew = torch.sum(active_in_probs * torch.stack(node_slews))
                
                pin_ats.append(expected_pin_at)
                pin_slews.append(expected_pin_slew)

            s_load = loads[self.num_pp + j]
            co_load = loads[self.num_pp + self.num_c + j]
            
            expected_s_at, expected_s_slew = 0.0, 0.0
            expected_co_at, expected_co_slew = 0.0, 0.0
            
            for impl_idx in range(self.num_impls):
                prob_impl = P_c[j, impl_idx]
                arcs = self.cell_arcs[impl_idx]
                
                # 计算 S 输出的最差时序 (使用 LSE 进行 Cell 内部引脚的 Max 竞争)
                s_paths_at, s_paths_slew = [], []
                for p_idx, p_name in enumerate(self.pin_names):
                    if p_name in arcs['S']:
                        arc = arcs['S'][p_name]
                        delay = diff_bilinear_interp(pin_slews[p_idx], s_load, arc['index_1_slew'], arc['index_2_load'], arc['delay_lut'])
                        slew = diff_bilinear_interp(pin_slews[p_idx], s_load, arc['index_1_slew'], arc['index_2_load'], arc['slew_lut'])
                        s_paths_at.append(pin_ats[p_idx] + delay)
                        s_paths_slew.append(slew)
                        
                if s_paths_at:
                    s_at_impl = smooth_max_lse(torch.stack(s_paths_at), gamma=0.01)
                    s_slew_impl = smooth_max_lse(torch.stack(s_paths_slew), gamma=0.01)
                else:
                    s_at_impl, s_slew_impl = torch.tensor(10.0), torch.tensor(10.0) # 幽灵路径惩罚
                    
                # 计算 CO 输出的最差时序
                co_paths_at, co_paths_slew = [], []
                for p_idx, p_name in enumerate(self.pin_names):
                    if p_name in arcs['CO']:
                        arc = arcs['CO'][p_name]
                        delay = diff_bilinear_interp(pin_slews[p_idx], co_load, arc['index_1_slew'], arc['index_2_load'], arc['delay_lut'])
                        slew = diff_bilinear_interp(pin_slews[p_idx], co_load, arc['index_1_slew'], arc['index_2_load'], arc['slew_lut'])
                        co_paths_at.append(pin_ats[p_idx] + delay)
                        co_paths_slew.append(slew)
                        
                if co_paths_at:
                    co_at_impl = smooth_max_lse(torch.stack(co_paths_at), gamma=0.01)
                    co_slew_impl = smooth_max_lse(torch.stack(co_paths_slew), gamma=0.01)
                else:
                    co_at_impl, co_slew_impl = torch.tensor(10.0), torch.tensor(10.0) # 幽灵路径惩罚
                    
                expected_s_at = expected_s_at + prob_impl * s_at_impl
                expected_s_slew = expected_s_slew + prob_impl * s_slew_impl
                expected_co_at = expected_co_at + prob_impl * co_at_impl
                expected_co_slew = expected_co_slew + prob_impl * co_slew_impl
                
            s_ats.append(expected_s_at)
            s_slews.append(expected_s_slew)
            co_ats.append(expected_co_at)
            co_slews.append(expected_co_slew)
            
            # 将新节点加入全局时序图 (先加S，后加CO，顺序与 node_cols 严格对应)
            if len(s_ats) == self.num_c:
                node_ats.extend(s_ats)
                node_slews.extend(s_slews)
                node_ats.extend(co_ats)
                node_slews.extend(co_slews)

        # [Dr. Gemini 核心修正 3]: 拒绝 Slack 概率稀释
        all_ats_tensor = torch.stack(node_ats)
        slacks = self.req_time - all_ats_tensor
        negative_slacks = torch.clamp(slacks, max=0.0)
        
        # 只有真实连接到 Sink 的节点，其负裕量才被计入 (乘以连接概率，如果概率为0则过滤掉该路径的违反)
        sink_probs = M_full[:, -1]
        active_neg_slacks = -negative_slacks * sink_probs
        
        WNS = smooth_max_lse(active_neg_slacks, gamma=0.01) 
        TNS = torch.sum(active_neg_slacks)
        
        return WNS, TNS, expected_area, M_internal, P_c