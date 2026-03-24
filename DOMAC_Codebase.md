# DOMAC_TSMC28 工程代码全局快照

**Root Directory:** `/home/changxian/DOMAC_TSMC28`

### `domac.py`

```python
import os
import sys
import torch
import time
import subprocess

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
    
    INIT_MODE = 'blank'
    
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
        
    BIT_WIDTH = 8
    TARGET_SINK_COUNT = (BIT_WIDTH * 2 - 1) * 2
    PP_COLS, COMP_COLS, C_TYPES = generate_multiplier_canvas(BIT_WIDTH)
    NUM_PP = len(PP_COLS)
    NUM_COMPRESSORS = len(COMP_COLS)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\n[System] 核心计算引擎将挂载至: {device}")
    if torch.cuda.is_available():
        print(f" -> 检测到显卡: {torch.cuda.get_device_name(0)}")
        torch.backends.cudnn.benchmark = True 

    pp_at = torch.full((NUM_PP,), 0.1, device=device)
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
```

### `src/parser/lib_parser.py`

```python
import re
import numpy as np
import torch
from collections import defaultdict

class NLDMParser:
    def __init__(self, lib_path, target_cells):
        """
        基于第一性原理的 NLDM 流式解析引擎
        :param lib_path: TSMC 28nm .lib 文件的绝对路径
        :param target_cells: 需要提取的物理单元名称列表 (如全加器、半加器)
        """
        self.lib_path = lib_path
        self.target_cells = set(target_cells)
        
        # 预编译正则，榨干 CPU 扫描性能
        self.re_cell = re.compile(r'^\s*cell\s*\(\s*"?([a-zA-Z0-9_]+)"?\s*\)')
        self.re_pin = re.compile(r'^\s*pin\s*\(\s*"?([a-zA-Z0-9_]+)"?\s*\)')
        self.re_related_pin = re.compile(r'^\s*related_pin\s*:\s*"?([a-zA-Z0-9_]+)"?')
        self.re_table = re.compile(r'^\s*(cell_rise|cell_fall|rise_transition|fall_transition)\s*\(')
        self.re_index_1 = re.compile(r'^\s*index_1\s*\(\s*"?([^"]+)"?\s*\)')
        self.re_index_2 = re.compile(r'^\s*index_2\s*\(\s*"?([^"]+)"?\s*\)')
        self.re_values = re.compile(r'^\s*values\s*\(\s*(.*)')

        # 匹配 area 
        self.re_area = re.compile(r'^\s*area\s*:\s*([\d\.]+)\s*;')
        # 匹配 capacitance
        self.re_cap = re.compile(r'^\s*capacitance\s*:\s*([\d\.]+)\s*;')

    def parse(self):
        print(f"[Core] 启动底层物理数据剥离，目标库: {self.lib_path}")
        
        # 核心数据字典结构: data[cell][out_pin][related_in_pin][table_group]
        # table_group: 'delay' (包含 cell_rise/fall), 'slew' (包含 rise/fall_transition)
        raw_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))
        
        # 状态机游标
        cur_cell, cur_pin, cur_related_pin, cur_table = None, None, None, None
        in_values = False
        temp_val_str = ""
        
        with open(self.lib_path, 'r', encoding='utf-8') as f:
            for line_idx, line in enumerate(f):
                line = line.strip()
                if not line or line.startswith('/*'): continue
                
                # 1. 嗅探 Cell 层级
                m_cell = self.re_cell.search(line)
                if m_cell:
                    cur_cell = m_cell.group(1) if m_cell.group(1) in self.target_cells else None
                    cur_pin, cur_related_pin, cur_table = None, None, None
                    continue
                if not cur_cell: continue # 无情跳过非目标 Cell，降低 I/O 损耗
                
               # ==========================================================
                # [新增] 1.5 捕获 Cell 的物理面积
                # 只要进入了有效 Cell，如果遇到 area 关键字，直接记录
                m_area = self.re_area.search(line)
                if m_area:
                    raw_data[cur_cell]['cell_area'] = float(m_area.group(1))
                    continue
                # ==========================================================

                # 2. 嗅探 Pin 层级 (通常是 Output/Input Pin)
                m_pin = self.re_pin.search(line)
                if m_pin:
                    cur_pin = m_pin.group(1)
                    cur_related_pin, cur_table = None, None
                    continue
                    
                # ==========================================================
                # [新增] 2.5 捕获 Pin 的负载电容
                # 只要确定了当前是哪个 pin，遇到 capacitance 关键字就记录
                m_cap = self.re_cap.search(line)
                if m_cap and cur_pin:
                    if 'pin_cap' not in raw_data[cur_cell]:
                        raw_data[cur_cell]['pin_cap'] = {}
                    raw_data[cur_cell]['pin_cap'][cur_pin] = float(m_cap.group(1))
                    continue
                # ==========================================================
                    
                # 3. 嗅探时序弧起点 (Related Pin / Input Pin)
                m_related = self.re_related_pin.search(line)
                if m_related and cur_pin:
                    cur_related_pin = m_related.group(1)
                    continue
                    
                # 4. 捕获具体的 LUT 表声明
                m_table = self.re_table.search(line)
                if m_table and cur_related_pin:
                    cur_table = m_table.group(1)
                    continue
                
                if not cur_table: continue
                
                # 5. 捕获坐标轴 (index_1: Slew, index_2: Load)
                m_idx1 = self.re_index_1.search(line)
                if m_idx1:
                    raw_data[cur_cell][cur_pin][cur_related_pin][cur_table]['index_1'] = np.array(m_idx1.group(1).replace(',',' ').split(), dtype=float)
                    continue
                m_idx2 = self.re_index_2.search(line)
                if m_idx2:
                    raw_data[cur_cell][cur_pin][cur_related_pin][cur_table]['index_2'] = np.array(m_idx2.group(1).replace(',',' ').split(), dtype=float)
                    continue
                    
                # 6. 捕获二维数值矩阵
                m_val = self.re_values.search(line)
                if m_val or in_values:
                    in_values = True
                    # 去掉末尾的反斜杠折行符，但【保留原始引号】
                    if line.endswith('\\'):
                        temp_val_str += line[:-1] + " "
                    else:
                        temp_val_str += line
                        # 当前 LUT 数据块读取完毕，准备二维重建
                        try:
                            # 利用正则精准提取所有在双引号 "" 内的字符串，每一个引号代表矩阵的一行！
                            rows_str = re.findall(r'"([^"]+)"', temp_val_str)
                            matrix = []
                            for r_str in rows_str:
                                # 将引号内的逗号替换为空格，然后切分为浮点数列表
                                clean_r = r_str.replace(',', ' ')
                                matrix.append(list(map(float, clean_r.split())))
                            
                            matrix = np.array(matrix)
                            raw_data[cur_cell][cur_pin][cur_related_pin][cur_table]['values'] = matrix
                            
                        except Exception as e:
                            print(f"[Warning] 解析 {cur_cell}:{cur_pin}->{cur_related_pin} 矩阵异常: {e}")
                            
                        # 状态重置
                        in_values, temp_val_str, cur_table = False, "", None

        return self._tensorize_and_find_worst_case(raw_data)

    def _tensorize_and_find_worst_case(self, raw_data):
        """
        按照 DOMAC 论文要求，将 rise 和 fall 取最大值（Worst-case），并转化为 PyTorch Tensor
        """
        print("[Core] 开始融合 Worst-case 物理场景并生成 PyTorch Tensors...")
        tensor_db = {}
        
        for cell, pins in raw_data.items():
            tensor_db[cell] = {}
            
            # ==========================================================
            # [新增修复] 1. 优先安全地把面积和电容继承过去
            if 'cell_area' in pins:
                tensor_db[cell]['cell_area'] = pins['cell_area']
            if 'pin_cap' in pins:
                tensor_db[cell]['pin_cap'] = pins['pin_cap']
            # ==========================================================
            
            for out_pin, related_pins in pins.items():
                # ==========================================================
                # [新增修复] 2. 如果遇到面积和电容这两个“伪装成引脚”的 key，立刻跳过！
                if out_pin in ['cell_area', 'pin_cap']:
                    continue
                # ==========================================================
                
                tensor_db[cell][out_pin] = {}
                for in_pin, tables in related_pins.items():
                    # 这里必须进行严谨的数据检查
                    if 'cell_rise' not in tables or 'cell_fall' not in tables:
                        continue
                        
                    # 校验坐标轴是否对齐
                    idx1 = tables['cell_rise']['index_1']
                    idx2 = tables['cell_rise']['index_2']
                    
                    assert np.allclose(idx1, tables['cell_fall']['index_1']), "Rise 和 Fall 的 Slew 坐标系未对齐，不能直接 np.maximum！"
                    assert np.allclose(idx2, tables['cell_fall']['index_2']), "Rise 和 Fall 的 Load 坐标系未对齐！"

                    # 取 Worst-case Delay 
                    delay_worst = np.maximum(tables['cell_rise']['values'], tables['cell_fall']['values'])
                    # 取 Worst-case Slew 
                    slew_worst = np.maximum(tables['rise_transition']['values'], tables['fall_transition']['values'])
                    
                    tensor_db[cell][out_pin][in_pin] = {
                        'index_1_slew': torch.tensor(idx1, dtype=torch.float32),
                        'index_2_load': torch.tensor(idx2, dtype=torch.float32),
                        'delay_lut': torch.tensor(delay_worst, dtype=torch.float32),
                        'slew_lut': torch.tensor(slew_worst, dtype=torch.float32)
                    }
            print(f" -> 成功编译物理单元: {cell}")
            
        return tensor_db

# ================= 单元测试与入口 =================
if __name__ == "__main__":
    TSMC28_LIB_PATH = "/home/changxian/library/t28_official/tcbn28hpcplusbwp12t40p140tt0p9v25c.lib"
    TARGET_CELLS = ['FA1D1BWP12T40P140', 'HA1D1BWP12T40P140'] 
    
    parser = NLDMParser(TSMC28_LIB_PATH, TARGET_CELLS)
    nldm_tensors = parser.parse()
    
    # 验证输出结构
    # print(nldm_tensors['FA_X1']['S']['A']['delay_lut'])
```

