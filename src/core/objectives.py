import torch
import torch.nn as nn
import torch.nn.functional as F

class DOMACLossFunction(nn.Module):
    # def __init__(self, pin_counts_lib=[3.0, 2.0]):
    #     """
    #     DOMAC 联合目标与约束损失函数引擎
    #     """
    #     super(DOMACLossFunction, self).__init__()
    #     self.pin_counts = torch.tensor(pin_counts_lib, dtype=torch.float32)
    def __init__(self, target_sink_count, pin_counts_lib=[3.0, 2.0]): # 接收动态目标
        super(DOMACLossFunction, self).__init__()
        self.target_sink_count = target_sink_count
        self.pin_counts = torch.tensor(pin_counts_lib, dtype=torch.float32)

    # def calc_performance_loss(self, wns, tns, area, t1, t2, alpha):
    #     """
    #     1. 性能驱动损失 (Performance Objective)
    #     """
    #     return t1 * wns + t2 * tns + alpha * area
    # def calc_performance_loss(self, wns, tns, area, t1, t2, alpha):
    def calc_performance_loss(self, wns, tns, area, glitch, t1, t2, alpha, beta):
        """
        1. 性能驱动损失 (Performance Objective)
        引入 beta * glitch 来惩罚到达时间的不平衡，从物理底层消灭毛刺功耗。
        """
        return t1 * wns + t2 * tns + alpha * area + beta * glitch
    
    # def calc_bijective_mapping_loss(self, M_internal, P_c):
    #     """
    #     2. Pin-Level 双射映射约束 (Bijective Mapping Loss L_BM)
    #     """
    #     # 实际流入每个特定引脚的概率总和，Shape: [num_c * 3]
    #     actual_in_signals = torch.sum(M_internal, dim=0) 
        
    #     num_c = P_c.shape[0]
    #     # P_c 的列 0 是 FA，列 1 是 HA
    #     expected_pins = torch.zeros(M_internal.shape[1], device=M_internal.device)
        
    #     for j in range(num_c):
    #         expected_pins[j * 3 + 0] = 1.0       # A 引脚: 不管是 FA 还是 HA 都要连
    #         expected_pins[j * 3 + 1] = 1.0       # B 引脚: 不管是 FA 还是 HA 都要连
    #         expected_pins[j * 3 + 2] = P_c[j, 0] # CI 引脚: 只有被判为 FA 的概率部分才允许连线
            
    #     return torch.sum((actual_in_signals - expected_pins) ** 2)

    def calc_bijective_mapping_loss(self, M_internal, P_c, active_pin_mask, c_types):
        actual_in_signals = torch.sum(M_internal, dim=0) 
        num_c = P_c.shape[0]
        expected_pins = torch.zeros(M_internal.shape[1], device=M_internal.device)
    
        for j in range(num_c):
            # A, B 引脚始终需要 1.0 的期望信号
            expected_pins[j * 3 + 0] = 1.0
            expected_pins[j * 3 + 1] = 1.0
        
             # CI 引脚：只有该坑位是 FA 时，才强制要求 1.0 的信号输入
            # 注意：因为你的画布已经提前指定了 c_types (FA或HA)，不需要依赖 P_c 来判断逻辑类型
            if c_types[j] == 'FA':
                expected_pins[j * 3 + 2] = 1.0
            else:
                expected_pins[j * 3 + 2] = 0.0 # HA 绝不要 CI 信号
            
        return torch.sum((actual_in_signals - expected_pins) ** 2)
    
    # def calc_discretization_loss(self, tensor):
    #     """
    #     3. 二值化驱动损失 (Discretization Loss L_D)
    #     """
    #     return torch.sum((tensor ** 2) * ((1.0 - tensor) ** 2))
    def calc_discretization_loss(self, tensor):
        """
        3. 终极二值化驱动：平方和集中度损失 (Gini Impurity / L2 Norm Maximization)
        利用 Softmax 守恒律，直接促使概率矩阵向 One-Hot 坍缩，无需退火算法！
        """
        # tensor shape: [total_nodes, total_target_pins]
        # 对每一行（每一个源节点流出的概率）计算平方和
        # 理想的 One-Hot 状态下，行平方和等于 1；均匀分布时极小。
        row_sq_sum = torch.sum(tensor ** 2, dim=1)
        
        # 目标是最大化平方和，等价于最小化 (1 - sq_sum)
        loss_per_row = 1.0 - row_sq_sum
        
        # 返回全局的总惩罚
        return torch.sum(loss_per_row)

    def calc_sink_loss(self, M_internal, target_max_signals):
        """
        4. [新增] 过度输出惩罚 (Sink Constraint Loss)
        逼迫 AI 使用全加器进行压缩。如果最终流向 Sink 的期望信号数超过限制，施加核弹级惩罚！
        """
        # 利用概率守恒计算流向 Sink 的概率：1 - 内部连线概率总和
        # 每行的和代表该节点进入压缩器的概率，1 减去它就是流向 Sink 的概率
        sink_probs = 1.0 - torch.sum(M_internal, dim=1)
        
        # 整个网络最终抛给外界的总信号期望数
        total_sink_signals = torch.sum(sink_probs)
        
        # 使用 F.relu 提取超标的部分。如果不超标 (<=2.0)，则惩罚为 0；超标则产生极大梯度。
        excess_signals = F.relu(total_sink_signals - target_max_signals)
        
        # 施加高权重的平方惩罚（权重可根据需要调大，比如 100.0 或 1000.0）
        l_sink = (excess_signals ** 2) * 100.0
        return l_sink, total_sink_signals

    def forward(self, wns, tns, area, glitch, M, P_c, hyperparams, active_pin_mask, c_types):    
        """
        联合损失计算引擎
        """
        t1 = hyperparams['t1']
        t2 = hyperparams['t2']
        alpha = hyperparams['alpha']
        beta = hyperparams.get('beta', 0.0) # 新增：提取毛刺功耗权重 (使用 get 防错)
        lambda1 = hyperparams['lambda1']
        lambda2 = hyperparams['lambda2']
        
        # 1. 性能 Loss (现在包含了功耗维度)
        l_perf = self.calc_performance_loss(wns, tns, area, glitch, t1, t2, alpha, beta)
        
        # 2. 合法拓扑 Loss
        l_bm = self.calc_bijective_mapping_loss(M, P_c, active_pin_mask, c_types)

        # 3. 离散化 Loss 
        l_d_M = self.calc_discretization_loss(M)
        l_d_P = self.calc_discretization_loss(P_c)
        l_d = l_d_M + l_d_P
        
        # 4. Sink 惩罚 Loss
        l_sink, actual_sink_count = self.calc_sink_loss(M, target_max_signals=self.target_sink_count)
        
        # 5. 总 Loss 融合
        l_bm_norm = l_bm / (l_bm.detach() + 1e-5)
        l_d_norm = l_d / (l_d.detach() + 1e-5)
        l_sink_norm = l_sink / (l_sink.detach() + 1e-5)
        # total_loss = l_perf + lambda1 * l_bm_norm + lambda2 * l_d_norm + l_sink_norm
        # 核心代码修正 (src/core/objectives.py)
        # 删除归一化操作，直接使用原始标量
        total_loss = l_perf + lambda1 * l_bm + lambda2 * l_d + l_sink     
        loss_dict = {
            'total_loss': total_loss,
            'l_perf': l_perf,
            'l_bm': l_bm,
            'l_d': l_d,
            'l_sink': l_sink,
            'actual_sink_count': actual_sink_count,
            'wns': wns,
            'tns': tns,
            'area': area,
            'glitch': glitch  # 新增：记录到日志，方便在训练时观察毛刺是否在下降
        }
        
        return total_loss, loss_dict