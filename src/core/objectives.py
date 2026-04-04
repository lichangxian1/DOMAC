import torch
import torch.nn as nn

class DOMACLossFunction(nn.Module):
    def __init__(self):
        super(DOMACLossFunction, self).__init__()

    def calc_performance_loss(self, wns, tns, area, glitch, t1, t2, alpha, beta):
        return t1 * wns + t2 * tns + alpha * area + beta * glitch
    
    def calc_bijective_mapping_loss_local(self, local_M_probs):
        """
        原汁原味的局部连线合法性：每个引脚和 Bypass 通道必须精准接收 1.0 的流量
        没有任何 0.5 陷阱！
        """
        l_bm = 0.0
        for M_ij in local_M_probs:
            col_sums = torch.sum(M_ij, dim=0)
            l_bm += torch.sum((col_sums - 1.0) ** 2)
        return l_bm
    
    def calc_discretization_loss(self, tensor_list):
        if isinstance(tensor_list, list):
            return sum(torch.sum((t ** 2) * ((1.0 - t) ** 2)) for t in tensor_list)
        return torch.sum((tensor_list ** 2) * ((1.0 - tensor_list) ** 2))

    def forward(self, wns, tns, area, glitch, local_M_probs, P_c, hyperparams, local_meta): 
        t1, t2, alpha, beta = hyperparams['t1'], hyperparams['t2'], hyperparams['alpha'], hyperparams.get('beta', 0.0)
        lambda1, lambda2 = hyperparams['lambda1'], hyperparams['lambda2']
        
        l_perf = self.calc_performance_loss(wns, tns, area, glitch, t1, t2, alpha, beta)
        l_bm = self.calc_bijective_mapping_loss_local(local_M_probs)
        
        l_d = self.calc_discretization_loss(local_M_probs) + self.calc_discretization_loss(P_c)
        
        l_bm_norm = l_bm / (l_bm.detach() + 1e-5)
        l_d_norm = l_d / (l_d.detach() + 1e-5)
        total_loss = l_perf + lambda1 * l_bm_norm + lambda2 * l_d_norm
        
        loss_dict = {
            'total_loss': total_loss, 'l_perf': l_perf, 'l_bm': l_bm, 'l_d': l_d,
            'l_sink': torch.tensor(0.0), 'actual_sink_count': 0, 'wns': wns, 'tns': tns, 'area': area, 'glitch': glitch
        }
        return total_loss, loss_dict