### `src/optimizer/train.py`

```python
import torch
import torch.optim as optim
import time
import torch.profiler

class DOMACTrainer:
    def __init__(self, model, loss_engine, lr=0.01):
        """
        DOMAC 训练引擎 (Dr. Gemini 性能探针版 + 并发进度回调支持)
        """
        self.model = model
        self.loss_engine = loss_engine
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)
        # # [暴力修正] 让 P_c (物理门选择) 的变化速度比 M (连线拓扑) 快 5 倍！
        # self.optimizer = optim.Adam([
        #     {'params': [self.model.m_logits], 'lr': lr},
        #     {'params': [self.model.p_logits], 'lr': lr * 5.0}  # 强行加速物理收敛
        # ])

        self.hyperparams = {
            't1': 1.5,     # WNS 权重拉到极致，逼迫网络突破延迟极限
            't2': 0.223,       # TNS 辅助全局路径寻优
            'alpha': 1,    # 【封印】前期绝对不许管面积！
            'lambda1': 0.2,  # 连线合法性是必须的
            'lambda2': 0.2,  # 【封印】前期不许进行二值化坍缩！让概率保持连续，充分探索！
            'tau_k':0.995,
        }

        # self.hyperparams = {
        #     't1': 3.4,     # WNS 权重拉到极致，逼迫网络突破延迟极限
        #     't2': 0.35,       # TNS 辅助全局路径寻优
        #     'alpha': 1,    # 【封印】前期绝对不许管面积！
        #     'lambda1': 0.25,  # 连线合法性是必须的
        #     'lambda2': 0.12,  # 【封印】前期不许进行二值化坍缩！让概率保持连续，充分探索！
        #     'tau_k':0.995,
        # }
    def update_hyperparameters(self, epoch):
        if epoch >= 100:
            self.hyperparams['alpha'] *= 1.003
            self.hyperparams['t1'] *= 1.005
            self.hyperparams['t2'] *= 1.005
            self.hyperparams['lambda1'] *= 1.01
            self.hyperparams['lambda2'] *= 1.01

    # def update_hyperparameters(self, epoch):
    #     """
    #     动态退火调度器：分阶段释放约束
    #     """
    #     # 阶段 1 (Epoch 0-99)：野蛮生长，全力追求 WNS 和合法拓扑
        
    #     # 阶段 2 (Epoch 100 触发)：拓扑基本成型，开始施加面积与二值化压力
    #     if epoch == 100:
    #         print("\n[Scheduler] Epoch 100 抵达！解封 Area 与 二值化 (L_D) 约束！")
    #         self.hyperparams['alpha'] = 0.05   
    #         self.hyperparams['lambda2'] = 0.1  
            
    #     # 阶段 3 (Epoch 100-300)：温水煮青蛙，逐步收紧离散化和合法性，逼迫最终坍缩
    #     if epoch > 120:
    #         # self.hyperparams['lambda1'] *= 1.02  # 越来越严苛的合法性
    #         # self.hyperparams['lambda2'] *= 1.05  # 逼迫概率走向 0 或 1
    #         # self.hyperparams['alpha'] *= 1.005   # 轻微压缩面积
    #         self.hyperparams['lambda1'] *= 1.02  
    #         self.hyperparams['lambda2'] *= 1.05  
    #         self.hyperparams['alpha'] *= 1.002

    # ================= [修改点 1：增加 epoch_callback 参数] =================
    def train(self, pp_at, pp_slew, max_epochs=300, epoch_callback=None):
    # ========================================================================
        print(f"[Optimizer] 启动 DOMAC 训练循环，最大迭代次数: {max_epochs}")
        print(f"[Profiler] 性能探针已植入。正在监控 Forward, Loss, Backward, Step 耗时...")
        
        # 性能累加器
        acc_forward, acc_loss, acc_backward, acc_step = 0.0, 0.0, 0.0, 0.0
        
        for epoch in range(max_epochs):
            self.update_hyperparameters(epoch)
            self.optimizer.zero_grad()
            
            # ================= [新增：极其暴力的温度退火] =================
            # 指数级降温：Epoch 0 时 tau=1.0，Epoch 300 时 tau 接近 0.05
            # 这会把 AI 伪造的 "冰块概率" 强行压成 0，暴露出真实的延迟！
            current_tau_k = self.hyperparams.get('tau_k')
            current_tau = max(0.05, 1.0 * (current_tau_k ** epoch))
            # current_tau = 1
            # # ================= [修复：三段式科学退火调度] =================
            # if epoch < 60:
            #     # [阶段 1: 探索期] 保持高温 1.0。
            #     # 允许一定的概率稀释，让梯度在不同拓扑之间顺畅流动，寻找最优解
            #     current_tau = 1.0 
            # elif epoch < 200:
            #     # [阶段 2: 极化期] 极其缓慢地降温。
            #     # 0.99 保证在 140 个 Epoch 内从 1.0 慢慢降到 0.24 左右。
            #     # 此时 WNS 的梯度依然存活，引导网络慢慢将优势路径向 1.0 靠拢。
            #     current_tau = 1.0 * (0.99 ** (epoch - 60))
            # else:
            #     # [阶段 3: 淬火期] 强制逼近 0.1 以下，固化物理连线，准备迎接 Legalizer
            #     # current_tau = max(0.05, 0.24 * (0.95 ** (epoch - 200)))
            #     # [阶段 3: 淬火期] 强制极化，但保留最低限度的梯度流
            #     current_tau = max(0.15, 0.24 * (0.95 ** (epoch - 200)))
            # # =================================================================
            
            # ================= [探针 1: 前向传播 STA] =================
            t0 = time.time()
            # wns, tns, area, M, P_c = self.model(pp_at, pp_slew)
            wns, tns, area, M, P_c = self.model(pp_at, pp_slew, tau=current_tau)
            t1 = time.time()
            acc_forward += (t1 - t0)
            
            active_pin_mask = self.model.active_pin_mask
            c_types = self.model.c_types
            
            # ================= [探针 2: 目标与约束 Loss 计算] =================
            total_loss, loss_dict = self.loss_engine(
                wns, tns, area, M, P_c, self.hyperparams, 
                active_pin_mask, c_types
            )
            t2 = time.time()
            acc_loss += (t2 - t1)

            # ================= [探针 3: 反向传播梯度计算] =================
            total_loss.backward()
            t3 = time.time()
            acc_backward += (t3 - t2)
            
            # ================= [探针 4: 优化器参数更新] =================
            self.optimizer.step()
            t4 = time.time()
            acc_step += (t4 - t3)
            
            # ================= [修改点 2：触发全局进度条回调] =================
            # 将当前 epoch 和最新的 WNS 传递给主进程的 tqdm 监听器
            if epoch_callback is not None:
                current_wns_val = loss_dict['wns'].item() if 'wns' in loss_dict else 0.0
                epoch_callback(epoch, current_wns_val)
            # ==================================================================

            # 每 20 步打印一次物理指标与性能报告
            if epoch % 20 == 0 or epoch == max_epochs - 1:
                print(f"\nEpoch {epoch:03d} | "
                      f"WNS: {loss_dict['wns'].item():.4f} | "
                      f"Area: {loss_dict['area'].item():.4f} | "
                      f"L_BM: {loss_dict['l_bm'].item():.4f} | "
                      f"Total Loss: {total_loss.item():.4f}")
                
                # 打印过去 20 步的平均耗时 (如果是 Epoch 0，就是单步耗时)
                div = 1 if epoch == 0 else 20
                print(f"  -> [Profiler] Avg Time/Epoch - "
                      f"Forward: {acc_forward/div:.3f}s | "
                      f"Loss: {acc_loss/div:.3f}s | "
                      f"Backward: {acc_backward/div:.3f}s | "
                      f"Step: {acc_step/div:.3f}s")
                
                # ================= [探针：抓捕 AI 的概率稀释作弊] =================
                # M 矩阵的 Shape 是 [总节点数, 压缩器引脚总数]
                # 对每一列求最大值，代表该引脚最主要的信号来源所占的百分比
                max_probs_per_pin, _ = torch.max(M, dim=0)
                
                # 统计有多少个引脚的“主来源概率”低于 0.95 (即掺杂了 >5% 的冰块信号)
                cheating_pins = torch.sum((max_probs_per_pin < 0.95) & (active_pin_mask > 0.5)).item()
                avg_max_prob = torch.mean(max_probs_per_pin).item()
                
                print(f"  -> [探针] 引脚最大连接概率均值: {avg_max_prob:.4f} (若趋近 1.0 则为纯粹硬连线)")
                print(f"  -> [探针] 发现 {cheating_pins} 个引脚正在进行严重的小数概率稀释！")
                
                # 特别打印最后一个压缩器 (极有可能是贪吃蛇的末端) 的三个引脚连线概率
                last_c_idx = P_c.shape[0] - 1
                col_A = last_c_idx * 3 + 0
                col_B = last_c_idx * 3 + 1
                col_CI = last_c_idx * 3 + 2
                print(f"  -> [探针] 末端加法器_{last_c_idx} 的主来源概率 - A:{max_probs_per_pin[col_A]:.4f}, B:{max_probs_per_pin[col_B]:.4f}, CI:{max_probs_per_pin[col_CI]:.4f}")
                
                # ================= [深度时序探针：揭露 AT 概率稀释真相] =================
                pin_ats = self.model._probe_pin_ats
                node_ats = self.model._probe_node_ats
                
                # 找出全图预期到达时间 (Expected AT) 最大的输入引脚
                worst_pin_idx = torch.argmax(pin_ats).item()
                worst_expected_at = pin_ats[worst_pin_idx].item()
                
                print(f"\n  🔍 [时序深度穿透] 观测最差引脚 Index: {worst_pin_idx} | 连续域期望 AT: {worst_expected_at:.4f} ns")
                
                # 提取该引脚的上游连线概率云
                probs_to_worst_pin = M[:, worst_pin_idx]
                top_probs, top_indices = torch.topk(probs_to_worst_pin, 5)
                
                expected_at_sum = 0.0
                for p, src_idx in zip(top_probs, top_indices):
                    src_at = node_ats[src_idx].item()
                    contribution = p.item() * src_at
                    expected_at_sum += contribution
                    print(f"      [源节点 {src_idx.item():>3d}] 概率: {p.item():.4f} | 真实物理AT: {src_at:.4f} ns -> 被稀释为: {contribution:.4f} ns")
                
                print(f"      ... (长尾碎概率贡献总和: {max(0.0, worst_expected_at - expected_at_sum):.4f} ns)")
                
                worst_physical_at = node_ats[top_indices[0]].item()
                print(f"  ⚠️  [物理真相警告] 若此时 Legalizer 强行硬连最大概率线, 该引脚真实 AT 将瞬间暴涨至 -> {worst_physical_at:.4f} ns!\n")
                # ====================================================================
                
                # 清零累加器，准备下一个周期的监控
                acc_forward, acc_loss, acc_backward, acc_step = 0.0, 0.0, 0.0, 0.0

        print("[Optimizer] 训练收敛完成。")
        return M.detach(), P_c.detach()
```

