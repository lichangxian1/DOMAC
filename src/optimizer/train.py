import torch
import torch.optim as optim

# 假设我们在上层目录，实际工程中请根据你的模块路径调整 import
# from src.core.compressor_tree import DOMAC_CompressorTree
# from src.core.objectives import DOMACLossFunction

class DOMACTrainer:
    def __init__(self, model, loss_engine, lr=0.01):
        """
        DOMAC 训练引擎
        基于第一性原理驱动可微 STA 和约束场的收敛
        """
        self.model = model
        self.loss_engine = loss_engine
        # DOMAC 论文通常使用 Adam 优化器处理这类具有复杂地形的非凸优化问题
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)
        
        # ================= 初始超参数字典 =================
        # t1, t2: 性能时序权重
        # alpha: 面积权重
        # lambda1: 双射映射(合法连接)约束权重
        # lambda2: 二值化(0/1)约束权重
        self.hyperparams = {
            't1': 1.0,
            't2': 0.01,
            'alpha': 1.0,  # 这个值可能需要根据 28nm 面积的量级做归一化调整
            'lambda1': 1.0,
            'lambda2': 1.0
        }

    def update_hyperparameters(self, epoch):
        """
        动态超参数退火调度器 (Dynamic Hyperparameter Scheduler)
        严格遵循 DOMAC 论文第 IV-C 节的设定：
        从第 100 步开始，每步增加特定百分比，强迫网络物理离散化。
        """
        if epoch >= 100:
            self.hyperparams['alpha'] *= 1.003    # 面积权重每次增加 0.3%
            self.hyperparams['t1'] *= 1.005       # WNS 权重每次增加 0.5%
            self.hyperparams['t2'] *= 1.005       # TNS 权重每次增加 0.5%
            self.hyperparams['lambda1'] *= 1.01   # 双射约束每次增加 1%
            self.hyperparams['lambda2'] *= 1.01   # 二值化约束每次增加 1%

    def train(self, pp_at, pp_slew, max_epochs=300):
        """
        执行主训练循环
        """
        print(f"[Optimizer] 启动 DOMAC 训练循环，最大迭代次数: {max_epochs}")
        
        for epoch in range(max_epochs):
            # 1. 触发动态参数更新
            self.update_hyperparameters(epoch)
            
            # 2. 梯度清零
            self.optimizer.zero_grad()
            
            # 3. 前向传播：穿过物理可微 STA 引擎
            wns, tns, area, M, P_c = self.model(pp_at, pp_slew)
            
            # 4. 计算多目标联合 Loss
            total_loss, loss_dict = self.loss_engine(wns, tns, area, M, P_c, self.hyperparams)
            
            # 5. 反向传播与参数更新
            total_loss.backward()
            self.optimizer.step()
            
            # 6. 工程监控打印 (每 20 步打印一次核心指标)
            if epoch % 20 == 0 or epoch == max_epochs - 1:
                print(f"Epoch {epoch:03d} | "
                      f"WNS: {loss_dict['wns'].item():.4f} | "
                      f"Area: {loss_dict['area'].item():.4f} | "
                      f"L_BM (连接合法性): {loss_dict['l_bm'].item():.4f} | "
                      f"L_D (二值化): {loss_dict['l_d'].item():.4f} | "
                      f"Total Loss: {total_loss.item():.4f}")

        print("[Optimizer] 训练收敛完成。连续概率空间已逼近物理离散态。")
        return M.detach(), P_c.detach()

# ================= 训练引擎独立自测 =================
if __name__ == "__main__":
    # 此处为脱离主框架的 Dummy 测试
    import torch.nn as nn
    import torch.nn.functional as F
    
    # 构建极简 Dummy 模型欺骗引擎，验证训练循环是否能跑通
    class DummyModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.m_logits = nn.Parameter(torch.randn(5, 3))
            self.p_logits = nn.Parameter(torch.randn(3, 2))
        def forward(self, at, slew):
            M = F.softmax(self.m_logits, dim=-1)
            P_c = F.softmax(self.p_logits, dim=-1)
            # 伪造 WNS, TNS, Area
            return torch.tensor(1.5, requires_grad=True), torch.tensor(2.0, requires_grad=True), torch.tensor(10.0, requires_grad=True), M, P_c

    class DummyLoss(nn.Module):
        def forward(self, wns, tns, area, M, P_c, hp):
            loss = hp['t1']*wns + hp['lambda1']*torch.sum(M) + hp['lambda2']*torch.sum(P_c)
            return loss, {'wns': wns, 'area': area, 'l_bm': torch.sum(M), 'l_d': torch.sum(P_c)}

    model = DummyModel()
    loss_fn = DummyLoss()
    trainer = DOMACTrainer(model, loss_fn, lr=0.05)
    
    dummy_at = torch.zeros(5)
    dummy_slew = torch.zeros(5)
    
    # 试跑 300 步
    final_M, final_P = trainer.train(dummy_at, dummy_slew, max_epochs=300)
    
    print("\n训练结束，查看最终的连接概率矩阵 M (局部):")
    print(final_M[:2, :])