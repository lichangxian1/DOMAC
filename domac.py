import os
import sys
import torch
import time
import subprocess

torch.set_num_threads(1)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.parser.lib_parser import NLDMParser
from src.core.compressor_tree import DOMAC_CompressorTree
from src.core.objectives import DOMACLossFunction
from src.optimizer.train import DOMACTrainer
from src.optimizer.legalizer import DOMACLegalizer
from src.export.verilog_gen import VerilogGenerator

# ================= [引入剥离出去的核心组件与探针] =================
from src.core.domac_utils import (
    create_physical_tensor_mock, 
    generate_multiplier_canvas, 
    generate_dadda_init_matrix,
    probe_column_height_overflow,
    probe_post_legalization_eval,
    probe_wavefront_at
)

def main():
    print("="*60)
    print(" [DOMAC 净室复现] TSMC 28nm 节点可微 STA 优化框架")
    print("="*60)
    
    INIT_MODE = 'blank'  # 可选 'dadda' 或 'blank'，分别对应 Dadda 热启动和纯随机冷启动
    
    # TARGET_CELLS = [
    #     'FA1D0BWP12T40P140',
    #     'HA1D0BWP12T40P140',
    # ]
    TARGET_CELLS = ['FA1D0BWP12T40P140', 'HA1D0BWP12T40P140','FA1D1BWP12T40P140', 'HA1D1BWP12T40P140','FA1D2BWP12T40P140', 'HA1D2BWP12T40P140','FA1D4BWP12T40P140', 'HA1D4BWP12T40P140']
    
    fa_names = [c for c in TARGET_CELLS if c.startswith('FA')]
    ha_names = [c for c in TARGET_CELLS if c.startswith('HA')]
    
    try:
        lib_path = "/home/changxian/library/t28_official/tcbn28hpcplusbwp12t40p140tt0p9v25c.lib"
        if os.path.exists(lib_path):
            print("[System] 发现 PDK 物理库，启动解析...")
            parser = NLDMParser(lib_path, TARGET_CELLS)
            nldm_db = parser.parse()

            print("\n" + "="*60)
            print(" 📊 [物理数据核对] 提取的 Area, Cap 与 Delay 全景概览")
            print("="*60)
            for cell in TARGET_CELLS:
                if cell in nldm_db:
                    area = nldm_db[cell].get('cell_area', 'N/A')
                    print(f"[{cell}]")
                    print(f"  -> 面积 (Area): {area} μm²")
                    
                    if 'pin_cap' in nldm_db[cell]:
                        print(f"  -> 引脚输入电容 (Input Capacitance):")
                        for pin, cap in nldm_db[cell]['pin_cap'].items():
                            print(f"     * {pin:<3} : {cap:.6f} pF") 
                    else:
                        print(f"  -> [Warning] 未发现引脚电容数据！")
                    
                    for out_pin in ['S', 'CO']:
                        if out_pin in nldm_db[cell]:
                            for in_pin in ['A', 'B', 'CI']:
                                if in_pin in nldm_db[cell][out_pin]:
                                    arc_data = nldm_db[cell][out_pin][in_pin]
                                    delay_lut = arc_data.get('delay_lut')
                                    if delay_lut is not None:
                                        print(f"  -> {in_pin} -> {out_pin:<2} 延迟极限: {delay_lut.min().item():.5f} ~ {delay_lut.max().item():.5f} ns")
                    print("-" * 40)
            print("="*60 + "\n")
            
            fa_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('FA') and c in nldm_db]
            ha_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('HA') and c in nldm_db]
        else:
            raise FileNotFoundError(f"找不到指定的工艺库文件: {lib_path}")
    except Exception as e:
        print(f"\n[Fatal Error] 系统初始化失败，拒绝以非严谨模式运行。原因: {e}")
        sys.exit(1)
        
    BIT_WIDTH = 12
    TARGET_SINK_COUNT = (BIT_WIDTH * 2 - 1) * 2
    # 接收包含物理延迟的 4 个返回值
    PP_COLS, COMP_COLS, C_TYPES, PP_AT_INIT = generate_multiplier_canvas(BIT_WIDTH)
    NUM_PP = len(PP_COLS)
    NUM_COMPRESSORS = len(COMP_COLS)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\n[System] 核心计算引擎将挂载至: {device}")
    if torch.cuda.is_available():
        print(f" -> 检测到显卡: {torch.cuda.get_device_name(0)}")
        torch.backends.cudnn.benchmark = True 

    # 【核心修复】将真实物理延迟作为 Tensor 喂给 AI
    pp_at = torch.tensor(PP_AT_INIT, dtype=torch.float32, device=device)
    pp_slew = torch.full((NUM_PP,), 0.02, device=device)
    REQ_TIME = 0 
    print("REQ_TIME：" + str(REQ_TIME))

    print(f"\n[Engine] 构建异构可微压缩树...")
    max_impls = max(len(fa_tensors), len(ha_tensors))
    BASELINE_GATE_INDEX = 1 
    safe_gate_idx = BASELINE_GATE_INDEX if max_impls > BASELINE_GATE_INDEX else 0

    if INIT_MODE == 'dadda':
        print(f" -> [Init] 采用 Dadda 树先验知识热启动 (物理门初始尺寸: D{safe_gate_idx})")
        init_m = generate_dadda_init_matrix(BIT_WIDTH, PP_COLS, COMP_COLS, C_TYPES)
        init_p = torch.zeros((NUM_COMPRESSORS, max_impls))
        init_p[:, safe_gate_idx] = 10.0  
        
        discrete_init_M = torch.zeros_like(init_m)
        discrete_init_M[:, :-1] = (init_m[:, :-1] == 10.0).float() 
        discrete_init_P = [safe_gate_idx] * NUM_COMPRESSORS

    elif INIT_MODE == 'blank':
        # print(f" -> [Init] 采用等概率全零矩阵冷启动 (无先验知识)")
        # total_nodes = NUM_PP + 2 * NUM_COMPRESSORS
        # total_target_pins = NUM_COMPRESSORS * 3
        # init_m = torch.zeros((total_nodes, total_target_pins + 1))
        # init_p = torch.zeros((NUM_COMPRESSORS, max_impls))
        
        print(f" -> [Init] 采用纯随机高斯噪声冷启动 (打破拓扑对称性)")
        total_nodes = NUM_PP + 2 * NUM_COMPRESSORS
        total_target_pins = NUM_COMPRESSORS * 3
        # 【致命修复】绝不能用 zeros！必须用正态分布噪声打破梯度对称性
        FIXED_SEED = 42 
        torch.manual_seed(FIXED_SEED)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(FIXED_SEED)
        init_m = torch.randn((total_nodes, total_target_pins + 1)) * 0.01
        init_p = torch.zeros((NUM_COMPRESSORS, max_impls))
        
    else:
        raise ValueError(f"[Fatal] 未知的初始化模式: {INIT_MODE}")
        
    model = DOMAC_CompressorTree(
        PP_COLS, COMP_COLS, fa_tensors, ha_tensors, C_TYPES, REQ_TIME, 
        device=device,
        init_m_logits=init_m, 
        init_p_logits=init_p
    ).to(device)

    loss_engine = DOMACLossFunction(target_sink_count=TARGET_SINK_COUNT)
    trainer = DOMACTrainer(model, loss_engine, lr=0.05)
    
    print("\n[Engine] 物理映射与梯度反向传播开始...")
    
    start_time = time.time()
    final_M, final_P = trainer.train(pp_at, pp_slew, max_epochs=300)
    
    print("\n[System] 优化执行完毕！网表拓扑已坍缩至离散界限附近。")
    
    legalizer = DOMACLegalizer()
    discrete_M, discrete_P = legalizer.legalize(final_M, final_P, C_TYPES, model.dag_mask)
    
    # # ================= [探针 1：列高溢出探针] =================
    # probe_column_height_overflow(model, discrete_M)
    # # ==========================================================

    # ================= [探针 2：离散化后硬连线物理评估 & WNS 溯源探针] =================
    probe_post_legalization_eval(
        model=model, 
        loss_engine=loss_engine, 
        trainer_hyperparams=trainer.hyperparams, 
        discrete_M=discrete_M, 
        discrete_P=discrete_P, 
        final_P=final_P, 
        pp_at=pp_at, 
        pp_slew=pp_slew, 
        REQ_TIME=REQ_TIME, 
        PP_COLS=PP_COLS, 
        COMP_COLS=COMP_COLS
    )

    # ================= [探针 3：波前到达时间 (Wavefront AT) 探针] =================
    probe_wavefront_at(model=model, discrete_M=discrete_M)

    # ==============================================================================

    os.makedirs("output/netlists", exist_ok=True)
    
    v_gen = VerilogGenerator(
        pp_cols=PP_COLS, 
        c_cols=COMP_COLS,
        c_types=C_TYPES,
        fa_cell_names=fa_names,
        ha_cell_names=ha_names
    )
    
    netlist_path = f"output/netlists/domac_tree_{BIT_WIDTH}.v"
    # tb_path = "output/netlists/tb_domac_.v"
    
    v_gen.generate(discrete_M, discrete_P, output_file=netlist_path)
    # v_gen.generate_testbench(tb_file=tb_path, netlist_file=netlist_path)
    
    top_path = f"output/netlists/domac_{BIT_WIDTH}.v"
    v_gen.generate_multiplier_top(
        bit_width=BIT_WIDTH, 
        top_file=top_path, 
        ct_module_name="domac_tree", 
        top_module_name="domac"
    )
    if INIT_MODE == 'dadda' and discrete_init_M is not None:
        print(f"\n[BaselineGen] 正在直接从 AI 热启动矩阵中剥离 {INIT_MODE} 基准网表 (保证 100% 对齐)...")
        v_gen.module_name = f"{INIT_MODE}_tree"
        v_gen.generate(discrete_init_M, discrete_init_P, output_file=f"output/netlists/{INIT_MODE}_tree_{BIT_WIDTH}.v")
        v_gen.generate_multiplier_top(
            bit_width=BIT_WIDTH,
            top_file=f"output/netlists/{INIT_MODE}_{BIT_WIDTH}.v",
            ct_module_name=f"{INIT_MODE}_tree",
            top_module_name=f"{INIT_MODE}"
        )
        v_gen.module_name = "dadda_tree"
    else:
        print(f"\n[BaselineGen] 当前为 '{INIT_MODE}' 冷启动模式，跳过生成基准对照组网表。")

    end_time = time.time()
    print("="*60)
    print(f" [任务完成] 全流程跑通，总耗时: {end_time - start_time:.2f} 秒")
    print(f" 请前往 output/netlists/domac_result.v 查看流片网表。")
    print("="*60)

    print("\n[System] 启动跨服传输，正在将网表发射至 GPU 仿真服务器...")
    rsync_cmd = [
        "rsync", "-avzP",
        "output/netlists/", 
        "-e", "ssh -p 16822",
        "lchangxian@202.120.39.27:/home/lchangxian/powerSimPlatform/src/rtl/"
    ]
    
    try:
        subprocess.run(rsync_cmd, check=True)
        print("="*60)
        print("[System] 🚀 跨服投递成功！")
        print("所有 RTL 网表已安全降落在 powerSimPlatform/src/rtl/ 目录下，准备好进行功耗评估！")
        print("="*60)
    except subprocess.CalledProcessError as e:
        print(f"\n[Fatal Error] 传输任务坠毁！rsync 返回了非零状态码: {e.returncode}")
        print("-> 建议检查: 1. 服务器网络是否畅通 2. SSH 端口和用户名是否正确。")
    except FileNotFoundError:
        print("\n[Fatal Error] 本地系统未找到 rsync 命令，请先运行 sudo apt install rsync 安装。")

if __name__ == "__main__":
    main()