import torch
import torch.optim as optim
import time
import torch.profiler

class DOMACTrainer:
    def __init__(self, model, loss_engine, lr=0.01):
        """
        DOMAC 训练引擎 (Dr. Gemini 性能探针版 + 并发进度回调支持)
        """
        self.model = model
        self.loss_engine = loss_engine
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)
        # # [暴力修正] 让 P_c (物理门选择) 的变化速度比 M (连线拓扑) 快 5 倍！
        # self.optimizer = optim.Adam([
        #     {'params': [self.model.m_logits], 'lr': lr},
        #     {'params': [self.model.p_logits], 'lr': lr * 5.0}  # 强行加速物理收敛
        # ])

        self.hyperparams = {
            't1': 1.45,     # WNS 权重拉到极致，逼迫网络突破延迟极限
            't2': 0.4,       # TNS 辅助全局路径寻优
            'alpha': 1,    # 【封印】前期绝对不许管面积！
            'lambda1': 0.66,  # 连线合法性是必须的
            'lambda2': 0.24,  # 【封印】前期不许进行二值化坍缩！让概率保持连续，充分探索！
            'tau_k':1,
            'beta': 0.0,  
        }
        
        # self.hyperparams = {
        #     't1': 3.4,     # WNS 权重拉到极致，逼迫网络突破延迟极限
        #     't2': 0.35,       # TNS 辅助全局路径寻优
        #     'alpha': 1,    # 【封印】前期绝对不许管面积！
        #     'lambda1': 0.25,  # 连线合法性是必须的
        #     'lambda2': 0.12,  # 【封印】前期不许进行二值化坍缩！让概率保持连续，充分探索！
        #     'tau_k':0.995,
        #     'beta': 100,     # 新增：毛刺功耗权重，适度关注毛刺下降但不至于过早牺牲性能
        # }
 
    def update_hyperparameters(self, epoch):
        # 阶段一：纯粹的 WNS 拓扑探索 (Epoch 0 ~ 150)
        # alpha, lambda1, lambda2 保持极低或初始状态，beta = 0
        if epoch < 150:
            pass 
            
        # 阶段二：面积回收与强制离散化 (Epoch 150 ~ 450)
        elif 150 <= epoch < 450:
            self.hyperparams['alpha'] *= 1.005    # 开始施压清理冗余面积
            self.hyperparams['t1'] *= 1.002       # WNS 继续缓慢施压
            self.hyperparams['lambda1'] *= 1.02   # 收紧合法性
            self.hyperparams['lambda2'] *= 1.05   # 暴力逼迫二值化
            # beta 依然为 0
            
        # 阶段三：极寒物理微调与毛刺消除 (Epoch 450 ~ 500)
        else:
            if epoch == 450:
                print("\n[Scheduler] 进入极寒固化期！唤醒毛刺消除引擎 (Beta)")
                self.hyperparams['beta'] = 0.5    # 突然施加毛刺惩罚！
            
            self.hyperparams['lambda2'] *= 1.01   # 维持二值化压力
            self.hyperparams['beta'] *= 1.02      # 缓慢增加防毛刺力度

            # 核心逻辑：此阶段 alpha (面积) 保持冰封或原样，给功耗优化留出绝对的空间

        # # 阶段 3 (Epoch 200 之后): 面积回收与物理坍缩
        # elif epoch >= 200:
        #     self.hyperparams['alpha'] *= 1.003
        #     self.hyperparams['t1'] *= 1.005
        #     self.hyperparams['t2'] *= 1.005
        #     self.hyperparams['lambda1'] *= 1.02   # 逼近 Legalizer，增强合法性惩罚
        #     self.hyperparams['lambda2'] *= 1.05   # 终极二值化施压，逼迫概率走向 0 或 1
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
    #     if epoch > 120:
    #         # self.hyperparams['lambda1'] *= 1.02  # 越来越严苛的合法性
    #         # self.hyperparams['lambda2'] *= 1.05  # 逼迫概率走向 0 或 1
    #         # self.hyperparams['alpha'] *= 1.005   # 轻微压缩面积
    #         self.hyperparams['lambda1'] *= 1.02  
    #         self.hyperparams['lambda2'] *= 1.05  
    #         self.hyperparams['alpha'] *= 1.002

    # ================= [修改点 1：增加 epoch_callback 参数] =================
    def train(self, pp_at, pp_slew, max_epochs=300, epoch_callback=None):
    # ========================================================================
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
            # current_tau_k = self.hyperparams.get('tau_k')
            # 手动控制三段式温度
            # 在 train 函数的 tau 调度中：
            if epoch < 150:
                current_tau = 1.0
            elif epoch < 450:
                current_tau = max(0.01, 1.0 * (0.985 ** (epoch - 150))) # 加快降温，探底 0.01
            else:
                current_tau = 0.01 # 绝对零度
            # current_tau = max(0.05, 1.0 * (current_tau_k ** epoch))
            # current_tau = 1
            # # ================= [修复：三段式科学退火调度] =================
            # if epoch < 60:
            #     # [阶段 1: 探索期] 保持高温 1.0。
            #     # 允许一定的概率稀释，让梯度在不同拓扑之间顺畅流动，寻找最优解
            #     current_tau = 1.0 
            # elif epoch < 200:
            #     # [阶段 2: 极化期] 极其缓慢地降温。
            #     # 0.99 保证在 140 个 Epoch 内从 1.0 慢慢降到 0.24 左右。
            #     # 此时 WNS 的梯度依然存活，引导网络慢慢将优势路径向 1.0 靠拢。
            #     current_tau = 1.0 * (0.99 ** (epoch - 60))
            # else:
            #     # [阶段 3: 淬火期] 强制逼近 0.1 以下，固化物理连线，准备迎接 Legalizer
            #     # current_tau = max(0.05, 0.24 * (0.95 ** (epoch - 200)))
            #     # [阶段 3: 淬火期] 强制极化，但保留最低限度的梯度流
            #     current_tau = max(0.15, 0.24 * (0.95 ** (epoch - 200)))
            # # =================================================================
            
            # ================= [探针 1: 前向传播 STA] =================
            t0 = time.time()
            # wns, tns, area, M, P_c = self.model(pp_at, pp_slew)
            wns, tns, area, glitch, M, P_c = self.model(pp_at, pp_slew, tau=current_tau)
            t1 = time.time()
            acc_forward += (t1 - t0)
            
            active_pin_mask = self.model.active_pin_mask
            c_types = self.model.c_types
            
            # ================= [探针 2: 目标与约束 Loss 计算] =================
            total_loss, loss_dict = self.loss_engine(
                wns, tns, area,glitch, M, P_c, self.hyperparams, 
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
            
            # ================= [修改点 2：触发全局进度条回调] =================
            # 将当前 epoch 和最新的 WNS 传递给主进程的 tqdm 监听器
            if epoch_callback is not None:
                current_wns_val = loss_dict['wns'].item() if 'wns' in loss_dict else 0.0
                epoch_callback(epoch, current_wns_val)
            # ==================================================================

            # 每 20 步打印一次物理指标与性能报告
            if epoch % 20 == 0 or epoch == max_epochs - 1:
                print(f"\nEpoch {epoch:03d} | "
                      f"WNS: {loss_dict['wns'].item():.4f} | "
                      f"Area: {loss_dict['area'].item():.4f} | "
                      f"Glitch: {loss_dict['glitch'].item():.4f} | " # <--- 【新增监控】
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
                
                # ================= [深度时序探针：揭露 AT 概率稀释真相] =================
                pin_ats = self.model._probe_pin_ats
                node_ats = self.model._probe_node_ats
                
                # 找出全图预期到达时间 (Expected AT) 最大的输入引脚
                worst_pin_idx = torch.argmax(pin_ats).item()
                worst_expected_at = pin_ats[worst_pin_idx].item()
                
                print(f"\n  🔍 [时序深度穿透] 观测最差引脚 Index: {worst_pin_idx} | 连续域期望 AT: {worst_expected_at:.4f} ns")
                
                # 提取该引脚的上游连线概率云
                probs_to_worst_pin = M[:, worst_pin_idx]
                top_probs, top_indices = torch.topk(probs_to_worst_pin, 5)
                
                expected_at_sum = 0.0
                for p, src_idx in zip(top_probs, top_indices):
                    src_at = node_ats[src_idx].item()
                    contribution = p.item() * src_at
                    expected_at_sum += contribution
                    print(f"      [源节点 {src_idx.item():>3d}] 概率: {p.item():.4f} | 真实物理AT: {src_at:.4f} ns -> 被稀释为: {contribution:.4f} ns")
                
                print(f"      ... (长尾碎概率贡献总和: {max(0.0, worst_expected_at - expected_at_sum):.4f} ns)")
                
                worst_physical_at = node_ats[top_indices[0]].item()
                print(f"  ⚠️  [物理真相警告] 若此时 Legalizer 强行硬连最大概率线, 该引脚真实 AT 将瞬间暴涨至 -> {worst_physical_at:.4f} ns!\n")
                # ====================================================================
                
                # 清零累加器，准备下一个周期的监控
                acc_forward, acc_loss, acc_backward, acc_step = 0.0, 0.0, 0.0, 0.0

        print("[Optimizer] 训练收敛完成。")
        return M.detach(), P_c.detach()