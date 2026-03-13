import torch
import torch.nn as nn
import torch.nn.functional as F
# from .diff_sta import smooth_max_lse, compute_expected_timing
from .diff_sta import smooth_max_lse, diff_bilinear_interp

class DOMAC_CompressorTree(nn.Module):
    def __init__(self, num_pp, num_compressors, cell_tensors, req_time):
        super(DOMAC_CompressorTree, self).__init__()
        self.num_pp = num_pp
        self.num_c = num_compressors
        self.num_impls = len(cell_tensors) 
        self.cell_tensors = cell_tensors
        self.req_time = req_time
        
        # === 动态提取真实数据 ===
        extracted_areas = []
        extracted_caps = []
        
        for ct in cell_tensors:
            # 提取面积
            area_val = ct.get('cell_area', 1.0) # 如果没抓到，给个默认值防崩
            extracted_areas.append(area_val)
            
            # 提取输入引脚的平均电容 (DOMAC为了简化拓扑计算，通常取各输入引脚电容的平均值或最大值作为节点等效电容)
            pin_caps = ct.get('pin_cap', {})
            if pin_caps:
                avg_cap = sum(pin_caps.values()) / len(pin_caps)
            else:
                avg_cap = 0.001 # 兜底假数据
            extracted_caps.append(avg_cap)
            
        # 彻底转化为带着真实 TSMC 28nm 物理基因的 PyTorch 张量
        self.area_lib = torch.tensor(extracted_areas, dtype=torch.float32)
        self.cap_in_lib = torch.tensor(extracted_caps, dtype=torch.float32)
        
        print(f"[Core] 动态加载物理参数完毕! Area库: {self.area_lib.tolist()}, Cap库: {self.cap_in_lib.tolist()}")
        
        # # [动态解耦]: 自动嗅探每个 Cell 可用的时序弧 (Timing Arcs)
        # self.available_arcs = []
        # for ct in cell_tensors:
        #     valid_arcs = []
        #     for out_p, in_dict in ct.items():
        #         # 避开我们刚刚注入的面积和电容 key
        #         if out_p in ['cell_area', 'pin_cap']: 
        #             continue
        #         # 记录所有真实的 (输出引脚, 输入引脚) 组合
        #         for in_p in in_dict.keys():
        #             valid_arcs.append((out_p, in_p))
                    
        #     if not valid_arcs:
        #         raise ValueError("[致命错误] 物理单元中未找到任何合法的时序弧！")
        #     self.available_arcs.append(valid_arcs)
            
        # print(f"[Core] 动态时序弧嗅探完毕。FA 探测到 {len(self.available_arcs[0])} 条弧，HA 探测到 {len(self.available_arcs[1])} 条弧。")

        # [终极物理对齐]: 将每个单元内部所有的时序弧融合为“单一最差情况 (Worst-case Envelope)”
        self.cell_worst_luts = []
        
        for cell_idx, ct in enumerate(cell_tensors):
            all_delays = []
            all_slews = []
            ref_idx1 = None
            ref_idx2 = None
            
            for out_p, in_dict in ct.items():
                if out_p in ['cell_area', 'pin_cap']: 
                    continue
                for in_p, arc_data in in_dict.items():
                    all_delays.append(arc_data['delay_lut'])
                    all_slews.append(arc_data['slew_lut'])
                    if ref_idx1 is None:
                        # 假设同一个 Cell 内所有时序弧共用同一个坐标轴
                        ref_idx1 = arc_data['index_1_slew']
                        ref_idx2 = arc_data['index_2_load']
            
            if not all_delays:
                raise ValueError(f"[致命错误] 单元 {cell_idx} 中没有发现合法的时序弧！")
            
            # 在张量层面执行降维打击：将 6 条/4 条弧叠在一起，取每一个格子里的最大值！
            worst_delay_lut = torch.max(torch.stack(all_delays), dim=0)[0]
            worst_slew_lut = torch.max(torch.stack(all_slews), dim=0)[0]
            
            # # ================= [验证探针：X光级透视] =================
            # if cell_idx == 0:  # 我们只拿 FA (全加器) 开刀验证
            #     print("\n" + "="*50)
            #     print("[验证探针] FA 内部 6 条时序弧在 7x7 LUT 矩阵中心点 (如 Slew_Idx=3, Load_Idx=3) 的真实延迟剥离:")
            #     for k, arc_delay in enumerate(all_delays):
            #         print(f"  -> 第 {k+1} 条时序弧 (Delay): {arc_delay[3][3].item():.6f} ns")
                
            #     print(f"  => [融合结果] Worst-case 延迟: {worst_delay_lut[3][3].item():.6f} ns")
                
            #     # 物理红线断言：融合后的矩阵，在任何一个点上，都必须 >= 所有的单条弧！
            #     for k, arc_delay in enumerate(all_delays):
            #         assert torch.all(worst_delay_lut >= arc_delay), f"致命错误！融合矩阵未能包络第 {k+1} 条时序弧！"
            #     print("[验证探针] 严格数学断言通过：Worst-case 张量面已完美覆盖所有底层物理时序弧！ ✓")
            #     print("="*50 + "\n")
            # # =========================================================
                
            self.cell_worst_luts.append({
                'index_1_slew': ref_idx1,
                'index_2_load': ref_idx2,
                'delay_lut': worst_delay_lut,
                'slew_lut': worst_slew_lut
            })
            print(f"[Core] 单元 {cell_idx} 成功融合 {len(all_delays)} 条弧，生成全局 Worst-case NLDM 张量面。")
        # =========================================================================
            
        self.p_logits = nn.Parameter(torch.zeros(self.num_c, self.num_impls))
        
        total_nodes = self.num_pp + self.num_c
        
        # [修改点 1]: M 矩阵增加一列，代表“连接到外部输出引脚 (Sink)”
        self.m_logits = nn.Parameter(torch.zeros(total_nodes, self.num_c + 1))
        
        # [修改点 2]: Mask 矩阵也增加一列，且确保 Sink 列对所有节点永远合法 (0.0)
        self.dag_mask = torch.full((total_nodes, self.num_c + 1), float('-inf'))
        for i in range(total_nodes):
            for j in range(self.num_c):
                if i < j + self.num_pp:  
                    self.dag_mask[i, j] = 0.0
            # 外部引脚通道永远开启
            self.dag_mask[i, self.num_c] = 0.0 

    # def query_timing_arc(self, cell_data, out_pin, in_pin, slew, load):
    #     """
    #     精确查询某一个单元的具体时序弧，并返回连续可导的延迟和转换时间
    #     """
    #     arc_data = cell_data[out_pin][in_pin]
        
    #     delay = diff_bilinear_interp(
    #         slew, load, 
    #         arc_data['index_1_slew'], arc_data['index_2_load'], arc_data['delay_lut']
    #     )
        
    #     out_slew = diff_bilinear_interp(
    #         slew, load, 
    #         arc_data['index_1_slew'], arc_data['index_2_load'], arc_data['slew_lut']
    #     )
    #     return delay, out_slew

    def query_cell_worst_timing(self, cell_idx, slew, load):
        """
        直接查询融合后的 Cell-level 最差时序包络面
        """
        lut_data = self.cell_worst_luts[cell_idx]
        
        delay = diff_bilinear_interp(
            slew, load, 
            lut_data['index_1_slew'], lut_data['index_2_load'], lut_data['delay_lut']
        )
        out_slew = diff_bilinear_interp(
            slew, load, 
            lut_data['index_1_slew'], lut_data['index_2_load'], lut_data['slew_lut']
        )
        return delay, out_slew
    
    def forward(self, pp_at, pp_slew):
        P_c = F.softmax(self.p_logits, dim=-1)
        
        # 激活出包含 Sink 的全局分布
        M_full = F.softmax(self.m_logits + self.dag_mask, dim=-1)
        
        # [修改点 3]: 我们剥离出纯内部连接矩阵 (剔除最后一列 Sink)，用于计算内部负载和向下传递
        M_internal = M_full[:, :-1] 
        
        expected_area = torch.sum(P_c @ self.area_lib)
        
        expected_node_caps = P_c @ self.cap_in_lib 
        
        # 使用纯内部矩阵计算内部节点的电容负载
        loads = M_internal @ expected_node_caps 
        
        node_ats = list(pp_at)
        node_slews = list(pp_slew)
        
        for j in range(self.num_c):
            # 内部连接概率
            in_probs = M_internal[:, j] 
            arrival_paths = []
            
            # for i in range(len(node_ats)):
            #     prob_ij = in_probs[i]
            #     delay_ij, out_slew_ij = compute_expected_timing(
            #         P_c[j], self.cell_tensors, 
            #         in_pin='A', out_pin='S', 
            #         slew=node_slews[i], load=loads[i]
            #     )
            #     path_at = node_ats[i] + delay_ij * prob_ij
            #     arrival_paths.append(path_at)
            
            # for i in range(len(node_ats)):
            #     prob_ij = in_probs[i]
                
            #     # ================= 动态时序弧查表 (Data-Driven) =================
            #     # 分别获取 FA (index 0) 和 HA (index 1) 嗅探到的第一条合法时序弧
            #     arc_fa = self.available_arcs[0][0]  # 例如 ('S', 'A') 
            #     arc_ha = self.available_arcs[1][0]  # 例如 ('S', 'A') 
                
            #     # 查表得到绝对物理延迟 (调用底层 C++ 算子)
            #     delay_fa, slew_fa = self.query_timing_arc(
            #         self.cell_tensors[0], arc_fa[0], arc_fa[1], node_slews[i], loads[i]
            #     )
            #     delay_ha, slew_ha = self.query_timing_arc(
            #         self.cell_tensors[1], arc_ha[0], arc_ha[1], node_slews[i], loads[i]
            #     )
                
            #     # ================= 计算“量子叠加态”下的数学期望 =================
            #     # 期望延迟 = FA概率 * FA延迟 + HA概率 * HA延迟
            #     delay_ij = P_c[j][0] * delay_fa + P_c[j][1] * delay_ha
            #     out_slew_ij = P_c[j][0] * slew_fa + P_c[j][1] * slew_ha
                
            #     # 累加路径到达时间
            #     path_at = node_ats[i] + delay_ij * prob_ij
            #     arrival_paths.append(path_at)

            for i in range(len(node_ats)):
                prob_ij = in_probs[i]
                
                # ================= 动态时序查表 (Worst-case Envelope) =================
                # 0 代表 FA，1 代表 HA
                delay_fa, slew_fa = self.query_cell_worst_timing(0, node_slews[i], loads[i])
                delay_ha, slew_ha = self.query_cell_worst_timing(1, node_slews[i], loads[i])
                
                # ================= 计算“量子叠加态”下的数学期望 =================
                delay_ij = P_c[j][0] * delay_fa + P_c[j][1] * delay_ha
                out_slew_ij = P_c[j][0] * slew_fa + P_c[j][1] * slew_ha
                
                path_at = node_ats[i] + delay_ij * prob_ij
                arrival_paths.append(path_at)

            at_j = smooth_max_lse(arrival_paths, gamma=0.01)
            slew_j = out_slew_ij 
            
            node_ats.append(at_j)
            node_slews.append(slew_j)
            
        endpoints_at = torch.stack(node_ats[-self.num_pp:]) 
        slacks = self.req_time - endpoints_at
        negative_slacks = torch.clamp(slacks, max=0.0)
        WNS = -torch.min(negative_slacks)
        TNS = -torch.sum(negative_slacks)
        
        # [修改点 4]: 返回 M_internal 给 Loss，因为 L_BM 和 L_D 只需要约束内部物理管脚
        return WNS, TNS, expected_area, M_internal, P_c