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
        # # [暴力修正] 让 P_c (物理门选择) 的变化速度比 M (连线拓扑) 快 5 倍！
        # self.optimizer = optim.Adam([
        #     {'params': [self.model.m_logits], 'lr': lr},
        #     {'params': [self.model.p_logits], 'lr': lr * 5.0}  # 强行加速物理收敛
        # ])

        # self.hyperparams = {
        #     't1': 10000.0,     # WNS 权重拉到极致，逼迫网络突破延迟极限
        #     't2': 0.01,       # TNS 辅助全局路径寻优
        #     'alpha': 3.0,    # 【封印】前期绝对不许管面积！
        #     'lambda1': 0.1,  # 连线合法性是必须的
        #     'lambda2': 0.5,  # 【封印】前期不许进行二值化坍缩！让概率保持连续，充分探索！
        # }

        self.hyperparams = {
            't1': 10.0,     # WNS 权重拉到极致，逼迫网络突破延迟极限
            't2': 0.01,       # TNS 辅助全局路径寻优
            'alpha': 0,    # 【封印】前期绝对不许管面积！
            'lambda1': 0.1,  # 连线合法性是必须的
            'lambda2': 0,  # 【封印】前期不许进行二值化坍缩！让概率保持连续，充分探索！
        }
    # def update_hyperparameters(self, epoch):
    #     if epoch >= 100:
    #         self.hyperparams['alpha'] *= 1.003
    #         self.hyperparams['t1'] *= 1.005
    #         self.hyperparams['t2'] *= 1.005
    #         self.hyperparams['lambda1'] *= 1.01
    #         self.hyperparams['lambda2'] *= 1.01

    def update_hyperparameters(self, epoch):
        """
        动态退火调度器：分阶段释放约束
        """
        # 阶段 1 (Epoch 0-99)：野蛮生长，全力追求 WNS 和合法拓扑
        
        # 阶段 2 (Epoch 100 触发)：拓扑基本成型，开始施加面积与二值化压力
        if epoch == 100:
            print("\n[Scheduler] Epoch 100 抵达！解封 Area 与 二值化 (L_D) 约束！")
            self.hyperparams['alpha'] = 0.05   
            self.hyperparams['lambda2'] = 0.1  
            
        # 阶段 3 (Epoch 100-300)：温水煮青蛙，逐步收紧离散化和合法性，逼迫最终坍缩
        if epoch > 100:
            self.hyperparams['lambda1'] *= 1.02  # 越来越严苛的合法性
            self.hyperparams['lambda2'] *= 1.05  # 逼迫概率走向 0 或 1
            self.hyperparams['alpha'] *= 1.005   # 轻微压缩面积

    def train(self, pp_at, pp_slew, max_epochs=300):
        print(f"[Optimizer] 启动 DOMAC 训练循环，最大迭代次数: {max_epochs}")
        print(f"[Profiler] 性能探针已植入。正在监控 Forward, Loss, Backward, Step 耗时...")
        
        # 性能累加器
        acc_forward, acc_loss, acc_backward, acc_step = 0.0, 0.0, 0.0, 0.0
        
        for epoch in range(max_epochs):
            self.update_hyperparameters(epoch)
            self.optimizer.zero_grad()
            
            # ================= [新增：极其暴力的温度退火] =================
            # 指数级降温：Epoch 0 时 tau=1.0，Epoch 300 时 tau 接近 0.05
            # 这会把 AI 伪造的 "冰块概率" 强行压成 0，暴露出真实的延迟！
            current_tau = max(0.05, 1.0 * (0.985 ** epoch))
            # current_tau = 1
            # ================= [探针 1: 前向传播 STA] =================
            t0 = time.time()
            # wns, tns, area, M, P_c = self.model(pp_at, pp_slew)
            wns, tns, area, M, P_c = self.model(pp_at, pp_slew, tau=current_tau)
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
                
                # ================= [探针：抓捕 AI 的概率稀释作弊] =================
                # M 矩阵的 Shape 是 [总节点数, 压缩器引脚总数]
                # 对每一列求最大值，代表该引脚最主要的信号来源所占的百分比
                max_probs_per_pin, _ = torch.max(M, dim=0)
                
                # 统计有多少个引脚的“主来源概率”低于 0.95 (即掺杂了 >5% 的冰块信号)
                cheating_pins = torch.sum((max_probs_per_pin < 0.95) & (active_pin_mask > 0.5)).item()
                avg_max_prob = torch.mean(max_probs_per_pin).item()
                
                print(f"  -> [探针] 引脚最大连接概率均值: {avg_max_prob:.4f} (若趋近 1.0 则为纯粹硬连线)")
                print(f"  -> [探针] 发现 {cheating_pins} 个引脚正在进行严重的小数概率稀释！")
                
                # 特别打印最后一个压缩器 (极有可能是贪吃蛇的末端) 的三个引脚连线概率
                last_c_idx = P_c.shape[0] - 1
                col_A = last_c_idx * 3 + 0
                col_B = last_c_idx * 3 + 1
                col_CI = last_c_idx * 3 + 2
                print(f"  -> [探针] 末端加法器_{last_c_idx} 的主来源概率 - A:{max_probs_per_pin[col_A]:.4f}, B:{max_probs_per_pin[col_B]:.4f}, CI:{max_probs_per_pin[col_CI]:.4f}")
                # 清零累加器，准备下一个周期的监控

                acc_forward, acc_loss, acc_backward, acc_step = 0.0, 0.0, 0.0, 0.0

        print("[Optimizer] 训练收敛完成。")
        return M.detach(), P_c.detach()