import torch
import torch.nn as nn
import torch.nn.functional as F
from .diff_sta import smooth_max_lse, diff_bilinear_interp

class DOMAC_CompressorTree(nn.Module):
    def __init__(self, pp_cols, c_cols, fa_tensors, ha_tensors, c_types, req_time):
        """
        DOMAC 压缩树核心引擎 (Dr. Gemini 终极重构版)
        :param fa_tensors: 全加器 (FA) 的所有可用物理实现列表
        :param ha_tensors: 半加器 (HA) 的所有可用物理实现列表
        :param c_types: 预先分配的压缩器类型列表，例如 ['FA', 'FA', 'HA']
        """
        super(DOMAC_CompressorTree, self).__init__()
        
        self.pp_cols = pp_cols
        self.c_cols = c_cols
        self.num_pp = len(pp_cols)
        self.num_c = len(c_cols)
        self.c_types = c_types
        
        # 物理节点扩容 (S 和 CO 独立输出)
        self.s_cols = c_cols
        self.co_cols = [col + 1 for col in c_cols] 
        self.node_cols = list(self.pp_cols) + list(self.s_cols) + list(self.co_cols)
        total_nodes = len(self.node_cols)
        
        # 异构物理库对齐
        self.num_fa_impls = len(fa_tensors) # FA的种类数
        self.num_ha_impls = len(ha_tensors) # HA的种类数
        self.max_impls = max(self.num_fa_impls, self.num_ha_impls) # 最大实现数，用于统一 Logits 维度
        self.req_time = req_time
        
        self.pin_names = ['A', 'B', 'CI']
        self.num_pins_per_c = len(self.pin_names)
        
        # 预解析 FA 和 HA 物理库
        self.fa_areas, self.fa_caps, self.fa_arcs = self._parse_tensors(fa_tensors)
        self.ha_areas, self.ha_caps, self.ha_arcs = self._parse_tensors(ha_tensors)
        
        # 统一维度的选择概率 Logits
        self.p_logits = nn.Parameter(torch.zeros(self.num_c, self.max_impls))
        
        # 构建物理实现掩码与引脚映射掩码
        p_mask = torch.zeros(self.num_c, self.max_impls)
        active_pin_mask = torch.zeros(self.num_c * self.num_pins_per_c)
        
        for j, c_type in enumerate(self.c_types):
            if c_type == 'FA':
                p_mask[j, self.num_fa_impls:] = float('-inf')
                active_pin_mask[j*3 : j*3+3] = 1.0 # FA 需要 3 个输入
            else: # HA
                p_mask[j, self.num_ha_impls:] = float('-inf')
                active_pin_mask[j*3 : j*3+2] = 1.0 # HA 只要 2 个输入
                active_pin_mask[j*3+2] = 0.0       # 封死 CI 引脚
                
        # 注册为 buffer，确保在 device 迁移时自动同步，但不参与梯度更新
        self.register_buffer('p_mask', p_mask)
        self.register_buffer('active_pin_mask', active_pin_mask)
        
        total_target_pins = self.num_c * self.num_pins_per_c 
        self.m_logits = nn.Parameter(torch.zeros(total_nodes, total_target_pins + 1))
        
        # 构建严格的 DAG 拓扑掩码
        dag_mask = torch.full((total_nodes, total_target_pins + 1), float('-inf'))
        for i in range(total_nodes):
            for j in range(self.num_c):
                # 防止组合逻辑环
                if i < self.num_pp:
                    is_downstream = True
                elif i < self.num_pp + self.num_c:
                    is_downstream = (i - self.num_pp) < j
                else:
                    is_downstream = (i - self.num_pp - self.num_c) < j

                is_same_column = (self.node_cols[i] == self.c_cols[j])
                
                if is_downstream and is_same_column:
                    for p_idx in range(self.num_pins_per_c):
                        # 只有存在这个引脚 (active_pin_mask == 1) 才允许连线
                        if self.active_pin_mask[j * 3 + p_idx] > 0.5:
                            dag_mask[i, j * self.num_pins_per_c + p_idx] = 0.0
                        
            # 外部输出通道 (Sink) 永远畅通
            dag_mask[i, total_target_pins] = 0.0 
            
        self.register_buffer('dag_mask', dag_mask)

# 物理库解析器：将原始物理库 Tensor 转换为训练友好的格式
    def _parse_tensors(self, tensors):
        areas, caps, arcs = [], [], []
        for ct in tensors:
            areas.append(ct.get('cell_area', 1.0))
            p_caps = [ct.get('pin_cap', {}).get(p, 0.001) for p in self.pin_names]
            caps.append(p_caps)
            
            arc_dict = {'S': {}, 'CO': {}}
            for in_p in self.pin_names:
                arc_s = ct.get('S', {}).get(in_p)
                arc_co = ct.get('CO', {}).get(in_p)
                if arc_s: arc_dict['S'][in_p] = arc_s
                if arc_co: arc_dict['CO'][in_p] = arc_co
            arcs.append(arc_dict)
        return torch.tensor(areas, dtype=torch.float32), torch.tensor(caps, dtype=torch.float32), arcs

