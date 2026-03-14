import torch
import torch.nn as nn
import torch.nn.functional as F
from .diff_sta import smooth_max_lse, diff_bilinear_interp

def prob_smooth_max_lse(probs, values, gamma=0.01):
    """
    [DOMAC 黑科技算子]: 概率加权平滑最大值
    不仅能平滑提取最大值，还能利用概率权重直接“物理湮灭”未连接的幽灵路径。
    """
    weighted_exp = probs * torch.exp(values / gamma)
    # 加上 1e-20 防止全 0 概率下 log(0) 导致数值崩溃
    return gamma * torch.log(torch.sum(weighted_exp) + 1e-20)


class DOMAC_CompressorTree(nn.Module):
    def __init__(self, pp_cols, c_cols, cell_tensors, req_time):
        super(DOMAC_CompressorTree, self).__init__()
        
        self.pp_cols = pp_cols
        self.c_cols = c_cols
        self.num_pp = len(pp_cols)
        self.num_c = len(c_cols)
        self.node_cols = list(self.pp_cols) + list(self.c_cols) 
        
        self.num_impls = len(cell_tensors) 
        self.req_time = req_time
        
        # ================= [架构升级]: 拥抱物理引脚 (Pin-Level) =================
        self.pin_names = ['A', 'B', 'CI']  # 严格对齐 NLDM 库的引脚定义
        self.num_pins_per_c = len(self.pin_names)
        
        self.cell_arcs = []
        self.pin_caps = []
        self.cell_areas = []
        
        for cell_idx, ct in enumerate(cell_tensors):
            # 1. 提取面积
            self.cell_areas.append(ct.get('cell_area', 1.0))
            
            # 2. 提取精确的引脚电容 [A, B, CI]
            p_caps = []
            for p_name in self.pin_names:
                # 如果这个单元没有这个引脚(比如 HA 没有 CI)，给一个极小的默认寄生电容
                p_caps.append(ct.get('pin_cap', {}).get(p_name, 0.001))
            self.pin_caps.append(p_caps)
            
            # 3. 提取精确的时序弧 (A->S, B->S, CI->S)
            arcs = {}
            for in_p in self.pin_names:
                # 尝试嗅探到 'S' 输出的时序弧
                arc_data = ct.get('S', {}).get(in_p)
                if arc_data is not None:
                    arcs[in_p] = arc_data
            self.cell_arcs.append(arcs)
            
        self.area_lib = torch.tensor(self.cell_areas, dtype=torch.float32)
        self.pin_caps_lib = torch.tensor(self.pin_caps, dtype=torch.float32) # Shape: [num_impls, 3]
        
        print(f"[Core] 物理引脚时序网络构建完毕。每台压缩器暴露出 {self.num_pins_per_c} 个引脚靶点。")

        # ================= 张量参数与掩码定义 =================
        self.p_logits = nn.Parameter(torch.zeros(self.num_c, self.num_impls))
        
        total_nodes = self.num_pp + self.num_c
        total_target_pins = self.num_c * self.num_pins_per_c  # 真正连接的是具体的引脚！
        
        # M 矩阵的列数：所有压缩器的所有引脚 + 1个 Sink 外部输出端
        self.m_logits = nn.Parameter(torch.zeros(total_nodes, total_target_pins + 1))
        
        # DAG Mask 双重物理封印 (防环路 + 防跨列)
        self.dag_mask = torch.full((total_nodes, total_target_pins + 1), float('-inf'))
        for i in range(total_nodes):
            for j in range(self.num_c):
                is_downstream = (i < j + self.num_pp)
                is_same_column = (self.node_cols[i] == self.c_cols[j])
                
                if is_downstream and is_same_column:
                    # 允许信号连接到这台压缩器的 A, B, CI 三个具体引脚上
                    for p_idx in range(self.num_pins_per_c):
                        self.dag_mask[i, j * self.num_pins_per_c + p_idx] = 0.0
                        
            # 外部输出通道 (Sink) 永远畅通
            self.dag_mask[i, total_target_pins] = 0.0 

    def forward(self, pp_at, pp_slew):
        P_c = F.softmax(self.p_logits, dim=-1) # [num_c, num_impls]
        M_full = F.softmax(self.m_logits + self.dag_mask, dim=-1) # [total_nodes, num_c * 3 + 1]
        M_internal = M_full[:, :-1] # [total_nodes, num_c * 3]
        
        expected_area = torch.sum(P_c @ self.area_lib)
        
        # 1. 节点电容精确推演 (基于选择概率与各引脚的真实电容)
        # expected_pin_caps: [num_c, 3] -> 展开为平铺的一维靶点
        expected_pin_caps = P_c @ self.pin_caps_lib 
        flat_expected_pin_caps = expected_pin_caps.view(-1) 
        
        # 精确计算每个节点背负的电容负载
        loads = M_internal @ flat_expected_pin_caps 
        
        node_ats = list(pp_at)
        node_slews = list(pp_slew)
        
        # 2. 时序传播引擎 (Pin-Level)
        for j in range(self.num_c):
            pin_ats = []
            pin_slews = []
            pin_prob_sums = [] # 记录这个引脚真实接到了多少信号权重
            
            # # --- a. 汇总到达每个【输入引脚】的外部信号 ---
            # for p_idx in range(self.num_pins_per_c):
            #     in_probs = M_internal[:, j * self.num_pins_per_c + p_idx]
                
            #     pin_prob_sums.append(torch.sum(in_probs))
            #     pin_ats.append(prob_smooth_max_lse(in_probs, torch.stack(node_ats)))
            #     pin_slews.append(prob_smooth_max_lse(in_probs, torch.stack(node_slews)))
                
            # --- a. 汇总到达每个【输入引脚】的外部信号 ---
            for p_idx in range(self.num_pins_per_c):
                # in_probs 包含了全局所有 14 个节点的连接概率
                in_probs_full = M_internal[:, j * self.num_pins_per_c + p_idx]
                
                # [核心修复]: 动态截断概率视图！
                # 当前时序图里算出了多少个节点的 AT，我们就只取前多少个节点的概率。
                # 依据 dag_mask，被截掉的后面那部分的概率严格为 0，所以绝对安全。
                current_nodes_cnt = len(node_ats)
                active_in_probs = in_probs_full[:current_nodes_cnt]
                
                pin_prob_sums.append(torch.sum(active_in_probs))
                
                # 现在的 active_in_probs 和 node_ats 长度完美对齐，随前向传播动态生长
                pin_ats.append(prob_smooth_max_lse(active_in_probs, torch.stack(node_ats)))
                pin_slews.append(prob_smooth_max_lse(active_in_probs, torch.stack(node_slews)))
            
            expected_cell_at = 0.0
            expected_cell_slew = 0.0
            
            node_j_idx = self.num_pp + j
            current_load = loads[node_j_idx]
                
            # --- b. 查表计算单元【内部】从各个引脚到输出的路径延迟 ---
            for impl_idx in range(self.num_impls):
                prob_impl = P_c[j, impl_idx]
                arcs = self.cell_arcs[impl_idx]
                
                impl_paths_at = []
                impl_paths_slew = []
                impl_paths_probs = [] # 用于在 Cell 内部压制不存在的时序弧或没接线的引脚
                
                for p_idx, p_name in enumerate(self.pin_names):
                    if p_name in arcs: # 确认该实现是否有这条物理时序弧 (例如 HA 就没有 CI->S)
                        arc = arcs[p_name]
                        delay = diff_bilinear_interp(pin_slews[p_idx], current_load, arc['index_1_slew'], arc['index_2_load'], arc['delay_lut'])
                        slew = diff_bilinear_interp(pin_slews[p_idx], current_load, arc['index_1_slew'], arc['index_2_load'], arc['slew_lut'])
                        
                        impl_paths_at.append(pin_ats[p_idx] + delay)
                        impl_paths_slew.append(slew)
                        impl_paths_probs.append(pin_prob_sums[p_idx])
                        
                # 再次使用 P-LSE！如果没有信号连到 CI 引脚，CI->S 的内部时序也不会参与 Max 竞争！
                if impl_paths_at:
                    at_out_impl = prob_smooth_max_lse(torch.stack(impl_paths_probs), torch.stack(impl_paths_at))
                    slew_out_impl = prob_smooth_max_lse(torch.stack(impl_paths_probs), torch.stack(impl_paths_slew))
                else:
                    at_out_impl = torch.tensor(0.0)
                    slew_out_impl = torch.tensor(0.0)
                    
                expected_cell_at = expected_cell_at + prob_impl * at_out_impl
                expected_cell_slew = expected_cell_slew + prob_impl * slew_out_impl
                
            node_ats.append(expected_cell_at)
            node_slews.append(expected_cell_slew)
            
        # 3. 终点评估
        sink_probs = M_full[:, -1]
        all_ats_tensor = torch.stack(node_ats)
        
        slacks = self.req_time - all_ats_tensor
        negative_slacks = torch.clamp(slacks, max=0.0)
        
        active_neg_slacks = -negative_slacks * sink_probs
        WNS = smooth_max_lse(active_neg_slacks, gamma=0.01) 
        TNS = torch.sum(active_neg_slacks)
        
        # 返回 M_internal，它的列数为 num_c * 3，交给目标函数约束
        return WNS, TNS, expected_area, M_internal, P_c