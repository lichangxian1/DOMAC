import os
import sys
import torch
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.parser.lib_parser import NLDMParser
from src.core.compressor_tree import DOMAC_CompressorTree
from src.core.objectives import DOMACLossFunction
from src.optimizer.train import DOMACTrainer
from src.optimizer.legalizer import DOMACLegalizer
from src.export.verilog_gen import VerilogGenerator

def create_physical_tensor_mock():
    idx_slew = torch.tensor([0.005, 0.01, 0.02, 0.04, 0.08, 0.16, 0.32], dtype=torch.float32)
    idx_load = torch.tensor([0.001, 0.002, 0.004, 0.008, 0.016, 0.032, 0.064], dtype=torch.float32)
    
    fa_delay_lut = torch.linspace(0.05, 0.20, 49).view(7, 7) 
    ha_delay_lut = torch.linspace(0.03, 0.15, 49).view(7, 7) 
    slew_lut = torch.linspace(0.01, 0.10, 49).view(7, 7)
    
    fa_base = {'cell_area': 2.5, 'S': {'A': {'index_1_slew': idx_slew, 'index_2_load': idx_load, 'delay_lut': fa_delay_lut, 'slew_lut': slew_lut}}, 'CO': {'A': {'index_1_slew': idx_slew, 'index_2_load': idx_load, 'delay_lut': fa_delay_lut, 'slew_lut': slew_lut}}}
    ha_base = {'cell_area': 1.8, 'S': {'A': {'index_1_slew': idx_slew, 'index_2_load': idx_load, 'delay_lut': ha_delay_lut, 'slew_lut': slew_lut}}, 'CO': {'A': {'index_1_slew': idx_slew, 'index_2_load': idx_load, 'delay_lut': ha_delay_lut, 'slew_lut': slew_lut}}}
    
    # 模拟返回多个物理实现的库：3种FA，2种HA
    return [fa_base, fa_base, fa_base], [ha_base, ha_base]

def generate_multiplier_canvas(bit_width):
    print(f"\n[Canvas Generator] 自动推演 {bit_width}x{bit_width} 乘法器画布...")
    pp_cols = []
    max_cols = bit_width * 2 - 1
    dots_in_col = [0] * max_cols
    
    for i in range(bit_width):
        for j in range(bit_width):
            col = i + j
            pp_cols.append(col)
            dots_in_col[col] += 1
            
    print(f" -> 共 {len(pp_cols)} 个 PP 节点。各列点数分布: {dots_in_col}")
    
    comp_cols = []
    c_types = []
    current_dots = list(dots_in_col)
    
    for col in range(max_cols):
        while current_dots[col] > 2:
            comp_cols.append(col) 
            c_types.append('FA') # 默认申请 FA 坑位
            current_dots[col] -= 3 
            current_dots[col] += 1 
            if col + 1 < max_cols:
                current_dots[col + 1] += 1 
                
    print(f" -> 申请 {len(comp_cols)} 个压缩器画布。")
    return sorted(pp_cols), sorted(comp_cols), c_types

