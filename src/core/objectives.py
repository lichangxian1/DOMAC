import torch
import torch.nn as nn

class DOMACLossFunction(nn.Module):
    def __init__(self, pin_counts_lib=[3.0, 2.0]):
        """
        DOMAC 联合目标与约束损失函数引擎
        
        参数:
        pin_counts_lib (list of float): 库中对应实现方式的输入引脚数。
                                        默认 [3.0, 2.0] 代表 index 0 是 FA(3输入), index 1 是 HA(2输入)。
        """
        super(DOMACLossFunction, self).__init__()
        self.pin_counts = torch.tensor(pin_counts_lib, dtype=torch.float32)
        
    def calc_performance_loss(self, wns, tns, area, t1, t2, alpha):
        """
        1. 性能驱动损失 (Performance Objective)
        公式: L_perf = t1 * WNS + t2 * TNS + alpha * Area
        """
        return t1 * wns + t2 * tns + alpha * area

    def calc_bijective_mapping_loss(self, M, P_c):
        """
        2. 双射映射约束损失 (Bijective Mapping Loss L_BM)
        
        【第一性原理深度解析】：
        在上一步的 CompressorTree 中，我们对 M 的行做了 Softmax，
        这意味着 "每一个上游节点的输出，必然按概率总和为1分配给了下游"。 (行和强制为1)
        但是！我们还没有约束 "接收端 (Compressor)"！
        一个全加器 (FA) 必须接收刚好 3 个输入，半加器 (HA) 必须接收刚好 2 个输入。
        如果当前节点被选择为 FA 的概率是 P_FA，HA 的概率是 P_HA，
        那么它期望接收的输入总数应该是: expected_in = P_FA * 3 + P_HA * 2
        
        因此，M 矩阵的【列和】必须极其严苛地逼近这个 expected_in！
        """
        # 计算 M 的实际列和 (每个压缩器收到的期望输入信号总数)
        # M shape: [total_nodes, num_compressors] -> col_sums shape: [num_compressors]
        actual_in_signals = torch.sum(M, dim=0) 
        
        # 计算基于物理实现概率的合法输入引脚数
        # P_c shape: [num_compressors, num_impls]
        # pin_counts shape: [num_impls]
        expected_pins = P_c @ self.pin_counts.to(P_c.device)
        
        # 计算均方误差惩罚 (MSE)
        l_bm = torch.sum((actual_in_signals - expected_pins) ** 2)
        return l_bm

    def calc_discretization_loss(self, tensor):
        """
        3. 二值化驱动损失 (Discretization Loss L_D)
        
        公式: L_D = sum( x^2 * (1-x)^2 )
        这是一个经典的双势阱函数 (Double-well potential)。
        当 x 趋近于 0.5 时，导数最大，产生极强的排斥力将概率向两边推。
        当 x 趋近于 0 或 1 时，损失降为 0，且导数也为 0，陷入稳定态。
        """
        return torch.sum((tensor ** 2) * ((1.0 - tensor) ** 2))

    def forward(self, wns, tns, area, M, P_c, hyperparams):
        """
        联合损失计算引擎
        
        hyperparams 字典需包含当前迭代步的动态权重:
        {'t1': ..., 't2': ..., 'alpha': ..., 'lambda1': ..., 'lambda2': ...}
        """
        t1 = hyperparams['t1']
        t2 = hyperparams['t2']
        alpha = hyperparams['alpha']
        lambda1 = hyperparams['lambda1']
        lambda2 = hyperparams['lambda2']
        
        # 1. 性能 Loss
        l_perf = self.calc_performance_loss(wns, tns, area, t1, t2, alpha)
        
        # 2. 合法拓扑 Loss
        l_bm = self.calc_bijective_mapping_loss(M, P_c)
        
        # 3. 离散化 Loss (应用于连接矩阵 M 和 物理选择矩阵 P_c)
        l_d_M = self.calc_discretization_loss(M)
        l_d_P = self.calc_discretization_loss(P_c)
        l_d = l_d_M + l_d_P
        
        # 4. 总 Loss 融合
        total_loss = l_perf + lambda1 * l_bm + lambda2 * l_d
        
        # 返回详细字典，便于在训练脚本中打印和监控收敛趋势
        loss_dict = {
            'total_loss': total_loss,
            'l_perf': l_perf,
            'l_bm': l_bm,
            'l_d': l_d,
            'wns': wns,
            'tns': tns,
            'area': area
        }
        
        return total_loss, loss_dict

# ================= Loss 第一性原理推演测试 =================
if __name__ == "__main__":
    print("[Objectives] 启动 DOMAC 数学约束场校验...")
    
    # 模拟环境
    loss_engine = DOMACLossFunction(pin_counts_lib=[3.0, 2.0]) # FA=3, HA=2
    
    # 模拟一个完美合法的状态：
    # 假设有 1 个压缩器，它 100% 确定自己是 FA (需要3个输入)
    perfect_P_c = torch.tensor([[1.0, 0.0]], requires_grad=True)
    # 有 4 个上游节点，前 3 个 100% 连接到它，第 4 个没连
    perfect_M = torch.tensor([
        [1.0], 
        [1.0], 
        [1.0], 
        [0.0]
    ], requires_grad=True)
    
    l_bm_perfect = loss_engine.calc_bijective_mapping_loss(perfect_M, perfect_P_c)
    l_d_perfect = loss_engine.calc_discretization_loss(perfect_M) + loss_engine.calc_discretization_loss(perfect_P_c)
    
    print(f"完美离散态 -> L_BM: {l_bm_perfect.item():.6f} (期望为0), L_D: {l_d_perfect.item():.6f} (期望为0)")
    
    # 模拟一个混沌的中间状态：
    # 压缩器 50% 是 FA，50% 是 HA (期望输入数: 0.5*3 + 0.5*2 = 2.5)
    chaos_P_c = torch.tensor([[0.5, 0.5]], requires_grad=True)
    # 上游节点都以 0.6 的概率连过来 (实际列和: 4 * 0.6 = 2.4)
    chaos_M = torch.tensor([
        [0.6], 
        [0.6], 
        [0.6], 
        [0.6]
    ], requires_grad=True)
    
    l_bm_chaos = loss_engine.calc_bijective_mapping_loss(chaos_M, chaos_P_c)
    l_d_chaos = loss_engine.calc_discretization_loss(chaos_M) + loss_engine.calc_discretization_loss(chaos_P_c)
    
    print(f"混沌叠加态 -> L_BM: {l_bm_chaos.item():.6f} (差距 2.5-2.4=0.1, 0.1^2=0.01), L_D: {l_d_chaos.item():.6f} (产生巨大惩罚值)")