### `src/optimizer/legalizer.py`

```python
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
```

### `src/core/compressor_tree.py`

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
from .diff_sta import smooth_max_lse, diff_bilinear_interp

class DOMAC_CompressorTree(nn.Module):
    # 1. 在初始化参数中加入 device
    # def __init__(self, pp_cols, c_cols, fa_tensors, ha_tensors, c_types, req_time, device='cpu'):
    #     super(DOMAC_CompressorTree, self).__init__()
    def __init__(self, pp_cols, c_cols, fa_tensors, ha_tensors, c_types, req_time, device='cpu', init_m_logits=None, init_p_logits=None):
        super(DOMAC_CompressorTree, self).__init__()
        self.device = device  # <--- [核心新增] 记住目标设备
        self.pp_cols = pp_cols
        self.c_cols = c_cols
        self.num_pp = len(pp_cols)
        self.num_c = len(c_cols)
        self.c_types = c_types
        
        self.s_cols = c_cols
        self.co_cols = [col + 1 for col in c_cols] 
        self.node_cols = list(self.pp_cols) + list(self.s_cols) + list(self.co_cols)
        total_nodes = len(self.node_cols)
        
        self.num_fa_impls = len(fa_tensors)
        self.num_ha_impls = len(ha_tensors)
        self.max_impls = max(self.num_fa_impls, self.num_ha_impls)
        self.req_time = req_time
        
        self.pin_names = ['A', 'B', 'CI']
        self.num_pins_per_c = len(self.pin_names)
        
        # 预编译为 3D 张量的物理库 (现在会在解析时直接上 GPU)
        self.fa_areas, self.fa_caps, self.fa_arcs = self._parse_tensors(fa_tensors)
        self.ha_areas, self.ha_caps, self.ha_arcs = self._parse_tensors(ha_tensors)
        
        # ... 后续的 p_logits, dag_mask 等代码保持不变 ...
        # self.p_logits = nn.Parameter(torch.zeros(self.num_c, self.max_impls))
        if init_p_logits is not None:
            self.p_logits = nn.Parameter(init_p_logits.clone().to(device))
        else:
            self.p_logits = nn.Parameter(torch.zeros(self.num_c, self.max_impls, device=device))
        
        p_mask = torch.zeros(self.num_c, self.max_impls)
        active_pin_mask = torch.zeros(self.num_c * self.num_pins_per_c)
        
        for j, c_type in enumerate(self.c_types):
            if c_type == 'FA':
                p_mask[j, self.num_fa_impls:] = float('-inf')
                active_pin_mask[j*3 : j*3+3] = 1.0
            else:
                p_mask[j, self.num_ha_impls:] = float('-inf')
                active_pin_mask[j*3 : j*3+2] = 1.0
                active_pin_mask[j*3+2] = 0.0
                
        self.register_buffer('p_mask', p_mask)
        self.register_buffer('active_pin_mask', active_pin_mask)
        
        # total_target_pins = self.num_c * self.num_pins_per_c 
        # self.m_logits = nn.Parameter(torch.zeros(total_nodes, total_target_pins + 1))
        total_target_pins = self.num_c * self.num_pins_per_c 
        if init_m_logits is not None:
            # 采用传入的热启动矩阵
            self.m_logits = nn.Parameter(init_m_logits.clone().to(device))
        else:
            # 原本的白板初始化
            self.m_logits = nn.Parameter(torch.zeros(total_nodes, total_target_pins + 1, device=device))
            
        dag_mask = torch.full((total_nodes, total_target_pins + 1), float('-inf'))
        for i in range(total_nodes):
            for j in range(self.num_c):
                if i < self.num_pp:
                    is_downstream = True
                elif i < self.num_pp + self.num_c:
                    is_downstream = (i - self.num_pp) < j
                else:
                    is_downstream = (i - self.num_pp - self.num_c) < j

                if is_downstream and (self.node_cols[i] == self.c_cols[j]):
                    for p_idx in range(self.num_pins_per_c):
                        if self.active_pin_mask[j * 3 + p_idx] > 0.5:
                            dag_mask[i, j * self.num_pins_per_c + p_idx] = 0.0
            dag_mask[i, total_target_pins] = 0.0 
            
        self.register_buffer('dag_mask', dag_mask)

    def _parse_tensors(self, tensors):
        areas, caps = [], []
        stacked_arcs = {'S': {}, 'CO': {}}
        for p in self.pin_names:
            stacked_arcs['S'][p] = {'delay_lut': [], 'slew_lut': []}
            stacked_arcs['CO'][p] = {'delay_lut': [], 'slew_lut': []}
        
        ref_arc = None
        for ct in tensors:
            for out_p in ['S', 'CO']:
                for in_p in self.pin_names:
                    if ct.get(out_p, {}).get(in_p):
                        ref_arc = ct[out_p][in_p]
                        break
                if ref_arc: break
            if ref_arc: break
            
        index_1_slew = ref_arc['index_1_slew']
        index_2_load = ref_arc['index_2_load']

        # for ct in tensors:
        #     areas.append(ct.get('cell_area', 1.0))
        #     p_caps = [ct.get('pin_cap', {}).get(p, 0.001) for p in self.pin_names]
        #     caps.append(p_caps)

        #     for out_p in ['S', 'CO']:
        #         for in_p in self.pin_names:
        #             arc = ct.get(out_p, {}).get(in_p)
        #             if arc:
        #                 stacked_arcs[out_p][in_p]['delay_lut'].append(arc['delay_lut'])
        #                 stacked_arcs[out_p][in_p]['slew_lut'].append(arc['slew_lut'])
        #             else:
        #                 stacked_arcs[out_p][in_p]['delay_lut'].append(torch.full((7,7), 10.0))
        #                 stacked_arcs[out_p][in_p]['slew_lut'].append(torch.full((7,7), 10.0))
        for ct_idx, ct in enumerate(tensors):
            # ==========================================================
            # 1. 严格面积审查 (拒绝默认值 1.0)
            # ==========================================================
            if 'cell_area' not in ct:
                raise ValueError(f"[Fatal] 物理库审查失败: 传入的第 {ct_idx} 个单元缺失面积(cell_area)数据！")
            areas.append(ct['cell_area'])
            
            # ==========================================================
            # 2. 严格电容审查 (拒绝默认值 0.001)
            # ==========================================================
            p_caps = []
            for p in self.pin_names:
                if p not in ct.get('pin_cap', {}):
                    # 如果是 CI 引脚缺失，且当前单元可能是半加器(HA)，合法，用 0.0 填充
                    if p == 'CI':
                        p_caps.append(0.0)
                    else:
                        raise ValueError(f"[Fatal] 物理库审查失败: 单元缺失必须引脚 '{p}' 的电容数据！")
                else:
                    p_caps.append(ct['pin_cap'][p])
            caps.append(p_caps)

            # ==========================================================
            # 3. 严格时序弧审查 (拒绝伪造 10.0ns 的惩罚延迟)
            # ==========================================================
            for out_p in ['S', 'CO']:
                for in_p in self.pin_names:
                    arc = ct.get(out_p, {}).get(in_p)
                    if arc:
                        stacked_arcs[out_p][in_p]['delay_lut'].append(arc['delay_lut'])
                        stacked_arcs[out_p][in_p]['slew_lut'].append(arc['slew_lut'])
                    else:
                        # 物理上确实不存在的路径 (例如 HA 的 CI->S)，填入全 0 张量。
                        # 在 forward 时，这些路径会被 active_pin_mask 屏蔽，所以填 0 是物理合法的
                        dummy_lut = torch.zeros((7,7))
                        stacked_arcs[out_p][in_p]['delay_lut'].append(dummy_lut)
                        stacked_arcs[out_p][in_p]['slew_lut'].append(dummy_lut)
        # =========================================================================
        # [核弹级显存挂载] 强行把嵌套在字典里的 3D 物理矩阵全部搬运到 GPU 显存上！
        for out_p in ['S', 'CO']:
            for in_p in self.pin_names:
                stacked_arcs[out_p][in_p]['delay_lut'] = torch.stack(stacked_arcs[out_p][in_p]['delay_lut']).to(self.device)
                stacked_arcs[out_p][in_p]['slew_lut'] = torch.stack(stacked_arcs[out_p][in_p]['slew_lut']).to(self.device)
                stacked_arcs[out_p][in_p]['index_1_slew'] = index_1_slew.to(self.device)
                stacked_arcs[out_p][in_p]['index_2_load'] = index_2_load.to(self.device)

        return torch.tensor(areas, dtype=torch.float32, device=self.device), torch.tensor(caps, dtype=torch.float32, device=self.device), stacked_arcs

    # def forward(self, pp_at, pp_slew):
    #     P_c = F.softmax(self.p_logits + self.p_mask, dim=-1) 
    #     M_full = F.softmax(self.m_logits + self.dag_mask, dim=-1) 
    #     M_internal = M_full[:, :-1] 
    def forward(self, pp_at, pp_slew, tau=1.0):
        # 【核心修改】将 logits 除以温度 tau，tau 越小，概率越向 0/1 极化！
        P_c = F.softmax((self.p_logits + self.p_mask) / tau, dim=-1) 
        M_full = F.softmax((self.m_logits + self.dag_mask) / tau, dim=-1) 
        M_internal = M_full[:, :-1]
            
        expected_area = 0.0
        expected_pin_caps_list = []

        for j, c_type in enumerate(self.c_types):
            is_fa = (c_type == 'FA')
            lib_areas = self.fa_areas if is_fa else self.ha_areas
            lib_caps = self.fa_caps if is_fa else self.ha_caps
            
            p_j = P_c[j, :self.num_fa_impls] if is_fa else P_c[j, :self.num_ha_impls]
            expected_area = expected_area + torch.sum(p_j * lib_areas.to(P_c.device))
            
            c_caps = p_j @ lib_caps.to(P_c.device)
            expected_pin_caps_list.append(c_caps)
            
        flat_expected_pin_caps = torch.cat(expected_pin_caps_list)
        # ================= [核心物理修复：引入线负载模型 WLM] =================
        # 假设 TSMC 28nm 下，一根跨 Cell 互连线的平均寄生电容约为 0.003 pF (3 fF)
        # 你可以根据实际库的情况微调这个值
        WIRE_CAP_PER_NET = 0.000 
        
        # 原逻辑：loads = M_internal @ flat_expected_pin_caps
        # 新逻辑：只要存在连线（M_internal），就必须附加上导线的寄生电容！
        # loads = M_internal @ flat_expected_pin_caps + M_internal * WIRE_CAP_PER_NET
        # 修改 src/core/compressor_tree.py 第 201 行左右
        loads = M_internal @ (flat_expected_pin_caps + WIRE_CAP_PER_NET)
        # ====================================================================
        # loads = M_internal @ flat_expected_pin_caps 
        
        # =========================================================================
        # [Dr. Gemini 降维打击：Push 前向广播范式]
        # 1. 初始时刻：只利用外部输入的 PP 信号，一波推给压缩树的所有引脚进行打底！
        m_pp_all = M_internal[:self.num_pp, :]
        pin_ats_all = pp_at @ m_pp_all
        pin_slews_all = pp_slew @ m_pp_all
        # =========================================================================

        s_ats, s_slews = [], []
        co_ats, co_slews = [], []

        for j in range(self.num_c):
            col_start = j * self.num_pins_per_c
            col_end = col_start + self.num_pins_per_c
            
            # 2. 坐享其成：当前压缩器的输入引脚时序，早已被前面的兄弟计算好并推送过来了！
            # 彻底消灭了 O(N^2) 的 torch.stack 和切片！
            pin_ats = pin_ats_all[col_start:col_end]
            pin_slews = pin_slews_all[col_start:col_end]

            s_load = loads[self.num_pp + j]
            co_load = loads[self.num_pp + self.num_c + j]
            
            is_fa = (self.c_types[j] == 'FA')
            cell_arcs = self.fa_arcs if is_fa else self.ha_arcs
            P_j = P_c[j, :self.num_fa_impls] if is_fa else P_c[j, :self.num_ha_impls]
            
            s_paths_at, s_paths_slew = [], []
            co_paths_at, co_paths_slew = [], []
            
            for p_idx, p_name in enumerate(self.pin_names):
                if self.active_pin_mask[j * 3 + p_idx] > 0.5:
                    
                    arc_S = cell_arcs['S'][p_name]
                    delays_S = diff_bilinear_interp(pin_slews[p_idx], s_load, arc_S['index_1_slew'], arc_S['index_2_load'], arc_S['delay_lut'])
                    slews_S = diff_bilinear_interp(pin_slews[p_idx], s_load, arc_S['index_1_slew'], arc_S['index_2_load'], arc_S['slew_lut'])
                    
                    s_paths_at.append(pin_ats[p_idx] + torch.sum(P_j * delays_S))
                    s_paths_slew.append(torch.sum(P_j * slews_S))
                    
                    arc_CO = cell_arcs['CO'][p_name]
                    delays_CO = diff_bilinear_interp(pin_slews[p_idx], co_load, arc_CO['index_1_slew'], arc_CO['index_2_load'], arc_CO['delay_lut'])
                    slews_CO = diff_bilinear_interp(pin_slews[p_idx], co_load, arc_CO['index_1_slew'], arc_CO['index_2_load'], arc_CO['slew_lut'])
                    
                    co_paths_at.append(pin_ats[p_idx] + torch.sum(P_j * delays_CO))
                    co_paths_slew.append(torch.sum(P_j * slews_CO))

            # expected_s_at = smooth_max_lse(s_paths_at, gamma=0.01) if s_paths_at else torch.tensor(10.0, device=P_c.device)
            # expected_s_slew = smooth_max_lse(s_paths_slew, gamma=0.01) if s_paths_at else torch.tensor(10.0, device=P_c.device)
            # expected_co_at = smooth_max_lse(co_paths_at, gamma=0.01) if co_paths_at else torch.tensor(10.0, device=P_c.device)
            # expected_co_slew = smooth_max_lse(co_paths_slew, gamma=0.01) if co_paths_at else torch.tensor(10.0, device=P_c.device)
            # 如果某输出引脚没有任何合法输入路径，到达时间应当是 0.0 而不是惩罚性的 10.0ns
            expected_s_at = smooth_max_lse(s_paths_at, gamma=0.01) if s_paths_at else torch.tensor(0.0, device=P_c.device)
            expected_s_slew = smooth_max_lse(s_paths_slew, gamma=0.01) if s_paths_slew else torch.tensor(0.0, device=P_c.device)
            expected_co_at = smooth_max_lse(co_paths_at, gamma=0.01) if co_paths_at else torch.tensor(0.0, device=P_c.device)
            expected_co_slew = smooth_max_lse(co_paths_slew, gamma=0.01) if co_paths_slew else torch.tensor(0.0, device=P_c.device)
            # =========================================================================
            # 3. [核弹级推送] 本节点算完后，直接通过 M_internal 一波推给所有未来的潜在下游引脚！
            # a = a + b 是安全的 out-of-place 加法，完美保留 Autograd 梯度！
            pin_ats_all = pin_ats_all + expected_s_at * M_internal[self.num_pp + j, :]
            pin_slews_all = pin_slews_all + expected_s_slew * M_internal[self.num_pp + j, :]
            
            pin_ats_all = pin_ats_all + expected_co_at * M_internal[self.num_pp + self.num_c + j, :]
            pin_slews_all = pin_slews_all + expected_co_slew * M_internal[self.num_pp + self.num_c + j, :]
            # =========================================================================
            
            s_ats.append(expected_s_at)
            s_slews.append(expected_s_slew)
            co_ats.append(expected_co_at)
            co_slews.append(expected_co_slew)
            
        # 完美拼接，彻底消灭 list of tensors 导致的 O(N) 性能雪崩
        s_ats_t = torch.stack(s_ats)
        co_ats_t = torch.stack(co_ats)
        all_ats_tensor = torch.cat([pp_at, s_ats_t, co_ats_t])
        
        slacks = self.req_time - all_ats_tensor

        # # =========================================================================
        # # 🚀 [核弹级物理修复：可微 CPA 代理模型 (Differentiable CPA Proxy)]
        # # =========================================================================
        # # 1. 计算每个节点流向外部 CPA (Sink) 的连续概率
        # sink_probs = 1.0 - torch.sum(M_internal, dim=1)
        # sink_probs = torch.clamp(sink_probs, min=0.0, max=1.0)
        
        # # 2. 假设 28nm 工艺下，CPA 内部每经过 1 bit 的进位延迟约为 0.035 ns
        # # 你可以根据实际库的 FA CI->CO 延迟微调这个值
        # CPA_CARRY_DELAY_PER_BIT = 0.035 
        # max_col = max(self.node_cols)
        
        # # 3. 构造与所有节点对应的列权重张量，并送入 GPU
        # cols_tensor = torch.tensor(self.node_cols, dtype=torch.float32, device=all_ats_tensor.device)
        
        # # 4. 计算每个节点的 CPA 进位惩罚：
        # # 如果你处于第 c 列，且流向了 Sink，那么你必须为后续的 (max_col - c) 个进位链买单！
        # distance_to_msb = max_col - cols_tensor
        # cpa_penalty = distance_to_msb * CPA_CARRY_DELAY_PER_BIT * sink_probs
        
        # # 5. [核心] 带有 CPA 视野的全局有效到达时间
        # effective_ats_tensor = all_ats_tensor + cpa_penalty
        
        # # 使用引入了 CPA 惩罚的 AT 来计算 Slack
        # slacks = self.req_time - effective_ats_tensor
        # # =========================================================================