def main():
    print("="*60)
    print(" [DOMAC 净室复现] TSMC 28nm 节点可微 STA 优化框架")
    print("="*60)
    
    TARGET_CELLS = [
        'FA1D0BWP12T40P140', 'FA1D1BWP12T40P140', 'FA1D2BWP12T40P140', 'FA1D4BWP12T40P140',
        'HA1D0BWP12T40P140', 'HA1D1BWP12T40P140', 'HA1D2BWP12T40P140', 'HA1D4BWP12T40P140'
    ]
    
    # 提前准备好物理名字，用于最终生成 Verilog
    fa_names = [c for c in TARGET_CELLS if c.startswith('FA')]
    ha_names = [c for c in TARGET_CELLS if c.startswith('HA')]
    
    try:
        lib_path = "/home/changxian/library/t28_official/tcbn28hpcplusbwp12t40p140tt0p9v25c.lib"
        if os.path.exists(lib_path):
            print("[System] 发现 PDK 物理库，启动解析...")
            parser = NLDMParser(lib_path, TARGET_CELLS)
            nldm_db = parser.parse()
            fa_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('FA') and c in nldm_db]
            ha_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('HA') and c in nldm_db]
        else:
            raise FileNotFoundError
    except Exception as e:
        print(f"\n[System] PDK 异常，切换【物理对齐 Mock 模式】...")
        fa_tensors, ha_tensors = create_physical_tensor_mock()
        # Mock 模式下必须伪造同样数量的名字给 Verilog 生成器，否则会越界崩溃
        fa_names = [f"Mock_FA_Impl_{i}" for i in range(len(fa_tensors))]
        ha_names = [f"Mock_HA_Impl_{i}" for i in range(len(ha_tensors))]

    BIT_WIDTH = 16
    PP_COLS, COMP_COLS, C_TYPES = generate_multiplier_canvas(BIT_WIDTH)
    NUM_PP = len(PP_COLS)
    NUM_COMPRESSORS = len(COMP_COLS)

    # pp_at = torch.linspace(0.0, 0.1, NUM_PP) 
    # pp_slew = torch.full((NUM_PP,), 0.05)
    # REQ_TIME = 0.1 
    # print("REQ_TIME：" + str(REQ_TIME))

    # print(f"\n[Engine] 构建异构可微压缩树...")
    # model = DOMAC_CompressorTree(PP_COLS, COMP_COLS, fa_tensors, ha_tensors, C_TYPES, REQ_TIME)

    # loss_engine = DOMACLossFunction()
    # trainer = DOMACTrainer(model, loss_engine, lr=0.05)
    
    # print("\n[Engine] 物理映射与梯度反向传播开始...")
    
    # start_time = time.time()
    # final_M, final_P = trainer.train(pp_at, pp_slew, max_epochs=300)
    # ================= [GPU 核动力点火] =================
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\n[System] 核心计算引擎将挂载至: {device}")
    if torch.cuda.is_available():
        print(f" -> 检测到显卡: {torch.cuda.get_device_name(0)}")
        # 为了极速性能，开启 CuDNN 基准测试加速
        torch.backends.cudnn.benchmark = True 

    # 1. 初始信号输入必须在显存上创建
    pp_at = torch.linspace(0.0, 0.1, NUM_PP, device=device) 
    pp_slew = torch.full((NUM_PP,), 0.05, device=device)
    REQ_TIME = 0.1 
    print("REQ_TIME：" + str(REQ_TIME))

    print(f"\n[Engine] 构建异构可微压缩树...")
    # 2. 传递 device 给模型，并强制模型所有 Parameter 和 Buffer 上 GPU
    model = DOMAC_CompressorTree(PP_COLS, COMP_COLS, fa_tensors, ha_tensors, C_TYPES, REQ_TIME, device=device).to(device)

    loss_engine = DOMACLossFunction()
    trainer = DOMACTrainer(model, loss_engine, lr=0.05)
    
    print("\n[Engine] 物理映射与梯度反向传播开始...")
    
    start_time = time.time()
    final_M, final_P = trainer.train(pp_at, pp_slew, max_epochs=300)
    
    print("\n[System] 优化执行完毕！网表拓扑已坍缩至离散界限附近。")
    
    # ================= [新增联调区块：全自动生成网表] =================
    
    # 1. 启动合法化器 (离散坍缩)
    legalizer = DOMACLegalizer()
    discrete_M, discrete_P = legalizer.legalize(final_M, final_P, C_TYPES, model.dag_mask)
    
    # # ================= [新增：Dr. Gemini 的矩阵透视镜] =================
    # # 临时修改 PyTorch 的打印选项，防止矩阵被折叠省略，保留 4 位小数以便观察概率分布
    # torch.set_printoptions(precision=4, sci_mode=False, linewidth=150, profile="full")
    
    # print("\n" + "="*60)
    # print(" 🔍 [矩阵透视] 连续概率态 vs 物理离散态")
    # print("="*60)
    
    # print(f"\n1. [连续概率态] 物理实现矩阵 P_c (Shape: {final_P.shape}):")
    # print("   (行代表 6 台压缩器，列代表 8 种物理门选项的选中概率)")
    # print(final_P)
    
    # print("\n2. [离散坍缩态] 最终选定的物理门索引 P_discrete:")
    # print(f"   {discrete_P}")
    
    # print(f"\n3. [连续概率态] 互连拓扑矩阵 M_internal (Shape: {final_M.shape}):")
    # print("   (行代表 28 个物理节点，列代表 18 个压缩器靶点引脚的连线概率)")
    # print(final_M)
    
    # print(f"\n4. [离散坍缩态] 合法化后的纯 0/1 拓扑矩阵 discrete_M (Shape: {discrete_M.shape}):")
    # print("   (这就是最终喂给 Verilog 的纯血 EDA 布线图)")
    # print(discrete_M)
    
    # print("="*60 + "\n")
    # # 恢复 PyTorch 默认打印截断（可选）
    # torch.set_printoptions(profile="default")
    # # ===================================================================

    # 2. 启动 Verilog 打印机
    # 确保输出目录存在
    os.makedirs("output/netlists", exist_ok=True)
    
    v_gen = VerilogGenerator(
        pp_cols=PP_COLS,       # <--- 新增传入参数
        c_cols=COMP_COLS,      # <--- 新增传入参数
        c_types=C_TYPES,
        fa_cell_names=fa_names,
        ha_cell_names=ha_names
    )
    
    netlist_path = "output/netlists/domac_result.v"
    tb_path = "output/netlists/tb_domac.v"
    
    v_gen.generate(discrete_M, discrete_P, output_file=netlist_path)
    v_gen.generate_testbench(tb_file=tb_path, netlist_file=netlist_path)
    
    end_time = time.time()
    print("="*60)
    print(f" [任务完成] 全流程跑通，总耗时: {end_time - start_time:.2f} 秒")
    print(f" 请前往 output/netlists/domac_result.v 查看流片网表。")
    print("="*60)

if __name__ == "__main__":
    # 开启 PyTorch 的异常检测，用于排查任何可能的梯度断裂
    # torch.autograd.set_detect_anomaly(True)
    main()