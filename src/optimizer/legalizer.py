import torch
import numpy as np
from scipy.optimize import linear_sum_assignment

class DOMACLegalizer:
    def __init__(self):
        # 不再需要预定义引脚数量，一切由传入的 c_types 决定
        pass

    def legalize(self, M_continuous, P_continuous, c_types, dag_mask):
        """
        DOMAC 物理网表坍缩引擎 (Pin-Level Wavefunction Collapse)
        """
        print("\n[Legalizer] 启动物理网表坍缩...")
        
        # 1. 离散化物理实现 (仅仅是选择 D0, D1 等物理单元，不改变逻辑结构)
        #  论文明确指出对概率使用 argmax 操作来选择最高概率的实现
        P_discrete = torch.argmax(P_continuous, dim=1).tolist()
        num_c = len(P_discrete)
        N = M_continuous.shape[0] # 总节点数
        
        # 2. 计算连向外部 Sink (CPA) 的残余概率
        row_sums = torch.sum(M_continuous, dim=1, keepdim=True)
        sink_probs = torch.clamp(1.0 - row_sums, min=0.0).detach().cpu().numpy()
        M_cont_np = M_continuous.detach().cpu().numpy()
        dag_mask_np = dag_mask.detach().cpu().numpy() # 引入物理屏障
        
        # 3. 展开物理引脚 (构建二分图的目标集合)
        target_pins = []
        for j, c_type in enumerate(c_types):
            # 无论 FA 还是 HA，A 和 B 引脚都必须存在
            target_pins.append(('comp', j, 'A', j * 3 + 0))
            target_pins.append(('comp', j, 'B', j * 3 + 1))
            # 只有逻辑类型为 FA 的压缩器，才拥有 CI 引脚
            if c_type == 'FA': 
                target_pins.append(('comp', j, 'CI', j * 3 + 2))
                
        # 计算需要多少个虚拟 Sink 节点来吸收多余的信号
        num_sink_pins = N - len(target_pins)
        if num_sink_pins < 0:
            raise ValueError(f"[致命错误] 节点数({N})不足以填满当前的压缩器引脚需求({len(target_pins)})！请检查画布生成器。")
            
        for _ in range(num_sink_pins):
            target_pins.append(('sink', None, None, -1))
            
        # 4. 构建代价矩阵 (Cost Matrix)
        W = np.zeros((N, N))
        for i in range(N):
            for p_idx, target in enumerate(target_pins):
                target_type, j, pin_name, col_idx = target
                if target_type == 'comp':
                    # 【核心安全修正】：叠加上 DAG Mask 的限制
                    # 如果原拓扑图中这里被封印（-inf），那么代价直接赋极小值，阻止匹配
                    if dag_mask_np[i, col_idx] == float('-inf'):
                        W[i, p_idx] = -1e9
                    else:
                        W[i, p_idx] = M_cont_np[i, col_idx]
                else:
                    # Sink 通道永远畅通，直接使用流向 Sink 的概率
                    W[i, p_idx] = sink_probs[i, 0]
                
        # 5. 执行匈牙利算法 (Hungarian Algorithm)
        #  利用该算法寻找概率和最大的匹配方案
        print("[Legalizer] 正在运行 scipy.optimize.linear_sum_assignment (匈牙利算法)...")
        row_ind, col_ind = linear_sum_assignment(W, maximize=True)
        
        # 6. 重组纯净的 0/1 拓扑矩阵
        M_discrete = torch.zeros_like(M_continuous)
        sink_connections = 0
        
        for i, p_idx in zip(row_ind, col_ind):
            target_type, j, pin_name, col_idx = target_pins[p_idx]
            if target_type == 'comp':
                # 安全校验：确保算法没有被逼到绝路选了非法边
                if W[i, p_idx] <= -1e8:
                    raise RuntimeError(f"[物理崩塌] 节点 {i} 被强行连接到了非法的压缩器 {j} 的 {pin_name} 引脚！")
                M_discrete[i, col_idx] = 1.0 
            else:
                sink_connections += 1
                
        print(f"[Legalizer] 坍缩完成！{len(target_pins)-num_sink_pins} 根线接入压缩树，{sink_connections} 根线直通下游 CPA。")
        return M_discrete, P_discrete