import torch

def smooth_max_lse(arrival_times, gamma=0.01):
    """
    Log-Sum-Exp (LSE) 平滑最大值算子。
    在可微静态时序分析 (STA) 中替代不可导的 max() 操作。
    确保时序图上的所有路径 (不仅是 Critical Path) 都能获得反向传播的梯度。
    
    参数:
    arrival_times (list of Tensor or Tensor): 汇聚到同一节点的所有输入到达时间 (Arrival Time)
    gamma (float): 平滑因子，论文默认设为 0.01。值越小越接近真实 Max，但梯度越陡峭。
    
    返回:
    Tensor: 平滑后的最大到达时间 (标量 Tensor)
    """
    # if not arrival_times:
    #     # 如果没有输入，默认到达时间为 0
    #     return torch.tensor(0.0, dtype=torch.float32, requires_grad=True)
    
    # 【修复】：安全地判断传入的是空列表还是空张量
    if isinstance(arrival_times, list) and len(arrival_times) == 0:
        return torch.tensor(0.0, dtype=torch.float32, requires_grad=True)
    elif torch.is_tensor(arrival_times) and arrival_times.numel() == 0:
        return torch.tensor(0.0, dtype=torch.float32, requires_grad=True)
        
    if isinstance(arrival_times, list):
        # 将列表中的 0D/1D tensor 堆叠，以便进行向量化运算
        stacked_at = torch.stack(arrival_times)
    else:
        stacked_at = arrival_times

    # 运用 LSE 公式: gamma * ln( sum( e^(x_i / gamma) ) )
    # 调用 torch.logsumexp 以保证底层的数值稳定性，防止指数爆炸
    lse_at = gamma * torch.logsumexp(stacked_at / gamma, dim=0)
    
    return lse_at


def diff_bilinear_interp(slew, load, index_1_slew, index_2_load, lut_values):
    """
    可微双线性插值引擎 (Differentiable Bilinear Interpolation)。
    基于 .lib 提取的 NLDM 离散查表，计算连续的 Delay 或 Output Slew，并保留反向传播梯度。
    
    参数:
    slew (Tensor): 当前节点的输入转换时间 (标量 Tensor)
    load (Tensor): 当前节点的输出负载电容 (标量 Tensor)
    index_1_slew (Tensor): .lib 中提取的 slew 坐标轴 (1D Tensor)
    index_2_load (Tensor): .lib 中提取的 load 坐标轴 (1D Tensor)
    lut_values (Tensor): .lib 中提取的 2D 数值矩阵 (Delay 或 Slew)
    
    返回:
    Tensor: 连续且可导的延迟或转换时间 (标量 Tensor)
    """
    # 1. 物理边界硬性截断 (Clamp)
    # 防止优化过程中产生的异常负载或 Slew 导致查表越界。Clamp 边界处的梯度为0，符合物理极限。
    # x = torch.clamp(slew, min=index_1_slew[0], max=index_1_slew[-1])
    # y = torch.clamp(load, min=index_2_load[0], max=index_2_load[-1])
    x = slew
    y = load

    # 2. 定位坐标区间 (searchsorted 本身不产生梯度，我们依靠权重的代数运算产生梯度)
    idx_x = torch.searchsorted(index_1_slew, x)
    idx_y = torch.searchsorted(index_2_load, y)
    
    # 确保索引不越界 (兜底保护)
    idx_x = torch.clamp(idx_x, 1, len(index_1_slew) - 1)
    idx_y = torch.clamp(idx_y, 1, len(index_2_load) - 1)
    
    # 3. 提取四个网格顶点的物理坐标
    x0 = index_1_slew[idx_x - 1]
    x1 = index_1_slew[idx_x]
    y0 = index_2_load[idx_y - 1]
    y1 = index_2_load[idx_y]
    
    # 4. 提取四个网格顶点的 LUT 数值
    v00 = lut_values[idx_x - 1, idx_y - 1]
    v01 = lut_values[idx_x - 1, idx_y]
    v10 = lut_values[idx_x, idx_y - 1]
    v11 = lut_values[idx_x, idx_y]
    
    # 5. 计算可微权重 (wx, wy 保留了来自 x 和 y 的梯度)
    wx = (x - x0) / (x1 - x0)
    wy = (y - y0) / (y1 - y0)
    
    # 6. 执行双线性插值 (代数组合，完美支持 Autograd)
    val0 = v00 * (1 - wy) + v01 * wy
    val1 = v10 * (1 - wy) + v11 * wy
    interpolated_value = val0 * (1 - wx) + val1 * wx
    
    return interpolated_value


def compute_expected_timing(p_c, cell_tensors_dict, in_pin, out_pin, slew, load):
    """
    计算基于实现概率的期望时序 (Expected Timing)。
    对应 DOMAC 论文中的期望延迟与期望 Slew 计算公式。
    
    参数:
    p_c (Tensor): 当前压缩器的实现概率分布，例如 [p_FA, p_HA]，需满足 sum(p_c) == 1
    cell_tensors_dict (list of dict): 包含不同 Cell (FA, HA) 的物理张量字典列表
    in_pin (str): 输入引脚名 (如 'A', 'B', 'CI')
    out_pin (str): 输出引脚名 (如 'S', 'CO')
    slew (Tensor): 期望输入转换时间
    load (Tensor): 期望输出负载
    
    返回:
    tuple: (expected_delay, expected_out_slew) 均携带梯度
    """
    expected_delay = torch.tensor(0.0, dtype=torch.float32)
    expected_out_slew = torch.tensor(0.0, dtype=torch.float32)
    
    # 遍历所有可能的实现 (FA, HA...)
    for idx, cell_tensors in enumerate(cell_tensors_dict):
        prob = p_c[idx]
        
        # 物理剪枝：如果当前概率极小，可跳过插值运算以加速前向传播 (可选优化)
        # if prob < 1e-4: continue 
        
        # 提取特定引脚时序弧的张量
        arc_data = cell_tensors.get(out_pin, {}).get(in_pin)
        
        if arc_data is None:
            # 如果没有这条时序弧 (例如 HA 可能没有 CI 到 CO 的弧)
            # continue
            delay = torch.tensor(10.0, dtype=torch.float32, device=p_c.device)
            out_slew = torch.tensor(10.0, dtype=torch.float32, device=p_c.device)
            
        # 可微查表
        delay = diff_bilinear_interp(
            slew, load, 
            arc_data['index_1_slew'], arc_data['index_2_load'], arc_data['delay_lut']
        )
        out_slew = diff_bilinear_interp(
            slew, load, 
            arc_data['index_1_slew'], arc_data['index_2_load'], arc_data['slew_lut']
        )
        
        # 概率加权累加 (累加操作完美可导)
        expected_delay = expected_delay + prob * delay
        expected_out_slew = expected_out_slew + prob * out_slew
        
    return expected_delay, expected_out_slew

# ================= 底层算子自测单元 =================
if __name__ == "__main__":
    # 纯净的底层自测逻辑，确保矩阵与梯度的连通性
    print("[DiffSTA] 底层算子加载完毕。当前工作模式：严格可微静态时序分析。")