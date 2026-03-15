import torch

def smooth_max_lse(arrival_times, gamma=0.01):
    if isinstance(arrival_times, list) and len(arrival_times) == 0:
        return torch.tensor(0.0, dtype=torch.float32, requires_grad=True)
    elif torch.is_tensor(arrival_times) and arrival_times.numel() == 0:
        return torch.tensor(0.0, dtype=torch.float32, requires_grad=True)
        
    if isinstance(arrival_times, list):
        stacked_at = torch.stack(arrival_times)
    else:
        stacked_at = arrival_times

    lse_at = gamma * torch.logsumexp(stacked_at / gamma, dim=0)
    return lse_at


def diff_bilinear_interp(slew, load, index_1_slew, index_2_load, lut_values):
    """
    终极张量广播版：可微双线性插值
    完美支持 lut_values 形状为 [num_impls, 7, 7] 的 3D 张量批处理查表！
    """
    x_min, x_max = index_1_slew[0], index_1_slew[-1]
    y_min, y_max = index_2_load[0], index_2_load[-1]
    
    x = torch.clamp(slew, min=x_min, max=x_max)
    y = torch.clamp(load, min=y_min, max=y_max)

    idx_x = torch.searchsorted(index_1_slew, x)
    idx_y = torch.searchsorted(index_2_load, y)
    
    idx_x = torch.clamp(idx_x, 1, len(index_1_slew) - 1)
    idx_y = torch.clamp(idx_y, 1, len(index_2_load) - 1)
    
    x0 = index_1_slew[idx_x - 1]
    x1 = index_1_slew[idx_x]
    y0 = index_2_load[idx_y - 1]
    y1 = index_2_load[idx_y]
    
    # 利用 ... (Ellipsis) 完美兼容 2D [7,7] 和 3D [N,7,7] 张量！
    v00 = lut_values[..., idx_x - 1, idx_y - 1]
    v01 = lut_values[..., idx_x - 1, idx_y]
    v10 = lut_values[..., idx_x, idx_y - 1]
    v11 = lut_values[..., idx_x, idx_y]
    
    wx = (x - x0) / (x1 - x0)
    wy = (y - y0) / (y1 - y0)
    
    val0 = v00 * (1 - wy) + v01 * wy
    val1 = v10 * (1 - wy) + v11 * wy
    
    return val0 * (1 - wx) + val1 * wx