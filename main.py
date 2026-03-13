import os
import sys
import torch
import time

# 强制将当前目录加入环境变量，解决 src 模块导入问题
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.parser.lib_parser import NLDMParser
from src.core.compressor_tree import DOMAC_CompressorTree
from src.core.objectives import DOMACLossFunction
from src.optimizer.train import DOMACTrainer

def create_physical_tensor_mock():
    """
    构建符合 TSMC 28nm 解析器输出格式的 Mock 物理张量字典。
    用于验证网络的前向/反向传播图是否绝对连通。
    """
    # 模拟坐标轴: Slew (7个点), Load (7个点)
    idx_slew = torch.tensor([0.005, 0.01, 0.02, 0.04, 0.08, 0.16, 0.32], dtype=torch.float32)
    idx_load = torch.tensor([0.001, 0.002, 0.004, 0.008, 0.016, 0.032, 0.064], dtype=torch.float32)
    
    # 构建 7x7 模拟延迟矩阵 (FA 较慢，HA 较快)
    fa_delay_lut = torch.linspace(0.05, 0.20, 49).view(7, 7) # FA 延迟范围 50ps - 200ps
    ha_delay_lut = torch.linspace(0.03, 0.15, 49).view(7, 7) # HA 延迟范围 30ps - 150ps
    
    # 转换时间矩阵
    slew_lut = torch.linspace(0.01, 0.10, 49).view(7, 7)
    
    # 按照 lib_parser.py 的输出字典结构组装
    # 结构: dict[out_pin][in_pin] -> arc_tensors
    fa_tensors = {
        'S': {
            'A': {
                'index_1_slew': idx_slew, 'index_2_load': idx_load,
                'delay_lut': fa_delay_lut, 'slew_lut': slew_lut
            }
        }
    }
    
    ha_tensors = {
        'S': {
            'A': {
                'index_1_slew': idx_slew, 'index_2_load': idx_load,
                'delay_lut': ha_delay_lut, 'slew_lut': slew_lut
            }
        }
    }
    
    return [fa_tensors, ha_tensors]

