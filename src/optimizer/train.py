import torch
import torch.optim as optim
import time
import torch.profiler
import math

class DOMACTrainer:
    def __init__(self, model, loss_engine, lr=0.01):
        """
        DOMAC 训练引擎 (Dr. Gemini 性能探针版 + 并发进度回调支持)
        """
        self.model = model
        self.loss_engine = loss_engine
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)

        # 将超参数的设定改为：初始值 (Init) 与 极限值 (Max)
        self.hyperparams = {
            't1': 1.45,        # WNS 始终保持主导
            't2': 0.04,         # TNS 辅助
            'alpha': 0.0,      # 初始不看面积
            'lambda1': 0.3,    # 初始维持轻微合法性
            'lambda2': 0.0,    # 初始绝对不允许二值化
            'tau': 1.0,        # 初始高温，充分探索
            'beta': 0.0,       # 初始无视毛刺
        }
        
        # 设定绝对安全上限，防止梯度爆炸
        self.max_bounds = {
            't1_max': 40,
            'alpha_max': 0.1,
            'lambda1_max': 4.0,   # 足够让 L_BM 降到 0，又不会反噬
            'lambda2_max': 10,  # L_D 本身数值很大(~150)，权重只需 0.15 就能产生 ~20 的惩罚
            'tau_min': 1,       # 最低温度 0.1 足够完成极化
            'beta_max': 5       # 毛刺惩罚适可而止
        }

    def _cosine_schedule(self, current_step, start_step, end_step, start_val, end_val):
        """
        学术级通用余弦退火函数
        在 start_step 之前返回 start_val；在 end_step 之后返回 end_val。
        在区间内呈现平滑的 S 型过渡。
        """
        if current_step <= start_step:
            return start_val
        if current_step >= end_step:
            return end_val
        
        progress = (current_step - start_step) / (end_step - start_step)
        # 余弦公式：平滑过渡从 0 到 1
        cosine_decay = 0.5 * (1.0 - math.cos(math.pi * progress))
        return start_val + (end_val - start_val) * cosine_decay

    def update_hyperparameters(self, epoch):
        # [阶段 1: 拓扑成型期 Epoch 0 ~ 80]
        # 只管 WNS 和 TNS，完全无拘无束地野蛮生长。
        
        # [阶段 2: 面积与【毛刺】的温和介入 Epoch 80 ~ 180]
        # 在网络还在犹豫的时候，把 Area 和 Beta 提上来，作为“破局”的次要标准
        self.hyperparams['alpha'] = self._cosine_schedule(epoch, 80, 180, 0.0, self.max_bounds['alpha_max'])
        self.hyperparams['lambda1'] = self._cosine_schedule(epoch, 80, 180, 0.2, self.max_bounds['lambda1_max'])
        self.hyperparams['t1'] = self._cosine_schedule(epoch, 80, 180, 1.45, self.max_bounds['t1_max'])
        
        # 【修正】毛刺惩罚必须在坍缩前觉醒！让它引导网络选择更平稳的拓扑分支
        self.hyperparams['beta'] = self._cosine_schedule(epoch, 100, 200, 0.0, self.max_bounds['beta_max'])
        
        # [阶段 3: 概率坍缩极化期 Epoch 150 ~ 250]
        # 听取了 WNS、Area 和 Glitch 的综合意见后，开始降温关门，焊死网表！
        self.hyperparams['tau'] = self._cosine_schedule(epoch, 150, 250, 1.0, self.max_bounds['tau_min'])
        self.hyperparams['lambda2'] = self._cosine_schedule(epoch, 150, 250, 0.0, self.max_bounds['lambda2_max'])
        
        # [阶段 4: 物理微调 Epoch 250 ~ 300]
        # 维持以上所有最大权重，让优化器在这个硬约束空间里走完最后的收敛步。

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
            # if epoch < 150:
            #     current_tau = 1.0
            # elif epoch < 450:
            #     current_tau = max(0.01, 1.0 * (0.985 ** (epoch - 150))) # 加快降温，探底 0.01
            # else:
            #     current_tau = 0.01 # 绝对零度
            # current_tau = max(0.05, 1.0 * (current_tau_k ** epoch))
            current_tau = 1

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
                # ================= [新增监控：各项损失的加权贡献度占比] =================
                hp = self.hyperparams
                t_loss = total_loss.item() + 1e-9  # 加 1e-9 防止极早期或异常情况下的除零灾难
                
                # 计算各项乘以动态超参数后的实际绝对贡献值
                w_wns = hp['t1'] * loss_dict['wns'].item()
                w_tns = hp['t2'] * loss_dict['tns'].item()
                w_area = hp['alpha'] * loss_dict['area'].item()
                w_glitch = hp.get('beta', 0.0) * loss_dict['glitch'].item()
                w_l_bm = hp['lambda1'] * loss_dict['l_bm'].item()
                w_l_d = hp['lambda2'] * loss_dict['l_d'].item()
                
                # 提示：如果输出的百分比总和不等于 100%，缺失的那部分是 TNS 和 Sink 惩罚的占比
                print(f"\nEpoch {epoch:03d} | "
                      f"WNS: {loss_dict['wns'].item():.4f} ({w_wns/t_loss*100:4.1f}%) | "
                      f"TNS: {loss_dict['tns'].item():.4f} ({w_tns/t_loss*100:4.1f}%) | "
                      f"Area: {loss_dict['area'].item():.4f} ({w_area/t_loss*100:4.1f}%) | "
                      f"Glitch: {loss_dict['glitch'].item():.4f} ({w_glitch/t_loss*100:4.1f}%) | "
                      f"L_BM: {loss_dict['l_bm'].item():.4f} ({w_l_bm/t_loss*100:4.1f}%) | "
                      f"L_D: {loss_dict['l_d'].item():.4f} ({w_l_d/t_loss*100:4.1f}%) | "
                      f"Total Loss: {total_loss.item():.4f}")

                # =======================================================================
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
                
                # 统计有多少个引脚的“主来源概率”低于 0.90 (即掺杂了 >10% 的冰块信号)
                cheating_pins = torch.sum((max_probs_per_pin < 0.90) & (active_pin_mask > 0.5)).item()
                avg_max_prob = torch.mean(max_probs_per_pin).item()
                
                print(f"  -> [探针] 引脚最大连接概率均值: {avg_max_prob:.4f} ")
                print(f"  -> [探针] 发现 {cheating_pins} 个引脚“主来源概率”低于 0.90")
                
                # # 特别打印最后一个压缩器 (极有可能是贪吃蛇的末端) 的三个引脚连线概率
                # last_c_idx = P_c.shape[0] - 1
                # col_A = last_c_idx * 3 + 0
                # col_B = last_c_idx * 3 + 1
                # col_CI = last_c_idx * 3 + 2
                # print(f"  -> [探针] 末端加法器_{last_c_idx} 的主来源概率 - A:{max_probs_per_pin[col_A]:.4f}, B:{max_probs_per_pin[col_B]:.4f}, CI:{max_probs_per_pin[col_CI]:.4f}")
                
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