# =========================================================================
        # 🚀 [真实物理校准：可切换架构的 CPA 代理模型]
        # =========================================================================
        # 1. 计算每个节点流向外部 CPA (Sink) 的连续概率
        sink_probs = 1.0 - torch.sum(M_internal, dim=1)
        sink_probs = torch.clamp(sink_probs, min=0.0, max=1.0)
        
        # 2. 基于 2026-03 DC 综合报告提取的绝对真实参数
        CPA_BIT_DELAY_RCA = 0.040      # 从报告得出: CI->CO 稳定在 0.04ns
        CPA_BASE_DELAY_RCA = 0.090     # 首位 HA + 末位 S 输出的固定开销
        
        CPA_TREE_STAGE_DELAY = 0.035   # 高速前缀树(Kogge-Stone)单级延迟预估
        CPA_BASE_DELAY_TREE = 0.055    # 树形加法器的基础进入延迟

        max_col = max(self.node_cols)
        cols_tensor = torch.tensor(self.node_cols, dtype=torch.float32, device=all_ats_tensor.device)
        distance_to_msb = max_col - cols_tensor
        
        # =======================================================
        # 模式切换开关：目前你的 DC 综合出的是 RCA，所以我们先用 RCA 模式训练！
        # 如果你未来在 DC 里开出了前缀树，请把这里改成 'PREFIX_TREE'
        # =======================================================
        CPA_ARCHITECTURE = 'RCA' 
        
        if CPA_ARCHITECTURE == 'RCA':
            # O(N) 线性惩罚模型，完美契合你刚刚贴出的 DC 综合网表！
            cpa_latency = CPA_BASE_DELAY_RCA + distance_to_msb * CPA_BIT_DELAY_RCA
        else:
            # O(log2(N)) 对数模型，代表 DesignWare 里的顶级综合结果
            cpa_latency = CPA_BASE_DELAY_TREE + CPA_TREE_STAGE_DELAY * torch.log2(distance_to_msb + 1.0)
            
        # 计算 CPA 综合惩罚
        cpa_penalty = cpa_latency * sink_probs
        
        # 3. 融合 CPA 惩罚后的全局有效到达时间
        effective_ats_tensor = all_ats_tensor + cpa_penalty
        
        # 4. 利用全链路时序计算最终的 Slack
        slacks = self.req_time - effective_ats_tensor
        # =========================================================================
        
        negative_slacks = torch.clamp(slacks, max=0.0)
        
        WNS = smooth_max_lse(-negative_slacks, gamma=0.01) 
        TNS = torch.sum(-negative_slacks)
        
        # ================= [新增：探针埋点] =================
        # 将当前周期的引脚期望AT和节点真实AT暂存，供训练探针解剖
        self._probe_pin_ats = pin_ats_all.detach()
        self._probe_node_ats = all_ats_tensor.detach()
        # ====================================================

        return WNS, TNS, expected_area, M_internal, P_c