def main():
    print("="*60)
    print(" [DOMAC 净室复现] TSMC 28nm 节点可微 STA 优化框架")
    print("="*60)
    
    # 1. 物理环境初始化
    try:
        # 这里你可以替换为你真实的 TSMC 28nm 路径
        lib_path = "/home/changxian/library/t28_official/tcbn28hpcplusbwp12t40p140tt0p9v25c.lib"
        target_cells = ['FA1D1BWP12T40P140', 'HA1D1BWP12T40P140']
        
        if os.path.exists(lib_path):
            print("[System] 检测到真实 PDK 物理库，启动流式解析...")
            parser = NLDMParser(lib_path, target_cells)
            nldm_db = parser.parse()
            cell_tensors = [nldm_db[target_cells[0]], nldm_db[target_cells[1]]]
        else:
            raise FileNotFoundError
    except Exception as e:
        import traceback
        print(f"\n[致命错误] 解析真实物理库时发生崩溃，原因: {e}")
        traceback.print_exc()  # 打印完整的崩溃追踪栈
        print("[System] 强制切换至【物理对齐 Mock 模式】...")
        cell_tensors = create_physical_tensor_mock()

    # 2. 硬件架构超参数定义
    # ================= [新增算术拓扑定义] =================
    # 我们模拟一个真实的乘法器部分积列分布 (例如 8个PP，分布在 0~3 列)
    PP_COLS = [0, 0, 1, 1, 1, 2, 2, 3] 
    
    # 我们投放 6 个压缩器坑位，预先分配给对应的列去处理
    COMP_COLS = [0, 1, 1, 2, 2, 3]
    
    NUM_PP = len(PP_COLS)
    NUM_COMPRESSORS = len(COMP_COLS)
    
    # 打破时序对称性死锁！为不同的 PP 注入 0.0 到 0.1ns 的到达时间阶梯
    pp_at = torch.linspace(0.0, 0.1, NUM_PP) 
    pp_slew = torch.full((NUM_PP,), 0.05)
    # ========================================================
    REQ_TIME = 0.1 # 约束时间 0.5ns (500ps)
    
    # 初始化部分积的到达时间和转换时间 (全0起步)
    pp_at = torch.zeros(NUM_PP, dtype=torch.float32)
    pp_slew = torch.full((NUM_PP,), 0.01, dtype=torch.float32)

    # 3. 实例化 DOMAC 核心引擎
    print(f"\n[Engine] 正在构建可微压缩树 (PP={NUM_PP}, Compressors={NUM_COMPRESSORS})...")
    # model = DOMAC_CompressorTree(
    #     num_pp=NUM_PP, 
    #     num_compressors=NUM_COMPRESSORS, 
    #     cell_tensors=cell_tensors, 
    #     req_time=REQ_TIME
    # )
    model = DOMAC_CompressorTree(PP_COLS, COMP_COLS, cell_tensors, REQ_TIME)

    # 4. 实例化目标函数与约束场
    # pin_counts_lib=[3.0, 2.0] 代表 FA 需要 3 个输入，HA 需要 2 个输入
    loss_engine = DOMACLossFunction(pin_counts_lib=[3.0, 2.0])
    
    # 5. 实例化训练器
    trainer = DOMACTrainer(model, loss_engine, lr=0.05)
    
    # 6. 启动优化循环
    print("\n[Engine] 物理映射与梯度反向传播测试开始...")
    start_time = time.time()
    
    final_M, final_P = trainer.train(pp_at, pp_slew, max_epochs=300)
    
    # 引入合法化器
    from src.optimizer.legalizer import DOMACLegalizer
    
    legalizer = DOMACLegalizer(pin_counts_lib=[3, 2])
    discrete_M, discrete_P = legalizer.legalize(final_M, final_P)
    
    print("\n================ 最终交付：纯血物理网表 ================")
    print("各压缩器最终实现类型 (0=FA, 1=HA):")
    print(discrete_P)
    
    print("\n离散化后的内部布线拓扑 (M矩阵，仅包含 0 和 1):")
    print(discrete_M)
    
    # 物理合法性终极断言
    print("\n[物理规则终极断言]")
    col_sums = torch.sum(discrete_M, dim=0).tolist()
    for j, (p_type, actual_pins) in enumerate(zip(discrete_P, col_sums)):
        expected = 3 if p_type == 0 else 2
        print(f"压缩器 {j}: 类型={'FA' if p_type==0 else 'HA'} -> 需要引脚: {expected}, 实际连线数: {int(actual_pins)} " + 
              (" [合法] ✓" if expected == actual_pins else " [非法] ❌"))
    
    # === 将以下代码加在 "[物理规则终极断言]" 的 for 循环之后 ===
    
    from src.export.verilog_gen import VerilogGenerator
    
    v_gen = VerilogGenerator(num_pp=NUM_PP, num_c=NUM_COMPRESSORS)
    # 调用生成器，将张量彻底转化为硅基语言
    v_gen.generate(discrete_M, discrete_P, output_file="output/netlists/domac_result.v")

    end_time = time.time()
    print(f"\n[System] 优化执行完毕，耗时: {end_time - start_time:.2f} 秒")
    
    print("\n[Result] 最终收敛的物理单元选择矩阵 P_c (局部):")
    print(final_P[:3, :]) # 打印前3个压缩器的实现概率 (列0: FA, 列1: HA)
    
    print("\n[Result] 最终收敛的拓扑连接概率矩阵 M (局部):")
    print(final_M[:5, :3]) # 打印前5个源节点连接到前3个压缩器的概率

if __name__ == "__main__":
    # 开启 PyTorch 的异常检测，任何不可导的非法操作都会直接报错抛出
    torch.autograd.set_detect_anomaly(True)
    main()