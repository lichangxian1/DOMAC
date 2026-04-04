import torch
import torch.nn as nn
import torch.nn.functional as F
from .diff_sta import smooth_max_lse, diff_bilinear_interp

class DOMAC_CompressorTree(nn.Module):
    # 注意：接口中去掉了无用的 init_m_logits，新增了 routing_stages, total_virtual_nodes 和 init_mode
    def __init__(self, pp_cols, c_cols, fa_tensors, ha_tensors, c_types, req_time, 
                 routing_stages, total_virtual_nodes, init_mode='blank', device='cpu', init_p_logits=None):
        super(DOMAC_CompressorTree, self).__init__()
        self.device = device  # <--- [核心新增] 记住目标设备
        self.pp_cols = pp_cols
        self.c_cols = c_cols
        self.num_pp = len(pp_cols)
        self.num_c = len(c_cols)
        self.c_types = c_types
        self.req_time = req_time
        
        # 记录所有虚拟节点的列权重 (Column)，供最终 CPA 惩罚使用
        self.total_virtual_nodes = total_virtual_nodes
        self.virtual_node_cols = torch.zeros(self.total_virtual_nodes, dtype=torch.long, device=device)
        self.virtual_node_cols[:self.num_pp] = torch.tensor(pp_cols, device=device)
        self.virtual_node_cols[self.num_pp : self.num_pp+self.num_c] = torch.tensor(c_cols, device=device)
        self.virtual_node_cols[self.num_pp+self.num_c : self.num_pp+2*self.num_c] = torch.tensor([c+1 for c in c_cols], device=device)
        
        self.pin_names = ['A', 'B', 'CI']
        self.num_pins_per_c = len(self.pin_names)
        
        # 1. 预编译为 3D 张量的物理库
        self.fa_areas, self.fa_caps, self.fa_arcs = self._parse_tensors(fa_tensors)
        self.ha_areas, self.ha_caps, self.ha_arcs = self._parse_tensors(ha_tensors)
        self.num_fa_impls = len(fa_tensors)
        self.num_ha_impls = len(ha_tensors)
        self.max_impls = max(self.num_fa_impls, self.num_ha_impls)
        
        # 2. 物理实现选取器 P_c (保持全局映射)
        if init_p_logits is not None:
            self.p_logits = nn.Parameter(init_p_logits.clone().to(device))
        else:
            self.p_logits = nn.Parameter(torch.zeros(self.num_c, self.max_impls, device=device))
            
        p_mask = torch.zeros(self.num_c, self.max_impls, device=device)
        for j, c_type in enumerate(self.c_types):
            if c_type == 'FA':
                p_mask[j, self.num_fa_impls:] = float('-inf')
            else:
                p_mask[j, self.num_ha_impls:] = float('-inf')
        self.register_buffer('p_mask', p_mask)
        
        # =========================================================================
        # 🚀 [架构重构] 注册局部级联矩阵群 (Local Matrix ParameterList)
        # =========================================================================
        self.local_m_logits = nn.ParameterList()
        self.local_meta = []
        
        for stage_meta in routing_stages:
            for meta in stage_meta:
                num_in = len(meta['in_wires'])
                num_pins = len(meta['pin_global_indices'])
                num_bypass = len(meta['out_bypass_ids'])
                num_out_cols = num_pins + num_bypass
                
                # 记录 Bypass 虚拟线的位权
                col = meta['col']
                for b_id in meta['out_bypass_ids']:
                    self.virtual_node_cols[b_id] = col
                    
                if num_in > 0 and num_out_cols > 0:
                    # [极简热启动] 如果是 Dadda 模式，直接用单位矩阵主对角线硬连线！
                    if init_mode == 'dadda' and num_in == num_out_cols:
                        m_ij = nn.Parameter(torch.eye(num_in, num_out_cols, device=device) * 10.0)
                    else:
                        m_ij = nn.Parameter(torch.randn(num_in, num_out_cols, device=device) * 0.01)
                        
                    self.local_m_logits.append(m_ij)
                    
                    # 存储元数据以供前向传播查表
                    self.local_meta.append({
                        'in_wires': meta['in_wires'],
                        'fa_ids': meta['fa_ids'],
                        'ha_ids': meta['ha_ids'],
                        'out_bypass_ids': meta['out_bypass_ids'],
                        'pin_global_indices': meta['pin_global_indices'],
                        'matrix_idx': len(self.local_m_logits) - 1,
                        'num_pins': num_pins,
                        'num_bypass': num_bypass
                    })
        # ========== [请在 __init__ 的最后补充这几行] ==========
        active_pin_mask = torch.zeros(self.num_c * self.num_pins_per_c, device=device)
        for j, c_type in enumerate(self.c_types):
            if c_type == 'FA': active_pin_mask[j*3 : j*3+3] = 1.0
            else: active_pin_mask[j*3 : j*3+2] = 1.0
        self.register_buffer('active_pin_mask', active_pin_mask)

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
            # ==========================================================
            # 1. 严格面积审查 (拒绝默认值 1.0)
            # ==========================================================
        for ct_idx, ct in enumerate(tensors):
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
        
        # 1. 提前计算所有物理压缩器的输入引脚期望电容与面积
        global_pin_caps = torch.zeros(self.num_c * 3, device=self.device)

        expected_area = 0.0

        for j, c_type in enumerate(self.c_types):
            is_fa = (c_type == 'FA')
            lib_areas = self.fa_areas if is_fa else self.ha_areas
            lib_caps = self.fa_caps if is_fa else self.ha_caps

            p_j = P_c[j, :self.num_fa_impls] if is_fa else P_c[j, :self.num_ha_impls]
            
            expected_area = expected_area + torch.sum(p_j * lib_areas)
            global_pin_caps[j*3 : j*3+3] = p_j @ lib_caps

        # 2. 从后向前计算反向导线电容负载 (Backward Load Propagation)
        # 这完美解决了局部矩阵架构下跨级连线的负载溯源问题
        node_loads = torch.zeros(self.total_virtual_nodes, device=self.device)
        # ================= [核心物理修复：引入线负载模型 WLM] =================
        # 假设 TSMC 28nm 下，一根跨 Cell 互连线的平均寄生电容约为 0.003 pF (3 fF)
        # 你可以根据实际库的情况微调这个值
        WIRE_CAP_PER_NET = 0.000 
        
        local_M_probs = [F.softmax(m / tau, dim=1) for m in self.local_m_logits]
        
        for meta in reversed(self.local_meta):
            M_ij = local_M_probs[meta['matrix_idx']]
            target_caps = torch.zeros(meta['num_pins'] + meta['num_bypass'], device=self.device)
            
            if meta['num_pins'] > 0:
                target_caps[:meta['num_pins']] = global_pin_caps[meta['pin_global_indices']]
            if meta['num_bypass'] > 0:
                target_caps[meta['num_pins']:] = node_loads[meta['out_bypass_ids']]
                
            in_wire_loads = M_ij @ (target_caps + WIRE_CAP_PER_NET)
            for idx, w in enumerate(meta['in_wires']):
                node_loads[w] += in_wire_loads[idx]

        # 3. 前向波前推进 (Forward Wavefront Propagation)
        wire_ats = torch.zeros(self.total_virtual_nodes, device=self.device)
        wire_slews = torch.zeros(self.total_virtual_nodes, device=self.device)
        
        wire_ats[:self.num_pp] = pp_at
        wire_slews[:self.num_pp] = pp_slew
        
        expected_glitch = 0.0
        global_pin_ats_probe = torch.zeros(self.num_c * 3, device=self.device)

        # 严格按级逐列遍历，彻底封死越级通道
        for meta in self.local_meta:
            M_ij = local_M_probs[meta['matrix_idx']]
            in_w = meta['in_wires']
            
            in_ats = wire_ats[in_w]
            in_slews = wire_slews[in_w]
            
            # 张量广播推流
            routed_ats = in_ats @ M_ij
            routed_slews = in_slews @ M_ij
            
            num_pins = meta['num_pins']
            num_bypass = meta['num_bypass']
            
            # 3.1 处理 Bypass 透传线
            if num_bypass > 0:
                out_b_ids = meta['out_bypass_ids']
                wire_ats[out_b_ids] = routed_ats[num_pins:]
                wire_slews[out_b_ids] = routed_slews[num_pins:]
                
            # 3.2 处理压缩器物理计算
            pin_ats = routed_ats[:num_pins]
            pin_slews = routed_slews[:num_pins]
            
            if num_pins > 0:
                global_pin_ats_probe[meta['pin_global_indices']] = pin_ats
            
            pin_offset = 0
            
            # 全加器
            for c_id in meta['fa_ids']:
                p_j = P_c[c_id, :self.num_fa_impls]
                c_ats = pin_ats[pin_offset : pin_offset+3]
                c_slews = pin_slews[pin_offset : pin_offset+3]
                pin_offset += 3
                
                # 💥 极其纯粹的 Glitch Variance
                mean_at = torch.mean(c_ats)
                expected_glitch = expected_glitch + torch.sqrt(torch.sum((c_ats - mean_at)**2) + 1e-8)
                
                s_load = node_loads[self.num_pp + c_id]
                co_load = node_loads[self.num_pp + self.num_c + c_id]
                
                s_paths_at, s_paths_slew = [], []
                co_paths_at, co_paths_slew = [], []
                
                for p_idx, p_name in enumerate(['A', 'B', 'CI']):
                    arc_S = self.fa_arcs['S'][p_name]
                    d_S = diff_bilinear_interp(c_slews[p_idx], s_load, arc_S['index_1_slew'], arc_S['index_2_load'], arc_S['delay_lut'])
                    sl_S = diff_bilinear_interp(c_slews[p_idx], s_load, arc_S['index_1_slew'], arc_S['index_2_load'], arc_S['slew_lut'])
                    s_paths_at.append(c_ats[p_idx] + torch.sum(p_j * d_S))
                    s_paths_slew.append(torch.sum(p_j * sl_S))
                    
                    arc_CO = self.fa_arcs['CO'][p_name]
                    d_CO = diff_bilinear_interp(c_slews[p_idx], co_load, arc_CO['index_1_slew'], arc_CO['index_2_load'], arc_CO['delay_lut'])
                    sl_CO = diff_bilinear_interp(c_slews[p_idx], co_load, arc_CO['index_1_slew'], arc_CO['index_2_load'], arc_CO['slew_lut'])
                    co_paths_at.append(c_ats[p_idx] + torch.sum(p_j * d_CO))
                    co_paths_slew.append(torch.sum(p_j * sl_CO))
                    
                wire_ats[self.num_pp + c_id] = smooth_max_lse(s_paths_at, gamma=0.01)
                wire_slews[self.num_pp + c_id] = smooth_max_lse(s_paths_slew, gamma=0.01)
                wire_ats[self.num_pp + self.num_c + c_id] = smooth_max_lse(co_paths_at, gamma=0.01)
                wire_slews[self.num_pp + self.num_c + c_id] = smooth_max_lse(co_paths_slew, gamma=0.01)

            # 半加器
            for c_id in meta['ha_ids']:
                p_j = P_c[c_id, :self.num_ha_impls]
                c_ats = pin_ats[pin_offset : pin_offset+2]
                c_slews = pin_slews[pin_offset : pin_offset+2]
                pin_offset += 2
                
                mean_at = torch.mean(c_ats)
                expected_glitch = expected_glitch + torch.sqrt(torch.sum((c_ats - mean_at)**2) + 1e-8)
                
                s_load = node_loads[self.num_pp + c_id]
                co_load = node_loads[self.num_pp + self.num_c + c_id]
                
                s_paths_at, s_paths_slew = [], []
                co_paths_at, co_paths_slew = [], []
                
                for p_idx, p_name in enumerate(['A', 'B']):
                    arc_S = self.ha_arcs['S'][p_name]
                    d_S = diff_bilinear_interp(c_slews[p_idx], s_load, arc_S['index_1_slew'], arc_S['index_2_load'], arc_S['delay_lut'])
                    sl_S = diff_bilinear_interp(c_slews[p_idx], s_load, arc_S['index_1_slew'], arc_S['index_2_load'], arc_S['slew_lut'])
                    s_paths_at.append(c_ats[p_idx] + torch.sum(p_j * d_S))
                    s_paths_slew.append(torch.sum(p_j * sl_S))
                    
                    arc_CO = self.ha_arcs['CO'][p_name]
                    d_CO = diff_bilinear_interp(c_slews[p_idx], co_load, arc_CO['index_1_slew'], arc_CO['index_2_load'], arc_CO['delay_lut'])
                    sl_CO = diff_bilinear_interp(c_slews[p_idx], co_load, arc_CO['index_1_slew'], arc_CO['index_2_load'], arc_CO['slew_lut'])
                    co_paths_at.append(c_ats[p_idx] + torch.sum(p_j * d_CO))
                    co_paths_slew.append(torch.sum(p_j * sl_CO))
                    
                wire_ats[self.num_pp + c_id] = smooth_max_lse(s_paths_at, gamma=0.01)
                wire_slews[self.num_pp + c_id] = smooth_max_lse(s_paths_slew, gamma=0.01)
                wire_ats[self.num_pp + self.num_c + c_id] = smooth_max_lse(co_paths_at, gamma=0.01)
                wire_slews[self.num_pp + self.num_c + c_id] = smooth_max_lse(co_paths_slew, gamma=0.01)

        # 4. CPA (Sink) 时序重建与惩罚
        # 智能动态抓取：任何没有作为后续阶段 in_wires 被消耗掉的节点，必然全部流向 CPA
        all_in_wires = set()
        for meta in self.local_meta:
            all_in_wires.update(meta['in_wires'])
            
        sink_wires = [w for w in range(self.total_virtual_nodes) if w not in all_in_wires]
        sink_ats = wire_ats[sink_wires]
        sink_cols = self.virtual_node_cols[sink_wires]
        
        max_col = torch.max(self.virtual_node_cols)
        distance_to_msb = max_col - sink_cols.float()
        
        CPA_BIT_DELAY_RCA = 0.040 
        CPA_BASE_DELAY_RCA = 0.090 
        cpa_latency = CPA_BASE_DELAY_RCA + distance_to_msb * CPA_BIT_DELAY_RCA
        
        effective_ats = sink_ats + cpa_latency
        slacks = self.req_time - effective_ats
        # =========================================================================
        
        negative_slacks = torch.clamp(slacks, max=0.0)

        WNS = smooth_max_lse(-negative_slacks, gamma=0.01) 
        TNS = torch.sum(-negative_slacks)
        
        # ================= [新增：探针埋点] =================
        # 将当前周期的引脚期望AT和节点真实AT暂存，供训练探针解剖
        self._probe_pin_ats = global_pin_ats_probe.detach()
        self._probe_node_ats = wire_ats.detach()
        
        # 返回包含了所有局部矩阵的列表，供 objectives 和 legalizer 使用
        return WNS, TNS, expected_area, expected_glitch, local_M_probs, P_c