```

### `src/core/objectives.py`

```python
import torch
import torch.nn as nn
import torch.nn.functional as F

class DOMACLossFunction(nn.Module):
    # def __init__(self, pin_counts_lib=[3.0, 2.0]):
    #     """
    #     DOMAC 联合目标与约束损失函数引擎
    #     """
    #     super(DOMACLossFunction, self).__init__()
    #     self.pin_counts = torch.tensor(pin_counts_lib, dtype=torch.float32)
    def __init__(self, target_sink_count, pin_counts_lib=[3.0, 2.0]): # 接收动态目标
        super(DOMACLossFunction, self).__init__()
        self.target_sink_count = target_sink_count
        self.pin_counts = torch.tensor(pin_counts_lib, dtype=torch.float32)

    def calc_performance_loss(self, wns, tns, area, t1, t2, alpha):
        """
        1. 性能驱动损失 (Performance Objective)
        """
        return t1 * wns + t2 * tns + alpha * area

    # def calc_bijective_mapping_loss(self, M_internal, P_c):
    #     """
    #     2. Pin-Level 双射映射约束 (Bijective Mapping Loss L_BM)
    #     """
    #     # 实际流入每个特定引脚的概率总和，Shape: [num_c * 3]
    #     actual_in_signals = torch.sum(M_internal, dim=0) 
        
    #     num_c = P_c.shape[0]
    #     # P_c 的列 0 是 FA，列 1 是 HA
    #     expected_pins = torch.zeros(M_internal.shape[1], device=M_internal.device)
        
    #     for j in range(num_c):
    #         expected_pins[j * 3 + 0] = 1.0       # A 引脚: 不管是 FA 还是 HA 都要连
    #         expected_pins[j * 3 + 1] = 1.0       # B 引脚: 不管是 FA 还是 HA 都要连
    #         expected_pins[j * 3 + 2] = P_c[j, 0] # CI 引脚: 只有被判为 FA 的概率部分才允许连线
            
    #     return torch.sum((actual_in_signals - expected_pins) ** 2)

    def calc_bijective_mapping_loss(self, M_internal, P_c, active_pin_mask, c_types):
        actual_in_signals = torch.sum(M_internal, dim=0) 
        num_c = P_c.shape[0]
        expected_pins = torch.zeros(M_internal.shape[1], device=M_internal.device)
    
        for j in range(num_c):
            # A, B 引脚始终需要 1.0 的期望信号
            expected_pins[j * 3 + 0] = 1.0
            expected_pins[j * 3 + 1] = 1.0
        
             # CI 引脚：只有该坑位是 FA 时，才强制要求 1.0 的信号输入
            # 注意：因为你的画布已经提前指定了 c_types (FA或HA)，不需要依赖 P_c 来判断逻辑类型
            if c_types[j] == 'FA':
                expected_pins[j * 3 + 2] = 1.0
            else:
                expected_pins[j * 3 + 2] = 0.0 # HA 绝不要 CI 信号
            
        return torch.sum((actual_in_signals - expected_pins) ** 2)
    
    def calc_discretization_loss(self, tensor):
        """
        3. 二值化驱动损失 (Discretization Loss L_D)
        """
        return torch.sum((tensor ** 2) * ((1.0 - tensor) ** 2))

    def calc_sink_loss(self, M_internal, target_max_signals):
        """
        4. [新增] 过度输出惩罚 (Sink Constraint Loss)
        逼迫 AI 使用全加器进行压缩。如果最终流向 Sink 的期望信号数超过限制，施加核弹级惩罚！
        """
        # 利用概率守恒计算流向 Sink 的概率：1 - 内部连线概率总和
        # 每行的和代表该节点进入压缩器的概率，1 减去它就是流向 Sink 的概率
        sink_probs = 1.0 - torch.sum(M_internal, dim=1)
        
        # 整个网络最终抛给外界的总信号期望数
        total_sink_signals = torch.sum(sink_probs)
        
        # 使用 F.relu 提取超标的部分。如果不超标 (<=2.0)，则惩罚为 0；超标则产生极大梯度。
        excess_signals = F.relu(total_sink_signals - target_max_signals)
        
        # 施加高权重的平方惩罚（权重可根据需要调大，比如 100.0 或 1000.0）
        l_sink = (excess_signals ** 2) * 100.0
        return l_sink, total_sink_signals

    # def forward(self, wns, tns, area, M, P_c, hyperparams):
    def forward(self, wns, tns, area, M, P_c, hyperparams, active_pin_mask, c_types):    
        """
        联合损失计算引擎
        """
        t1 = hyperparams['t1']
        t2 = hyperparams['t2']
        alpha = hyperparams['alpha']
        lambda1 = hyperparams['lambda1']
        lambda2 = hyperparams['lambda2']
        
        # 1. 性能 Loss
        l_perf = self.calc_performance_loss(wns, tns, area, t1, t2, alpha)
        
        # 2. 合法拓扑 Loss
        # l_bm = self.calc_bijective_mapping_loss(M, P_c)
        l_bm = self.calc_bijective_mapping_loss(M, P_c, active_pin_mask, c_types)

        # 3. 离散化 Loss 
        l_d_M = self.calc_discretization_loss(M)
        l_d_P = self.calc_discretization_loss(P_c)
        l_d = l_d_M + l_d_P
        
        # 4. Sink 惩罚 Loss
        # 我们希望最终整个乘法器这列最多只留 2 个信号给底部的加法器
        l_sink, actual_sink_count = self.calc_sink_loss(M, target_max_signals=self.target_sink_count)
        
        # 5. 总 Loss 融合
        l_bm_norm = l_bm / (l_bm.detach() + 1e-5)
        l_d_norm = l_d / (l_d.detach() + 1e-5)
        l_sink_norm = l_sink / (l_sink.detach() + 1e-5)
        total_loss = l_perf + lambda1 * l_bm_norm + lambda2 * l_d_norm + l_sink_norm
        
        loss_dict = {
            'total_loss': total_loss,
            'l_perf': l_perf,
            'l_bm': l_bm,
            'l_d': l_d,
            'l_sink': l_sink,
            'actual_sink_count': actual_sink_count,
            'wns': wns,
            'tns': tns,
            'area': area
        }
        
        return total_loss, loss_dict
