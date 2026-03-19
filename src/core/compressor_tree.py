import torch
import torch.nn as nn
import torch.nn.functional as F
from .diff_sta import smooth_max_lse, diff_bilinear_interp

class DOMAC_CompressorTree(nn.Module):
    # 1. 在初始化参数中加入 device
    def __init__(self, pp_cols, c_cols, fa_tensors, ha_tensors, c_types, req_time, device='cpu'):
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
        self.p_logits = nn.Parameter(torch.zeros(self.num_c, self.max_impls))
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
        
        total_target_pins = self.num_c * self.num_pins_per_c 
        self.m_logits = nn.Parameter(torch.zeros(total_nodes, total_target_pins + 1))
        
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

    def forward(self, pp_at, pp_slew):
        P_c = F.softmax(self.p_logits + self.p_mask, dim=-1) 
        M_full = F.softmax(self.m_logits + self.dag_mask, dim=-1) 
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
        loads = M_internal @ flat_expected_pin_caps 
        
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
        negative_slacks = torch.clamp(slacks, max=0.0)
        
        WNS = smooth_max_lse(-negative_slacks, gamma=0.01) 
        TNS = torch.sum(-negative_slacks)
        
        return WNS, TNS, expected_area, M_internal, P_c