# 前向传播：核心的可微 STA 计算逻辑
    def forward(self, pp_at, pp_slew):
        # 1. 施加异构物理掩码
        P_c = F.softmax(self.p_logits + self.p_mask, dim=-1) 
        M_full = F.softmax(self.m_logits + self.dag_mask, dim=-1) 
        M_internal = M_full[:, :-1] 
        
        # 2. 利用概率计算面积与节点负载的数学期望
        expected_area = 0.0
        
        # [Dr. Gemini 修正 2]: 使用列表与 cat，彻底根除 In-place 梯度炸弹
        expected_pin_caps_list = []

        # 对于 每一个压缩器 c:
        #     期望面积 += Sum( P_c[c] * c的所有可能物理面积 )
        #     期望引脚电容向量[c的引脚区间] = P_c[c] 与 [c的所有物理引脚电容] 的点积
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
        
        # 将输入节点的时序堆叠为 Tensor 备用
        pp_ats_stack = torch.stack(list(pp_at))
        pp_slews_stack = torch.stack(list(pp_slew))
        
        s_ats, s_slews = [], []
        co_ats, co_slews = [], []

        for j in range(self.num_c):
            pin_ats, pin_slews = [], []
            for p_idx in range(self.num_pins_per_c):
                col_idx = j * self.num_pins_per_c + p_idx
                
                # [Dr. Gemini 核心修正 1]: 真正的深度拓扑连通！
                # 1. 提取来自 PP (部分积) 的信号期望
                m_pp = M_internal[:self.num_pp, col_idx]
                expected_pin_at = torch.sum(m_pp * pp_ats_stack)
                expected_pin_slew = torch.sum(m_pp * pp_slews_stack)
                
                # 2. 提取来自前方压缩器 S 输出的信号 (j > 0 时才有前方节点)
                if j > 0:
                    m_s = M_internal[self.num_pp : self.num_pp + j, col_idx]
                    expected_pin_at = expected_pin_at + torch.sum(m_s * torch.stack(s_ats))
                    expected_pin_slew = expected_pin_slew + torch.sum(m_s * torch.stack(s_slews))
                    
                    # 3. 提取来自前方压缩器 CO 输出的信号
                    m_co = M_internal[self.num_pp + self.num_c : self.num_pp + self.num_c + j, col_idx]
                    expected_pin_at = expected_pin_at + torch.sum(m_co * torch.stack(co_ats))
                    expected_pin_slew = expected_pin_slew + torch.sum(m_co * torch.stack(co_slews))
                
                pin_ats.append(expected_pin_at)
                pin_slews.append(expected_pin_slew)

            # --- 下方的物理插值代码保持不变 ---
            s_load = loads[self.num_pp + j]
            co_load = loads[self.num_pp + self.num_c + j]
            
            expected_s_at, expected_s_slew = 0.0, 0.0
            expected_co_at, expected_co_slew = 0.0, 0.0
            
            is_fa = (self.c_types[j] == 'FA')
            num_impls = self.num_fa_impls if is_fa else self.num_ha_impls
            cell_arcs = self.fa_arcs if is_fa else self.ha_arcs
            
            for impl_idx in range(num_impls):
                prob_impl = P_c[j, impl_idx]
                arcs = cell_arcs[impl_idx]
                
                s_paths_at, s_paths_slew = [], []
                for p_idx, p_name in enumerate(self.pin_names):
                    if p_name in arcs['S']:
                        arc = arcs['S'][p_name]
                        delay = diff_bilinear_interp(pin_slews[p_idx], s_load, arc['index_1_slew'], arc['index_2_load'], arc['delay_lut'])
                        slew = diff_bilinear_interp(pin_slews[p_idx], s_load, arc['index_1_slew'], arc['index_2_load'], arc['slew_lut'])
                        s_paths_at.append(pin_ats[p_idx] + delay)
                        s_paths_slew.append(slew)
                        
                s_at_impl = smooth_max_lse(torch.stack(s_paths_at), gamma=0.01) if s_paths_at else torch.tensor(10.0, device=P_c.device)
                s_slew_impl = smooth_max_lse(torch.stack(s_paths_slew), gamma=0.01) if s_paths_at else torch.tensor(10.0, device=P_c.device)
                    
                co_paths_at, co_paths_slew = [], []
                for p_idx, p_name in enumerate(self.pin_names):
                    if p_name in arcs['CO']:
                        arc = arcs['CO'][p_name]
                        delay = diff_bilinear_interp(pin_slews[p_idx], co_load, arc['index_1_slew'], arc['index_2_load'], arc['delay_lut'])
                        slew = diff_bilinear_interp(pin_slews[p_idx], co_load, arc['index_1_slew'], arc['index_2_load'], arc['slew_lut'])
                        co_paths_at.append(pin_ats[p_idx] + delay)
                        co_paths_slew.append(slew)
                        
                co_at_impl = smooth_max_lse(torch.stack(co_paths_at), gamma=0.01) if co_paths_at else torch.tensor(10.0, device=P_c.device)
                co_slew_impl = smooth_max_lse(torch.stack(co_paths_slew), gamma=0.01) if co_paths_at else torch.tensor(10.0, device=P_c.device)
                    
                expected_s_at = expected_s_at + prob_impl * s_at_impl
                expected_s_slew = expected_s_slew + prob_impl * s_slew_impl
                expected_co_at = expected_co_at + prob_impl * co_at_impl
                expected_co_slew = expected_co_slew + prob_impl * co_slew_impl
                
            s_ats.append(expected_s_at)
            s_slews.append(expected_s_slew)
            co_ats.append(expected_co_at)
            co_slews.append(expected_co_slew)
            
        # 循环彻底结束后，再将所有的节点时序拼成全局 Tensor
        node_ats = list(pp_at) + s_ats + co_ats
        all_ats_tensor = torch.stack(node_ats)
        
        slacks = self.req_time - all_ats_tensor
        negative_slacks = torch.clamp(slacks, max=0.0)
        
        WNS = smooth_max_lse(-negative_slacks, gamma=0.01) 
        TNS = torch.sum(-negative_slacks)
        
        return WNS, TNS, expected_area, M_internal, P_c