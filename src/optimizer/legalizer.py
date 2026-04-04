import torch
import numpy as np
from scipy.optimize import linear_sum_assignment

class DOMACLegalizer:
    def legalize(self, local_M_probs, P_continuous, local_meta, num_pp, num_c):
        """
        局部坍缩与全局网表逆向编译引擎
        """
        print("\n[Legalizer] 启动微型矩阵局部坍缩...")
        P_discrete = torch.argmax(P_continuous, dim=1).tolist()
        
        discrete_local_M = []
        for M_ij in local_M_probs:
            M_np = M_ij.detach().cpu().numpy()
            # 针对局部小矩阵极速求解匈牙利算法
            row_ind, col_ind = linear_sum_assignment(M_np, maximize=True)
            M_disc = torch.zeros_like(M_ij)
            M_disc[row_ind, col_ind] = 1.0
            discrete_local_M.append(M_disc)
            
        print("[Legalizer] 局部坍缩完毕！正在启动路径追踪重组全局 RTL 网表...")
        total_nodes = num_pp + 2 * num_c
        global_M = torch.zeros((total_nodes, num_c * 3 + 1))
        
        # 溯源字典：记录虚拟线最终指向哪个真实的源头
        wire_source = {i: i for i in range(total_nodes)} 
        
        for M_disc, meta in zip(discrete_local_M, local_meta):
            in_wires = meta['in_wires']
            num_pins = meta['num_pins']
            
            for r, c in zip(*torch.where(M_disc == 1.0)):
                src_wire = in_wires[r.item()]
                true_src = wire_source[src_wire] 
                
                if c.item() < num_pins:
                    pin_global_idx = meta['pin_global_indices'][c.item()]
                    global_M[true_src, pin_global_idx] = 1.0
                else:
                    bypass_idx = c.item() - num_pins
                    bypass_wire_id = meta['out_bypass_ids'][bypass_idx]
                    wire_source[bypass_wire_id] = true_src
                    
        row_sums = torch.sum(global_M[:, :-1], dim=1)
        global_M[row_sums == 0, -1] = 1.0
        
        print(f"[Legalizer] 翻译完成，成功生成 VerilogGen 可读的全局拓扑。")
        return discrete_local_M, P_discrete, global_M