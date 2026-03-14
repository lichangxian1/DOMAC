import torch
import numpy as np
from scipy.optimize import linear_sum_assignment

class DOMACLegalizer:
    def __init__(self, pin_counts_lib=[3, 2]):
        self.pin_counts = pin_counts_lib

    def legalize(self, M_continuous, P_continuous):
        print("\n[Legalizer] 启动物理网表坍缩 (Pin-Level Wavefunction Collapse)...")
        
        # 1. 离散化物理实现 (P_c)
        P_discrete = torch.argmax(P_continuous, dim=1).tolist()
        num_c = len(P_discrete)
        N = M_continuous.shape[0] # 总节点数
        
        # 2. 计算连向外部 Sink 的残余概率
        row_sums = torch.sum(M_continuous, dim=1, keepdim=True)
        sink_probs = torch.clamp(1.0 - row_sums, min=0.0).detach().numpy()
        M_cont_np = M_continuous.detach().numpy()
        
        # 3. 展开物理引脚 (构建二分图的目标集合)
        target_pins = []
        for j in range(num_c):
            # 无论 FA 还是 HA，A 和 B 引脚都必须连线
            target_pins.append(('comp', j, 'A', j * 3 + 0))
            target_pins.append(('comp', j, 'B', j * 3 + 1))
            # 只有被判定为 FA 的，才开放 CI 引脚接收连线
            if P_discrete[j] == 0: 
                target_pins.append(('comp', j, 'CI', j * 3 + 2))
                
        num_sink_pins = N - len(target_pins)
        if num_sink_pins < 0:
            raise ValueError("[致命错误] 节点数不足以填满当前的压缩器引脚需求！")
            
        for _ in range(num_sink_pins):
            target_pins.append(('sink', None, None, -1))
            
        # 4. 构建代价矩阵
        W = np.zeros((N, N))
        for i in range(N):
            for p_idx, target in enumerate(target_pins):
                target_type, j, pin_name, col_idx = target
                if target_type == 'comp':
                    W[i, p_idx] = M_cont_np[i, col_idx]
                else:
                    W[i, p_idx] = sink_probs[i, 0]
                
        # 5. 执行匈牙利算法
        print("[Legalizer] 正在运行 scipy.optimize.linear_sum_assignment (匈牙利算法)...")
        row_ind, col_ind = linear_sum_assignment(W, maximize=True)
        
        # 6. 重组离散的 0/1 拓扑矩阵
        M_discrete = torch.zeros_like(M_continuous)
        for i, p_idx in zip(row_ind, col_ind):
            target_type, j, pin_name, col_idx = target_pins[p_idx]
            if target_type == 'comp':
                M_discrete[i, col_idx] += 1.0 
                
        print("[Legalizer] Pin-Level 坍缩完成！获得了 100% 合法的 EDA 网表拓扑。")
        return M_discrete, P_discrete