```

### `src/core/diff_sta.py`

```python
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
```

### `src/core/domac_utils.py`

```python
# domac_utils.py
import torch
import numpy as np

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
    print(f"\n[Canvas Generator] 自动推演 {bit_width}x{bit_width} 乘法器画布 (严格 Dadda Tree 算法)...")
    pp_cols = []
    max_cols = bit_width * 2 - 1
    dots_in_col = [0] * max_cols
    
    # 1. 生成初始部分积 (Partial Products) 矩阵
    for i in range(bit_width):
        for j in range(bit_width):
            col = i + j
            pp_cols.append(col)
            dots_in_col[col] += 1
            
    print(f" -> 共 {len(pp_cols)} 个 PP 节点。初始点数分布:\n    {dots_in_col}")
    
    # 2. 计算 Dadda 树的目标高度序列 (2, 3, 4, 6, 9, 13, 19, 28...)
    dadda_seq = [2]
    while dadda_seq[-1] < bit_width:
        dadda_seq.append(int(dadda_seq[-1] * 1.5))
    dadda_seq.reverse() 
    
    # 过滤掉大于等于当前最大高度的目标，只保留真正需要压缩的阶段
    targets = [t for t in dadda_seq if t < max(dots_in_col)]
    print(f" -> Dadda 目标高度收敛序列: {targets}")
    
    comp_cols_raw = []
    c_types_raw = []
    current_dots = list(dots_in_col)
    
    # 3. 按目标高度逐级扫荡压缩
    for stage_idx, target in enumerate(targets):
        current_len = len(current_dots)
        next_dots = [0] * current_len
        carry_from_prev = 0
        
        for col in range(current_len):
            V = current_dots[col]
            # 当前列在下一级期望达到的高度边界 (扣除上一列传来的进位后，本列允许留下的节点数)
            allowed_output = target - carry_from_prev
            
            if V > allowed_output:
                # 需要通过引入压缩器来削减的点数
                reduction_needed = V - allowed_output
                
                # 贪心分配：1 个 FA 削减 2 个高度，1 个 HA 削减 1 个高度
                f = reduction_needed // 2
                h = reduction_needed % 2
                
                for _ in range(f):
                    comp_cols_raw.append(col)
                    c_types_raw.append('FA')
                for _ in range(h):
                    comp_cols_raw.append(col)
                    c_types_raw.append('HA')
                    
                # 本列保留的点数 = 原有数量 - 削减的高度
                dots_stay = V - reduction_needed
                next_dots[col] = dots_stay + carry_from_prev
                carry_from_prev = f + h
            else:
                # 不需要压缩，全部透传，加上进位
                next_dots[col] = V + carry_from_prev
                carry_from_prev = 0
                
        # 最后一个进位如果存在，顺延到最高位的下一列
        if carry_from_prev > 0:
            next_dots.append(carry_from_prev)
            
        current_dots = next_dots
        
    final_max = max(current_dots)
    print(f" -> 压缩完毕！最终最大高度: {final_max}。")
    print(f" -> 申请 {len(comp_cols_raw)} 个压缩器画布 ({c_types_raw.count('FA')} FA, {c_types_raw.count('HA')} HA)。")
    
    if final_max > 2:
        print("\n[致命警告] Dadda 树未能将高度压缩至 2！请检查位宽逻辑。")
        
    # 4. [高危漏洞修复] 安全地将坑位和物理类型进行联合排序 (Zip Sort)
    # 确保无论 Stage 怎么穿插，列索引和分配给该列的门类型永远死死绑定
    combined = sorted(zip(comp_cols_raw, c_types_raw), key=lambda x: x[0])
    comp_cols = [x[0] for x in combined]
    c_types = [x[1] for x in combined]

    return pp_cols, comp_cols, c_types
    
def generate_dadda_init_matrix(bit_width, pp_cols, c_cols, c_types):
    """
    [Dr. Gemini 热启动引擎] 提取纯血 Dadda 树的硬连线逻辑，
    并转化为 DOMAC 连续概率矩阵的初始 Logits。
    """
    print(f"\n[Warm Start] 正在提取 Dadda 拓扑作为先验知识，初始化拓扑概率矩阵...")
    num_pp = len(pp_cols)
    num_c = len(c_cols)
    total_nodes = num_pp + 2 * num_c
    total_target_pins = num_c * 3
    
    # 初始化全 0 矩阵 (Logits)。之后会被 Softmax 转化为概率。
    m_logits = torch.zeros((total_nodes, total_target_pins + 1))
    
    max_cols = bit_width * 2 - 1
    signals = [[] for _ in range(max_cols)]
    
    # 1. 初始化 PP 信号源节点 ID (0 到 num_pp-1)
    k = 0
    for i in range(bit_width):
        for j in range(bit_width):
            signals[i+j].append(k)
            k += 1
            
    dadda_seq = [2]
    while dadda_seq[-1] < bit_width:
        dadda_seq.append(int(dadda_seq[-1] * 1.5))
    dadda_seq.reverse()
    targets = [t for t in dadda_seq if t < max([len(col) for col in signals])]
    
    # 2. 建立反向映射表：DOMAC 的压缩器是按列(col)排好序的，
    # 我们必须把 Dadda 生成过程中的压缩器准确映射到 DOMAC 的绝对索引 j 上。
    comp_index_map = {col: {'FA': [], 'HA': []} for col in range(max_cols)}
    for j, (col, c_type) in enumerate(zip(c_cols, c_types)):
        comp_index_map[col][c_type].append(j)
        
    comp_usage = {col: {'FA': 0, 'HA': 0} for col in range(max_cols)}
    
    # 3. 严格遵循 Dadda 算法，但这次我们记录连线索引！
    for stage_idx, target in enumerate(targets):
        next_signals = [[] for _ in range(max_cols + 1)]
        carry_from_prev = []
        
        for col in range(len(signals)):
            current_sigs = signals[col] + carry_from_prev
            V = len(current_sigs)
            
            if V > target:
                reduction_needed = V - target
                f = reduction_needed // 2
                h = reduction_needed % 2
                
                carries_generated = []
                
                for _ in range(f):
                    s1, s2, s3 = current_sigs.pop(), current_sigs.pop(), current_sigs.pop()
                    # 获取该 FA 在 DOMAC 体系下的绝对索引
                    j = comp_index_map[col]['FA'][comp_usage[col]['FA']]
                    comp_usage[col]['FA'] += 1
                    
                    # [注入先验偏置] 给 Dadda 的目标连线施加 10.0 的极高初始权重
                    m_logits[s1, j * 3 + 0] = 10.0
                    m_logits[s2, j * 3 + 1] = 10.0
                    m_logits[s3, j * 3 + 2] = 10.0
                    
                    # 生成下一级的节点 ID
                    next_signals[col].append(num_pp + j)       # S 输出
                    carries_generated.append(num_pp + num_c + j) # CO 输出
                    
                for _ in range(h):
                    s1, s2 = current_sigs.pop(), current_sigs.pop()
                    j = comp_index_map[col]['HA'][comp_usage[col]['HA']]
                    comp_usage[col]['HA'] += 1
                    
                    m_logits[s1, j * 3 + 0] = 10.0
                    m_logits[s2, j * 3 + 1] = 10.0
                    
                    next_signals[col].append(num_pp + j)
                    carries_generated.append(num_pp + num_c + j)
                    
                next_signals[col].extend(current_sigs)
                carry_from_prev = carries_generated
            else:
                next_signals[col].extend(current_sigs)
                carry_from_prev = []
                
        if carry_from_prev:
            if len(signals) >= len(next_signals):
                next_signals.append([])
            next_signals[len(signals)].extend(carry_from_prev)
            
        signals = next_signals

    # 4. 处理最终流向 CPA (Sink) 的剩余信号
    for i in range(total_nodes):
        # 如果某个节点没有任何一根引脚指向压缩器（最高 Logit 小于 5.0），说明它直接通向 Sink
        if torch.max(m_logits[i, :-1]) < 5.0:
            m_logits[i, -1] = 10.0
            
    print(f" -> Dadda 知识蒸馏完毕！已将 {int(torch.sum(m_logits == 10.0).item())} 根硬连线转化为高斯先验。")
    return m_logits

# ================= [探针 1：列高溢出探针] =================
def probe_column_height_overflow(model, discrete_M):
    """
    [DOMAC 探针] 最终输出到 CPA 的列高 (Column Height) 核查
    （原版保留了全部的注释与逻辑）
    """
    print("\n" + "="*60)
    print(" 🕵️ [DOMAC 探针] 最终输出到 CPA 的列高 (Column Height) 核查")
    print("="*60)

    # 1. 获取所有节点的列权重属性
    node_cols = model.node_cols

    # 2. 找出流向 Sink (下游 CPA) 的节点
    # 在 discrete_M 中，如果某一行全为 0，说明该节点没有连向任何内部压缩器引脚，必然流向了 Sink
    row_sums = torch.sum(discrete_M, dim=1)
    nodes_to_sink = torch.where(row_sums == 0)[0].tolist()

    # 3. 提取这些残余节点的列权重，并统计每一列的数量
    sink_weights = [node_cols[i] for i in nodes_to_sink]
    col_counts = Counter(sink_weights)
    
    overflow_detected = False
    for col, count in sorted(col_counts.items()):
        if count > 2:
            # 超过 2 个信号，必然触发 DC 综合工具的多重 CPA 级联雪崩！
            print(f" 🚨 [致命溢出] 第 {col:>2} 列: 残留了 {count} 个未压缩信号！")
            overflow_detected = True
        else:
            print(f" ✅ [正常]     第 {col:>2} 列: 残留 {count} 个信号")

    if overflow_detected:
        print("\n ⚠️ 结论：列压缩未彻底完成！")
        print("    下游 DC 综合工具将被迫把多余的信号强行跨接 (如 intadd_1 -> intadd_0)，导致 0.4ns+ 的时序雪崩！")
    else:
        print("\n 完美：所有列已严格压缩至 <= 2，完全符合进入单一高速 CPA 的条件。")
    print("="*60 + "\n")

