import torch
import torch.optim as optim
import time
import torch.profiler

class DOMACTrainer:
    def __init__(self, model, loss_engine, lr=0.01):
        """
        DOMAC 训练引擎 (Dr. Gemini 性能探针版)
        """
        self.model = model
        self.loss_engine = loss_engine
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)
        
# [Dr. Gemini 的极权统治：初期只看速度和合法性]
        self.hyperparams = {
            't1': 1.0,     # WNS 权重拉到极致，逼迫网络突破延迟极限
            't2': 0.01,       # TNS 辅助全局路径寻优
            'alpha': 3.0,    # 【封印】前期绝对不许管面积！
            'lambda1': 0.1,  # 连线合法性是必须的
            'lambda2': 0.5,  # 【封印】前期不许进行二值化坍缩！让概率保持连续，充分探索！
        }

    def update_hyperparameters(self, epoch):
        if epoch >= 100:
            self.hyperparams['alpha'] *= 1.003
            self.hyperparams['t1'] *= 1.005
            self.hyperparams['t2'] *= 1.005
            self.hyperparams['lambda1'] *= 1.01
            self.hyperparams['lambda2'] *= 1.01

    # def update_hyperparameters(self, epoch):
    #     """
    #     动态退火调度器：分阶段释放约束
    #     """
    #     # 阶段 1 (Epoch 0-99)：野蛮生长，全力追求 WNS 和合法拓扑
        
    #     # 阶段 2 (Epoch 100 触发)：拓扑基本成型，开始施加面积与二值化压力
    #     if epoch == 100:
    #         print("\n[Scheduler] Epoch 100 抵达！解封 Area 与 二值化 (L_D) 约束！")
    #         self.hyperparams['alpha'] = 0.05   
    #         self.hyperparams['lambda2'] = 0.1  
            
    #     # 阶段 3 (Epoch 100-300)：温水煮青蛙，逐步收紧离散化和合法性，逼迫最终坍缩
    #     if epoch > 100:
    #         self.hyperparams['lambda1'] *= 1.02  # 越来越严苛的合法性
    #         self.hyperparams['lambda2'] *= 1.05  # 逼迫概率走向 0 或 1
    #         self.hyperparams['alpha'] *= 1.005   # 轻微压缩面积

    def train(self, pp_at, pp_slew, max_epochs=300):
        print(f"[Optimizer] 启动 DOMAC 训练循环，最大迭代次数: {max_epochs}")
        print(f"[Profiler] 性能探针已植入。正在监控 Forward, Loss, Backward, Step 耗时...")
        
        # 性能累加器
        acc_forward, acc_loss, acc_backward, acc_step = 0.0, 0.0, 0.0, 0.0
        
        for epoch in range(max_epochs):
            self.update_hyperparameters(epoch)
            self.optimizer.zero_grad()
            
            # ================= [探针 1: 前向传播 STA] =================
            t0 = time.time()
            wns, tns, area, M, P_c = self.model(pp_at, pp_slew)
            t1 = time.time()
            acc_forward += (t1 - t0)
            
            active_pin_mask = self.model.active_pin_mask
            c_types = self.model.c_types
            
            # ================= [探针 2: 目标与约束 Loss 计算] =================
            total_loss, loss_dict = self.loss_engine(
                wns, tns, area, M, P_c, self.hyperparams, 
                active_pin_mask, c_types
            )
            t2 = time.time()
            acc_loss += (t2 - t1)

            # ================= [探针 3: 反向传播梯度计算] =================
            total_loss.backward()
            t3 = time.time()
            acc_backward += (t3 - t2)
            
            # ================= [探针 4: 优化器参数更新] =================
            self.optimizer.step()
            t4 = time.time()
            acc_step += (t4 - t3)
            
            # 每 20 步打印一次物理指标与性能报告
            if epoch % 20 == 0 or epoch == max_epochs - 1:
                print(f"\nEpoch {epoch:03d} | "
                      f"WNS: {loss_dict['wns'].item():.4f} | "
                      f"Area: {loss_dict['area'].item():.4f} | "
                      f"L_BM: {loss_dict['l_bm'].item():.4f} | "
                      f"Total Loss: {total_loss.item():.4f}")
                
                # 打印过去 20 步的平均耗时 (如果是 Epoch 0，就是单步耗时)
                div = 1 if epoch == 0 else 20
                print(f"  -> [Profiler] Avg Time/Epoch - "
                      f"Forward: {acc_forward/div:.3f}s | "
                      f"Loss: {acc_loss/div:.3f}s | "
                      f"Backward: {acc_backward/div:.3f}s | "
                      f"Step: {acc_step/div:.3f}s")
                
                # 清零累加器，准备下一个周期的监控
                acc_forward, acc_loss, acc_backward, acc_step = 0.0, 0.0, 0.0, 0.0

        print("[Optimizer] 训练收敛完成。")
        return M.detach(), P_c.detach()