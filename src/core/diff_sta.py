# ============================================================
# 替换 src/core/diff_sta.py 全文
# ============================================================
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


def leaky_clamp(tensor, min_val, max_val, leak=0.01):
    """
    带泄漏的软截断：边界内原样返回，边界外保留leak比例的线性梯度。
    防止超出LUT范围时梯度彻底消失，同时限制外推幅度。
    """
    clamped = torch.clamp(tensor, min_val, max_val)
    return clamped + leak * (tensor - clamped)


def diff_bilinear_interp(slew, load, index_1_slew, index_2_load, lut_values):
    """
    可微双线性插值，支持 lut_values 为 [num_impls, R, C] 的3D批量查表。
    使用 Leaky Clamp 保证边界外梯度存活，Hard Clamp 保证索引安全。
    """
    x_min, x_max = index_1_slew[0], index_1_slew[-1]
    y_min, y_max = index_2_load[0], index_2_load[-1]

    # 1. 带梯度的软截断值（用于计算插值权重wx, wy）
    x_safe = leaky_clamp(slew, x_min, x_max)
    y_safe = leaky_clamp(load, y_min, y_max)

    # 2. 无梯度的硬截断值（仅用于searchsorted找索引，detach切断无意义的追踪）
    x_idx_target = torch.clamp(slew, x_min, x_max).detach()
    y_idx_target = torch.clamp(load, y_min, y_max).detach()

    idx_x = torch.searchsorted(index_1_slew, x_idx_target)
    idx_y = torch.searchsorted(index_2_load, y_idx_target)

    idx_x = torch.clamp(idx_x, 1, len(index_1_slew) - 1)
    idx_y = torch.clamp(idx_y, 1, len(index_2_load) - 1)

    x0 = index_1_slew[idx_x - 1]
    x1 = index_1_slew[idx_x]
    y0 = index_2_load[idx_y - 1]
    y1 = index_2_load[idx_y]

    # 3. 用x_safe/y_safe计算权重，保证梯度流通
    wx = (x_safe - x0) / (x1 - x0)
    wy = (y_safe - y0) / (y1 - y0)

    v00 = lut_values[..., idx_x - 1, idx_y - 1]
    v01 = lut_values[..., idx_x - 1, idx_y]
    v10 = lut_values[..., idx_x, idx_y - 1]
    v11 = lut_values[..., idx_x, idx_y]

    val0 = v00 * (1 - wy) + v01 * wy
    val1 = v10 * (1 - wy) + v11 * wy

    result = val0 * (1 - wx) + val1 * wx

    # 4. 绝对物理下限：防止Leaky外推产生负延迟
    return torch.clamp(result, min=0.0)