# ================= [探针 2：离散化后硬连线物理评估 & WNS 溯源] =================
def probe_post_legalization_eval(model, loss_engine, trainer_hyperparams, discrete_M, discrete_P, final_P, pp_at, pp_slew, REQ_TIME, PP_COLS, COMP_COLS):
    print("\n[Evaluator] 正在对坍缩后的 0/1 离散硬连线进行最终物理时序核算...")
    with torch.no_grad():
        # 1. 构造离散化物理尺寸的 One-Hot 张量
        discrete_P_tensor = torch.zeros_like(final_P)
        for i, idx in enumerate(discrete_P):
            discrete_P_tensor[i, idx] = 1.0
            
        # 2. 构造包含 Sink (CPA) 列的完整离散连线矩阵
        discrete_M_full = torch.zeros_like(model.m_logits)
        discrete_M_full[:, :-1] = discrete_M
        # 匈牙利算法没有分给压缩树的引脚，必定全部流向了最后的 CPA (Sink)
        row_sums = torch.sum(discrete_M, dim=1)
        discrete_M_full[row_sums == 0, -1] = 1.0

        # 3. 备份原本训练结束时的模糊 logits
        orig_m_logits = model.m_logits.clone()
        orig_p_logits = model.p_logits.clone()

        # 4. [核心技巧] 注入极端 Logits 强制网络走硬连线
        new_m_logits = torch.full_like(orig_m_logits, -1e4)
        new_m_logits[discrete_M_full == 1.0] = 1e4
        model.m_logits.copy_(new_m_logits)

        new_p_logits = torch.full_like(orig_p_logits, -1e4)
        new_p_logits[discrete_P_tensor == 1.0] = 1e4
        model.p_logits.copy_(new_p_logits)

        # 5. 执行一次纯净的前向传播与 Loss 计算
        eval_wns, eval_tns, eval_area, eval_M, eval_P = model(pp_at, pp_slew, tau=1.0)
        eval_loss, eval_dict = loss_engine(
            eval_wns, eval_tns, eval_area, eval_M, eval_P, trainer_hyperparams, 
            model.active_pin_mask, model.c_types
        )

        print(f" -> [坍缩后真实指标] WNS: {eval_dict['wns'].item():.4f} ns | "
              f"Area: {eval_dict['area'].item():.4f} μm² | "
              f"L_BM: {eval_dict['l_bm'].item():.4f} | "
              f"Total Loss: {eval_loss.item():.4f}")
        
        # ================= [WNS 计算过程溯源探针] =================
        print("\n" + "="*60)
        print(" 🧮 [DOMAC 探针] 离散化网表 WNS 内部计算逻辑核对")
        print("="*60)
        
        # 1. 提取离散化评估后的全图所有节点的 AT (到达时间)
        all_ats = model._probe_node_ats.detach().cpu().numpy()
        req_time = REQ_TIME 
        
        # 2. 计算每个节点的 Slack (容限)
        slacks = req_time - all_ats
        
        # 3. 找出全图 Slack 最差的节点 (即 AT 最大的节点)
        worst_idx = np.argmin(slacks)
        worst_at = all_ats[worst_idx]
        worst_slack = slacks[worst_idx]
        
        # 4. 翻译这个“罪魁祸首”节点的物理身份
        num_pp = len(PP_COLS)
        num_c = len(COMP_COLS)
        if worst_idx < num_pp:
            node_name = f"原始输入信号 PP_in_{worst_idx}"
        elif worst_idx < num_pp + num_c:
            c_idx = worst_idx - num_pp
            node_name = f"压缩器 U_comp_{c_idx} 的 S (Sum) 输出引脚"
        else:
            c_idx = worst_idx - num_pp - num_c
            node_name = f"压缩器 U_comp_{c_idx} 的 CO (Carry-Out) 输出引脚"
            
        print(f" -> 1. 设定的目标到达时间 (REQ_TIME) : {req_time:.4f} ns")
        print(f" -> 2. 全局最慢的关键节点判定为     : {node_name}")
        print(f" -> 3. 查表计算的该节点实际 AT      : {worst_at:.4f} ns")
        print(f" -> 4. 原始负超额 (Negative Slack)  : {min(0.0, worst_slack):.4f} ns")
        print(f" -> 5. AI 最终汇报的平滑 eval_wns   : {eval_wns.item():.4f} ns")
        print("="*60 + "\n")

        # 6. 恢复原本的 logits (保持代码状态安全)
        model.m_logits.copy_(orig_m_logits)
        model.p_logits.copy_(orig_p_logits)

# ================= [探针 3：波前到达时间 (Wavefront AT)] =================
def probe_wavefront_at(model, discrete_M):
    print("\n" + "="*65)
    print(" 🌊 [DOMAC 探针] CPA 输入波前到达时间 (Wavefront AT) 剖析")
    print("="*65)
    
    # 提取离散化评估后，全图节点的真实物理到达时间
    node_ats = model._probe_node_ats.detach().cpu().numpy()
    node_cols = model.node_cols
    
    # 找出流向 Sink 的节点 (行和为 0 的离散 M)
    row_sums = torch.sum(discrete_M, dim=1)
    nodes_to_sink = torch.where(row_sums == 0)[0].tolist()
    
    # 按照列(Column)分类收集这些节点的 AT
    col_to_ats = {}
    for idx in nodes_to_sink:
        col = node_cols[idx]
        at = node_ats[idx]
        if col not in col_to_ats:
            col_to_ats[col] = []
        col_to_ats[col].append(at)
        
    print(f"{'比特位 (Column)':<15} | {'交付给 CPA 的最晚时间 (Max AT)':<25} | {'波前状态诊断'}")
    print("-" * 65)
    
    for col in sorted(col_to_ats.keys()):
        max_at = max(col_to_ats[col])
        if col < 7 and max_at > 0.18:
            status = "🚨 危险 (波前倒置/低位滞后)"
        elif col >= 7 and max_at > 0.28:
            status = "⚠️ 偏高 (全局延迟瓶颈)"
        else:
            status = "✅ 优秀 (符合 CPA 期望)"
            
        print(f" Col {col:<10} | {max_at:.4f} ns{'':<16} | {status}")
        
    print("="*65 + "\n")
```

### `src/export/verilog_gen.py`

```python
import torch

