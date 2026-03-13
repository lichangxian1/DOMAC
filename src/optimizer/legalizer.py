import torch
import numpy as np
from scipy.optimize import linear_sum_assignment

class DOMACLegalizer:
    def __init__(self, pin_counts_lib=[3, 2]):
        """
        DOMAC 合法化引擎
        利用匈牙利算法解决二分图最大权匹配，将概率拓扑映射为纯血 EDA 网表。
        """
        self.pin_counts = pin_counts_lib

    def legalize(self, M_continuous, P_continuous):
        """
        执行离散化坍缩
        
        参数:
        M_continuous (Tensor): 连续的内部连接概率矩阵 [total_nodes, num_c]
        P_continuous (Tensor): 连续的实现概率矩阵 [num_c, num_impls]
        
        返回:
        M_discrete (Tensor), P_discrete (list): 绝对纯净的 0/1 矩阵和实现列表
        """
        print("\n[Legalizer] 启动物理网表坍缩 (Wavefunction Collapse)...")
        
        # ================= 1. 离散化物理实现 (P_c) =================
        # 对每一个压缩器，直接取概率最大的实现方式 (Argmax)
        # 比如 0 代表 FA, 1 代表 HA
        P_discrete = torch.argmax(P_continuous, dim=1).tolist()
        
        # ================= 2. 重构完整的 M 矩阵 (包含 Sink) =================
        # M_continuous 只包含内部连接。根据行和为 1 的法则，推导出连向外部输出(Sink)的概率
        row_sums = torch.sum(M_continuous, dim=1, keepdim=True)
        sink_probs = torch.clamp(1.0 - row_sums, min=0.0)
        M_full = torch.cat([M_continuous, sink_probs], dim=1).detach().numpy()
        
        N = M_full.shape[0]     # 总节点数 (源)
        num_c = M_full.shape[1] - 1 # 内部压缩器数量
        
        # ================= 3. 展开物理引脚 (构建二分图的目标集合) =================
        target_pins = []
        
        # 依据刚刚确定的离散 P_discrete，动态生成内部引脚坑位
        for j in range(num_c):
            needed_pins = self.pin_counts[P_discrete[j]]
            for _ in range(needed_pins):
                target_pins.append(('comp', j)) # 标记为：连向内部第 j 个压缩器
                
        # 计算剩余的线，全部归入外部输出引脚 (Sink)
        num_sink_pins = N - len(target_pins)
        if num_sink_pins < 0:
            raise ValueError("[致命错误] 节点数不足以填满当前的压缩器引脚需求！")
            
        for _ in range(num_sink_pins):
            target_pins.append(('sink', num_c))
            
        # ================= 4. 构建代价矩阵 (Cost Matrix) =================
        # W 矩阵的行是 Source，列是展开后的特定 Pin
        W = np.zeros((N, N))
        for i in range(N):
            for p_idx, target in enumerate(target_pins):
                target_type, j = target
                # 取出神经网络计算出的那条“软连接”概率作为匹配权重
                W[i, p_idx] = M_full[i, j]
                
        # ================= 5. 执行匈牙利算法 =================
        # 寻找最大概率和的绝对匹配方案 (maximize=True)
        print("[Legalizer] 正在运行 scipy.optimize.linear_sum_assignment (匈牙利算法)...")
        row_ind, col_ind = linear_sum_assignment(W, maximize=True)
        
        # ================= 6. 重组离散的 0/1 拓扑矩阵 =================
        M_discrete = torch.zeros_like(M_continuous)
        
        for i, p_idx in zip(row_ind, col_ind):
            target_type, j = target_pins[p_idx]
            if target_type == 'comp':
                M_discrete[i, j] += 1.0 # 物理连线建立
                
        # 校验：检查是否有非法多连
        if torch.max(M_discrete) > 1.0:
            print("[警告] 同一源节点向同一压缩器连接了多根线 (短接)，这在某些综合工具中可能需要 Buffer 隔离。")
            
        print("[Legalizer] 坍缩完成！获得了 100% 合法的 EDA 网表拓扑。")
        return M_discrete, P_discrete