class VerilogGenerator:
    def __init__(self, pp_cols, c_cols, c_types, fa_cell_names, ha_cell_names, module_name="domac_tree"):
        """
        [Dr. Gemini 终极版] RTL 网表与 Testbench 双生生成器
        """
        self.pp_cols = pp_cols
        self.c_cols = c_cols
        self.num_pp = len(pp_cols)
        self.num_c = len(c_cols)
        self.c_types = c_types
        self.module_name = module_name
        self.fa_cell_names = fa_cell_names
        self.ha_cell_names = ha_cell_names
        
        # 缓存输出端口的权重信息，供 TB 使用
        self.tb_output_ports = [] 

    def generate(self, discrete_M, discrete_P, output_file="output_netlist.v"):
        print(f"\n[VerilogGen] 正在将矩阵拓扑编译为纯血 RTL 网表: {output_file}")
        
        total_nodes = self.num_pp + 2 * self.num_c
        
        wire_names = [f"pp_in_{i}" for i in range(self.num_pp)]
        wire_names += [f"comp_{j}_S" for j in range(self.num_c)]
        wire_names += [f"comp_{j}_CO" for j in range(self.num_c)]
            
        with open(output_file, 'w') as f:
            f.write(f"module {self.module_name} (\n")
            f.write(f"    input wire {', '.join(wire_names[:self.num_pp])}")
            
            output_ports = []
            assign_statements = []
            self.tb_output_ports = [] # 清空缓存
            
            row_sums = torch.sum(discrete_M, dim=1).tolist()
            
            for i in range(total_nodes):
                if row_sums[i] == 0: 
                    if i < self.num_pp:
                        out_name = f"out_pp_{i}"
                        output_ports.append(out_name)
                        assign_statements.append(f"    assign {out_name} = {wire_names[i]};")
                        self.tb_output_ports.append((out_name, self.pp_cols[i])) # 记录直通 PP 的权重
                    else:
                        out_name = wire_names[i]
                        output_ports.append(out_name)
                        
                        # 解析是 S 还是 CO，并记录对应的物理权重
                        if "_S" in out_name:
                            j = int(out_name.split("_")[1])
                            self.tb_output_ports.append((out_name, self.c_cols[j]))
                        elif "_CO" in out_name:
                            j = int(out_name.split("_")[1])
                            self.tb_output_ports.append((out_name, self.c_cols[j] + 1)) # 进位权重 +1
                         
            if output_ports:
                f.write(f",\n    output wire {', '.join(output_ports)}\n);\n\n")
            else:
                f.write("\n);\n\n")
            
            f.write("    // Internal wire declarations\n")
            for j in range(self.num_c):
                s_wire = f"comp_{j}_S"
                co_wire = f"comp_{j}_CO"
                if s_wire not in output_ports: f.write(f"    wire {s_wire};\n")
                if co_wire not in output_ports: f.write(f"    wire {co_wire};\n")
            f.write("\n")
            
            if assign_statements:
                f.write("    // Feed-through assignments\n")
                f.write("\n".join(assign_statements) + "\n\n")

            f.write("    // Compressor Tree Instantiations\n")
            for j in range(self.num_c):
                c_type = self.c_types[j]
                impl_idx = discrete_P[j]
                
                if c_type == 'FA':
                    cell_name = self.fa_cell_names[impl_idx]
                    inputs = ['A', 'B', 'CI']
                else:
                    cell_name = self.ha_cell_names[impl_idx]
                    inputs = ['A', 'B']
                    
                f.write(f"    {cell_name} U_comp_{j} (\n")
                
                for p_idx, pin_name in enumerate(inputs):
                    col_idx = j * 3 + p_idx 
                    connected_source = None
                    for i in range(total_nodes):
                        if discrete_M[i, col_idx] == 1.0:
                            connected_source = wire_names[i]
                            break
                    if connected_source is None:
                        raise ValueError(f"[物理崩塌] 压缩器 {j} 的 {pin_name} 引脚悬空！")
                    f.write(f"        .{pin_name}({connected_source}),\n")
                
                f.write(f"        .S(comp_{j}_S),\n        .CO(comp_{j}_CO)\n    );\n\n")
            f.write("endmodule\n")
            
        print(f"[VerilogGen] 物理网表已成功封盒！")

    def generate_multiplier_top(self, bit_width, top_file="domac.v", ct_module_name="domac_tree", top_module_name="domac"):
        """
        自动生成完整的乘法器顶层封装模块
        包含: PPG (部分积生成阵列) + CT (DOMAC 压缩树) + CPA (末级加法器)
        """
        print(f"[VerilogGen] 正在组装完整乘法器顶层模块: {top_file}")
        
        out_width = bit_width * 2
        
        with open(top_file, 'w') as f:
            f.write(f"`timescale 1ns/1ps\n\n")
            f.write(f"module {top_module_name} (\n")
            f.write(f"    input  wire [{bit_width-1}:0] A,\n")
            f.write(f"    input  wire [{bit_width-1}:0] B,\n")
            f.write(f"    output wire [{out_width-1}:0] P\n")
            f.write(f");\n\n")
            
            f.write("    // ==========================================\n")
            f.write("    // 1. Partial Product Generator (PPG) 阵列\n")
            f.write("    // ==========================================\n")
            pp_wire_names = []
            k = 0
            for i in range(bit_width):
                for j in range(bit_width):
                    wire_name = f"pp_in_{k}"
                    pp_wire_names.append(wire_name)
                    # 硬件并行生成部分积：A的第i位 AND B的第j位
                    f.write(f"    wire {wire_name} = A[{i}] & B[{j}];\n")
                    k += 1
            f.write("\n")
            
            f.write("    // ==========================================\n")
            f.write("    // 2. DOMAC AI 优化压缩树 (CT)\n")
            f.write("    // ==========================================\n")
            # 声明 CT 输出的那些毫无规律的杂散线
            out_wires = [port[0] for port in self.tb_output_ports]
            f.write(f"    wire {', '.join(out_wires)};\n\n")
            
            f.write(f"    {ct_module_name} U_CT (\n")
            
            # 绑定输入
            port_bindings = []
            for i in range(self.num_pp):
                port_bindings.append(f"        .pp_in_{i}(pp_in_{i})")
            
            # 绑定输出
            for out_name in out_wires:
                port_bindings.append(f"        .{out_name}({out_name})")
                
            f.write(",\n".join(port_bindings) + "\n")
            f.write("    );\n\n")
            
            f.write("    // ==========================================\n")
            f.write("    // 3. Carry-Propagate Adder (CPA) 加法器\n")
            f.write("    // ==========================================\n")
            f.write("    // 将压缩树残留的杂散信号按二进制权重对齐重建，送入高速 CPA\n")
            
            # 分类收集不同权重的信号
            col_signals = {w: [] for w in range(out_width)}
            for out_name, weight in self.tb_output_ports:
                col_signals[weight].append(out_name)
                
            # 动态重建向量: 保证能够被标准的 assign P = vec0 + vec1 完美吸收
            # 如果某列刚好压缩到剩 2 根线，这里就会生成 vec_0 和 vec_1 两个 32-bit 向量
            max_depth = max([len(sigs) for sigs in col_signals.values()])
            
            vec_names = []
            for d in range(max_depth):
                vec_name = f"cpa_vec_{d}"
                vec_names.append(vec_name)
                f.write(f"    wire [{out_width-1}:0] {vec_name};\n")
                
                # 为该向量的每一位赋值
                for w in range(out_width):
                    if d < len(col_signals[w]):
                        f.write(f"    assign {vec_name}[{w}] = {col_signals[w][d]};\n")
                    else:
                        f.write(f"    assign {vec_name}[{w}] = 1'b0; // 缺位补零\n")
                f.write("\n")
            
            f.write("    // 综合工具 (Design Compiler) 会将下述加法自动推断为极速并行前缀加法器\n")
            sum_expr = " + ".join(vec_names)
            f.write(f"    assign P = {sum_expr};\n\n")
            
            f.write("endmodule\n")
            
        print(f"[VerilogGen] 顶层模块封装完毕！可直接送入综合工具。")

    def generate_pure_dadda_baseline(self, bit_width, output_file="dadda_baseline_ct.v", top_file="dadda.v"):
        """
        [Dr. Gemini 基准线生成器] 直接输出纯正的 Dadda Tree 初始 Verilog 网表
        用于控制变量法对照实验 (Control Experiment)
        """
        print(f"\n[BaselineGen] 启动纯血 Dadda Tree 基准网表生成器...")
        
        # 默认使用索引 0 的物理单元作为基础构建块 (通常是驱动最小的 D0 或基础 D1)
        fa_name = self.fa_cell_names[0]
        ha_name = self.ha_cell_names[0]
        
        max_cols = bit_width * 2 - 1
        signals = [[] for _ in range(max_cols)]
        
        # 1. 初始化部分积信号池
        k = 0
        for i in range(bit_width):
            for j in range(bit_width):
                signals[i+j].append(f"pp_in_{k}")
                k += 1
                
        # 2. 推导目标高度序列
        dadda_seq = [2]
        while dadda_seq[-1] < bit_width:
            dadda_seq.append(int(dadda_seq[-1] * 1.5))
        dadda_seq.reverse()
        targets = [t for t in dadda_seq if t < max([len(col) for col in signals])]
        
        verilog_lines = []
        comp_idx = 0
        
        # 3. 严格遵循 Dadda 算法逐级收敛连线
        for stage_idx, target in enumerate(targets):
            next_signals = [[] for _ in range(max_cols + 1)]
            carry_from_prev = []
            
            for col in range(len(signals)):
                # Dadda 物理连线法则：当前列未压缩的点 + 上一列传来的进位，共同构成当前列的总点数
                current_sigs = signals[col] + carry_from_prev
                V = len(current_sigs)
                
                if V > target:
                    reduction_needed = V - target
                    f = reduction_needed // 2
                    h = reduction_needed % 2
                    
                    carries_generated = []
                    
                    for _ in range(f):
                        s1 = current_sigs.pop()
                        s2 = current_sigs.pop()
                        s3 = current_sigs.pop()
                        s_out = f"comp_{comp_idx}_S"
                        co_out = f"comp_{comp_idx}_CO"
                        verilog_lines.append(f"    {fa_name} U_comp_{comp_idx} (.A({s1}), .B({s2}), .CI({s3}), .S({s_out}), .CO({co_out}));")
                        comp_idx += 1
                        next_signals[col].append(s_out)
                        carries_generated.append(co_out)
                        
                    for _ in range(h):
                        s1 = current_sigs.pop()
                        s2 = current_sigs.pop()
                        s_out = f"comp_{comp_idx}_S"
                        co_out = f"comp_{comp_idx}_CO"
                        verilog_lines.append(f"    {ha_name} U_comp_{comp_idx} (.A({s1}), .B({s2}), .S({s_out}), .CO({co_out}));")
                        comp_idx += 1
                        next_signals[col].append(s_out)
                        carries_generated.append(co_out)
                        
                    next_signals[col].extend(current_sigs)
                    carry_from_prev = carries_generated
                else:
                    next_signals[col].extend(current_sigs)
                    carry_from_prev = []
                    
            if carry_from_prev:
                if len(signals) >= len(next_signals):
                    next_signals.append([])
                next_signals[len(signals)].extend(carry_from_prev)
                
            signals = next_signals

        while signals and not signals[-1]:
            signals.pop()
            
        # 4. 收集最终输出端口与权重映射
        outputs_with_weights = []
        assign_lines = []
        for col, sigs in enumerate(signals):
            for sig in sigs:
                if sig.startswith("pp_in_"):
                    # 如果有初级信号一刀未剪直达底层，需赋予别名
                    out_name = f"out_{sig}"
                    assign_lines.append(f"    assign {out_name} = {sig};")
                    outputs_with_weights.append((out_name, col))
                else:
                    outputs_with_weights.append((sig, col))
                    
        # 5. 生成压缩树 (CT) 网表文件
        with open(output_file, 'w') as f:
            f.write("module dadda_baseline_ct (\n")
            inputs = [f"pp_in_{i}" for i in range(bit_width * bit_width)]
            f.write(f"    input wire {', '.join(inputs)},\n")
            outputs = [name for name, _ in outputs_with_weights]
            f.write(f"    output wire {', '.join(outputs)}\n")
            f.write(");\n\n")
            
            internal_wires = [f"comp_{i}_S" for i in range(comp_idx)] + [f"comp_{i}_CO" for i in range(comp_idx)]
            internal_wires_to_declare = [w for w in internal_wires if w not in outputs]
            
            if internal_wires_to_declare:
                f.write("    wire ")
                for idx, w in enumerate(internal_wires_to_declare):
                    f.write(w)
                    if idx < len(internal_wires_to_declare) - 1:
                        f.write(", ")
                    if (idx + 1) % 10 == 0:
                        f.write("\n         ")
                f.write(";\n\n")
                
            if assign_lines:
                f.write("\n".join(assign_lines) + "\n\n")
                
            f.write("\n".join(verilog_lines))
            f.write("\nendmodule\n")

        # 6. 巧妙复用已有的生成器，组装顶层乘法器 (Top Module)
        original_tb_ports = self.tb_output_ports
        self.tb_output_ports = outputs_with_weights
        
        # 显式指定对照组的 Top 模块名为 dadda
        self.generate_multiplier_top(bit_width, top_file=top_file, ct_module_name="dadda_baseline_ct", top_module_name="dadda")
        
        self.tb_output_ports = original_tb_ports # 恢复现场
        print(f"[BaselineGen] 纯血 Dadda 初始基准网表生成完毕！")
        print(f"  -> CT 核心网表: {output_file}")
        print(f"  -> Top 顶层装配: {top_file}")

```

