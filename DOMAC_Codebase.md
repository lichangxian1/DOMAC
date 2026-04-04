# DOMAC_TSMC28 工程代码全局快照

**Root Directory:** `/home/changxian/DOMAC_TSMC28`

### `domac.py`

```python
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

USE_BOOTH = False   # 想切换时只改这一行

if USE_BOOTH:
    from src.export.verilog_gen_booth import VerilogGenerator
    from src.core.domac_utils_booth import (
        create_physical_tensor_mock,
        generate_multiplier_canvas,
        generate_dadda_init_matrix,
        probe_column_height_overflow,
        probe_post_legalization_eval,
        probe_wavefront_at
    )
else:
    from src.export.verilog_gen import VerilogGenerator
    from src.core.domac_utils import (
        create_physical_tensor_mock,
        generate_multiplier_canvas,
        generate_dadda_init_matrix,
        probe_column_height_overflow,
        probe_post_legalization_eval,
        probe_wavefront_at,
        build_local_routing_graph
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
    # TARGET_CELLS = ['FA_X1', 'HA_X1']

    fa_names = [c for c in TARGET_CELLS if c.startswith('FA')]
    ha_names = [c for c in TARGET_CELLS if c.startswith('HA')]
    
    try:
        lib_path = "/home/changxian/library/t28_official/tcbn28hpcplusbwp12t40p140tt0p9v25c.lib"
        # lib_path = "/home/changxian/freepdk-45nm-master/stdcells.lib"
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
    if USE_BOOTH:
        PP_COLS, COMP_COLS, C_TYPES, PP_AT_INIT = generate_multiplier_canvas(BIT_WIDTH)
    else:
        PP_COLS, COMP_COLS, C_TYPES = generate_multiplier_canvas(BIT_WIDTH)
    NUM_PP = len(PP_COLS)
    NUM_COMPRESSORS = len(COMP_COLS)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\n[System] 核心计算引擎将挂载至: {device}")
    if torch.cuda.is_available():
        print(f" -> 检测到显卡: {torch.cuda.get_device_name(0)}")
        torch.backends.cudnn.benchmark = True 

    # 【核心修复】将真实物理延迟作为 Tensor 喂给 AI
    if USE_BOOTH:
        pp_at = torch.tensor(PP_AT_INIT, dtype=torch.float32, device=device)
    else:
        pp_at = torch.full((NUM_PP,), 0.1, device=device)
    pp_slew = torch.full((NUM_PP,), 0.02, device=device)
    REQ_TIME = 0 
    print("REQ_TIME：" + str(REQ_TIME))

    print(f"\n[Engine] 构建异构可微压缩树...")
    max_impls = max(len(fa_tensors), len(ha_tensors))
    BASELINE_GATE_INDEX = 1 
    safe_gate_idx = BASELINE_GATE_INDEX if max_impls > BASELINE_GATE_INDEX else 0

    # =======================================================
    # 替换 2：净化初始化逻辑，彻底移除没用的旧版全局矩阵
    # =======================================================
    init_p = None
    if INIT_MODE == 'dadda':
        print(f" -> [Init] 采用 Dadda 树物理先验热启动 (物理门初始尺寸: D{safe_gate_idx})")
        init_p = torch.zeros((NUM_COMPRESSORS, max_impls))
        init_p[:, safe_gate_idx] = 10.0  
    elif INIT_MODE == 'blank':
        print(f" -> [Init] 采用纯随机冷启动 (拓扑随机，物理门随机)")
        init_p = torch.zeros((NUM_COMPRESSORS, max_impls))

    routing_stages, total_virtual_nodes = build_local_routing_graph(BIT_WIDTH, PP_COLS, COMP_COLS, C_TYPES)

    model = DOMAC_CompressorTree(
        PP_COLS, COMP_COLS, fa_tensors, ha_tensors, C_TYPES, REQ_TIME, 
        routing_stages=routing_stages,
        total_virtual_nodes=total_virtual_nodes,
        init_mode=INIT_MODE,   
        init_p_logits=init_p,  # <--- 修复：完美注入物理先验
        device=device
    ).to(device)

    loss_engine = DOMACLossFunction()
    trainer = DOMACTrainer(model, loss_engine, lr=0.066)
    
    print("\n[Engine] 物理映射与梯度反向传播开始...")
    start_time = time.time()
    final_local_M, final_P = trainer.train(pp_at, pp_slew, max_epochs=270)
    
    print("\n[System] 优化执行完毕！网表拓扑已坍缩至离散界限附近。")
    
    legalizer = DOMACLegalizer()
    discrete_local_M, discrete_P, global_M = legalizer.legalize(
        final_local_M, final_P, model.local_meta, NUM_PP, NUM_COMPRESSORS
    )
    
    # ================= [探针区] =================
    probe_post_legalization_eval(
        model=model, 
        loss_engine=loss_engine, 
        trainer_hyperparams=trainer.hyperparams, 
        discrete_local_M=discrete_local_M,  
        discrete_P=discrete_P, 
        final_P=final_P, 
        pp_at=pp_at, 
        pp_slew=pp_slew, 
        REQ_TIME=REQ_TIME, 
        PP_COLS=PP_COLS, 
        COMP_COLS=COMP_COLS
    )

    probe_wavefront_at(model=model, discrete_M=global_M[:, :-1])

    # =======================================================
    # 替换 3：重组网表生成逻辑，直接调用原生 Baseline 发生器
    # =======================================================
    os.makedirs("output/netlists", exist_ok=True)
    v_gen = VerilogGenerator(
        pp_cols=PP_COLS, c_cols=COMP_COLS, c_types=C_TYPES,
        fa_cell_names=fa_names, ha_cell_names=ha_names
    )
    
    netlist_path = f"output/netlists/domac_tree_{BIT_WIDTH}.v"
    v_gen.generate(global_M[:, :-1], discrete_P, output_file=netlist_path)
    
    top_path = f"output/netlists/domac_{BIT_WIDTH}.v"
    v_gen.generate_multiplier_top(
        bit_width=BIT_WIDTH, top_file=top_path, 
        ct_module_name="domac_tree", top_module_name="domac"
    )
    
    # 极简、安全的基准网表生成
    if INIT_MODE == 'dadda':
        print(f"\n[BaselineGen] 正在直接从架构底层推演纯血 Dadda 基准网表...")
        v_gen.generate_pure_dadda_baseline(
            bit_width=BIT_WIDTH,
            output_file=f"output/netlists/{INIT_MODE}_tree_{BIT_WIDTH}.v",
            top_file=f"output/netlists/{INIT_MODE}_{BIT_WIDTH}.v"
        )
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
    # NANGATE_LIB_PATH = "/home/changxian/freepdk-45nm-master/stdcells.lib"
    # TARGET_CELLS = ['FA_X1', 'HA_X1'] 
    # parser = NLDMParser(NANGATE_LIB_PATH, TARGET_CELLS)
    
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
            't1': 1.45,     # WNS 权重拉到极致，逼迫网络突破延迟极限
            't2': 0.4,       # TNS 辅助全局路径寻优
            'alpha': 1,    # 【封印】前期绝对不许管面积！
            'lambda1': 0.66,  # 连线合法性是必须的
            'lambda2': 0.24,  # 【封印】前期不许进行二值化坍缩！让概率保持连续，充分探索！
            'tau_k':0.985,
            'beta': 0.00125,  
        }
        
        # self.hyperparams = {
        #     't1': 3.4,     # WNS 权重拉到极致，逼迫网络突破延迟极限
        #     't2': 0.35,       # TNS 辅助全局路径寻优
        #     'alpha': 1,    # 【封印】前期绝对不许管面积！
        #     'lambda1': 0.25,  # 连线合法性是必须的
        #     'lambda2': 0.12,  # 【封印】前期不许进行二值化坍缩！让概率保持连续，充分探索！
        #     'tau_k':0.995,
        #     'beta': 100,     # 新增：毛刺功耗权重，适度关注毛刺下降但不至于过早牺牲性能
        # }
 
    def update_hyperparameters(self, epoch):
        if 100 <= epoch < 200:
            self.hyperparams['t1'] *= 1.005       # WNS (Performance) 绝对优先，持续缓慢施压
            self.hyperparams['t2'] *= 1.005
            self.hyperparams['beta'] *= 1.01      # [修复点] 将 1.05 降到 1.01，温和引入功耗惩罚，平滑到达时间
            self.hyperparams['lambda1'] *= 1.01   # 连线合法性必须逐步收紧
            self.hyperparams['lambda2'] *= 1.01
            # 核心逻辑：此阶段 alpha (面积) 保持冰封或原样，给功耗优化留出绝对的空间

        # 阶段 3 (Epoch 200 之后): 面积回收与物理坍缩
        elif epoch >= 200:
            self.hyperparams['t1'] *= 1.005       # 时序霸权不可动摇
            self.hyperparams['t2'] *= 1.005
            self.hyperparams['beta'] *= 1.002     # 功耗压制转为平稳维持（防暴涨）
            self.hyperparams['alpha'] *= 1.01     # 面积 (Area) 垫底，此时才开始发力清理冗余逻辑门
            self.hyperparams['lambda1'] *= 1.02   # 逼近 Legalizer，增强合法性惩罚
            self.hyperparams['lambda2'] *= 1.05   # 终极二值化施压，逼迫概率走向 0 或 1
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
            wns, tns, area, glitch, local_M_probs, P_c = self.model(pp_at, pp_slew, tau=current_tau)
            t1 = time.time()
            acc_forward += (t1 - t0)
            
            # ================= [探针 2: 目标与约束 Loss 计算] =================
            total_loss, loss_dict = self.loss_engine(
                wns, tns, area, glitch, local_M_probs, P_c, self.hyperparams, self.model.local_meta
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
                      f"Glitch: {loss_dict['glitch'].item():.4f} | " # <--- 【新增监控】
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
                max_probs_list = [torch.max(m, dim=0)[0] for m in local_M_probs]
                if max_probs_list:
                    all_max_probs = torch.cat(max_probs_list)
                    avg_max_prob = torch.mean(all_max_probs).item()
                    cheating_pins = torch.sum(all_max_probs < 0.95).item()
                else:
                    avg_max_prob = 1.0
                    cheating_pins = 0
                    
                print(f"  -> [探针] 局部矩阵最大连接概率均值: {avg_max_prob:.4f} (趋近 1.0 为纯粹硬连线)")
                print(f"  -> [探针] 发现 {cheating_pins} 个局部引脚存在小数稀释。")
                
                pin_ats = self.model._probe_pin_ats
                worst_pin_idx = torch.argmax(pin_ats).item()
                worst_expected_at = pin_ats[worst_pin_idx].item()
                print(f"\n  🔍 [时序深度穿透] 观测最差引脚全局 Index: {worst_pin_idx} | 连续域期望 AT: {worst_expected_at:.4f} ns")
                print(f"  ⚠️  [架构升级] 局部级联架构已激活，跨级倒流已被物理封锁。")

        print("[Optimizer] 训练收敛完成。")
        return [m.detach() for m in local_M_probs], P_c.detach()
```

### `src/optimizer/legalizer.py`

```python
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
```

### `src/core/compressor_tree.py`

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
from .diff_sta import smooth_max_lse, diff_bilinear_interp

class DOMAC_CompressorTree(nn.Module):
    # 注意：接口中去掉了无用的 init_m_logits，新增了 routing_stages, total_virtual_nodes 和 init_mode
    def __init__(self, pp_cols, c_cols, fa_tensors, ha_tensors, c_types, req_time, 
                 routing_stages, total_virtual_nodes, init_mode='blank', device='cpu', init_p_logits=None):
        super(DOMAC_CompressorTree, self).__init__()
        self.device = device  # <--- [核心新增] 记住目标设备
        self.pp_cols = pp_cols
        self.c_cols = c_cols
        self.num_pp = len(pp_cols)
        self.num_c = len(c_cols)
        self.c_types = c_types
        self.req_time = req_time
        
        # 记录所有虚拟节点的列权重 (Column)，供最终 CPA 惩罚使用
        self.total_virtual_nodes = total_virtual_nodes
        self.virtual_node_cols = torch.zeros(self.total_virtual_nodes, dtype=torch.long, device=device)
        self.virtual_node_cols[:self.num_pp] = torch.tensor(pp_cols, device=device)
        self.virtual_node_cols[self.num_pp : self.num_pp+self.num_c] = torch.tensor(c_cols, device=device)
        self.virtual_node_cols[self.num_pp+self.num_c : self.num_pp+2*self.num_c] = torch.tensor([c+1 for c in c_cols], device=device)
        
        self.pin_names = ['A', 'B', 'CI']
        self.num_pins_per_c = len(self.pin_names)
        
        # 1. 预编译为 3D 张量的物理库
        self.fa_areas, self.fa_caps, self.fa_arcs = self._parse_tensors(fa_tensors)
        self.ha_areas, self.ha_caps, self.ha_arcs = self._parse_tensors(ha_tensors)
        self.num_fa_impls = len(fa_tensors)
        self.num_ha_impls = len(ha_tensors)
        self.max_impls = max(self.num_fa_impls, self.num_ha_impls)
        
        # 2. 物理实现选取器 P_c (保持全局映射)
        if init_p_logits is not None:
            self.p_logits = nn.Parameter(init_p_logits.clone().to(device))
        else:
            self.p_logits = nn.Parameter(torch.zeros(self.num_c, self.max_impls, device=device))
            
        p_mask = torch.zeros(self.num_c, self.max_impls, device=device)
        for j, c_type in enumerate(self.c_types):
            if c_type == 'FA':
                p_mask[j, self.num_fa_impls:] = float('-inf')
            else:
                p_mask[j, self.num_ha_impls:] = float('-inf')
        self.register_buffer('p_mask', p_mask)
        
        # =========================================================================
        # 🚀 [架构重构] 注册局部级联矩阵群 (Local Matrix ParameterList)
        # =========================================================================
        self.local_m_logits = nn.ParameterList()
        self.local_meta = []
        
        for stage_meta in routing_stages:
            for meta in stage_meta:
                num_in = len(meta['in_wires'])
                num_pins = len(meta['pin_global_indices'])
                num_bypass = len(meta['out_bypass_ids'])
                num_out_cols = num_pins + num_bypass
                
                # 记录 Bypass 虚拟线的位权
                col = meta['col']
                for b_id in meta['out_bypass_ids']:
                    self.virtual_node_cols[b_id] = col
                    
                if num_in > 0 and num_out_cols > 0:
                    # [极简热启动] 如果是 Dadda 模式，直接用单位矩阵主对角线硬连线！
                    if init_mode == 'dadda' and num_in == num_out_cols:
                        m_ij = nn.Parameter(torch.eye(num_in, num_out_cols, device=device) * 10.0)
                    else:
                        m_ij = nn.Parameter(torch.randn(num_in, num_out_cols, device=device) * 0.01)
                        
                    self.local_m_logits.append(m_ij)
                    
                    # 存储元数据以供前向传播查表
                    self.local_meta.append({
                        'in_wires': meta['in_wires'],
                        'fa_ids': meta['fa_ids'],
                        'ha_ids': meta['ha_ids'],
                        'out_bypass_ids': meta['out_bypass_ids'],
                        'pin_global_indices': meta['pin_global_indices'],
                        'matrix_idx': len(self.local_m_logits) - 1,
                        'num_pins': num_pins,
                        'num_bypass': num_bypass
                    })
        # ========== [请在 __init__ 的最后补充这几行] ==========
        active_pin_mask = torch.zeros(self.num_c * self.num_pins_per_c, device=device)
        for j, c_type in enumerate(self.c_types):
            if c_type == 'FA': active_pin_mask[j*3 : j*3+3] = 1.0
            else: active_pin_mask[j*3 : j*3+2] = 1.0
        self.register_buffer('active_pin_mask', active_pin_mask)

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
            # ==========================================================
            # 1. 严格面积审查 (拒绝默认值 1.0)
            # ==========================================================
        for ct_idx, ct in enumerate(tensors):
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
        
        # 1. 提前计算所有物理压缩器的输入引脚期望电容与面积
        global_pin_caps = torch.zeros(self.num_c * 3, device=self.device)

        expected_area = 0.0

        for j, c_type in enumerate(self.c_types):
            is_fa = (c_type == 'FA')
            lib_areas = self.fa_areas if is_fa else self.ha_areas
            lib_caps = self.fa_caps if is_fa else self.ha_caps

            p_j = P_c[j, :self.num_fa_impls] if is_fa else P_c[j, :self.num_ha_impls]
            
            expected_area = expected_area + torch.sum(p_j * lib_areas)
            global_pin_caps[j*3 : j*3+3] = p_j @ lib_caps

        # 2. 从后向前计算反向导线电容负载 (Backward Load Propagation)
        # 这完美解决了局部矩阵架构下跨级连线的负载溯源问题
        node_loads = torch.zeros(self.total_virtual_nodes, device=self.device)
        # ================= [核心物理修复：引入线负载模型 WLM] =================
        # 假设 TSMC 28nm 下，一根跨 Cell 互连线的平均寄生电容约为 0.003 pF (3 fF)
        # 你可以根据实际库的情况微调这个值
        WIRE_CAP_PER_NET = 0.000 
        
        local_M_probs = [F.softmax(m / tau, dim=1) for m in self.local_m_logits]
        
        for meta in reversed(self.local_meta):
            M_ij = local_M_probs[meta['matrix_idx']]
            target_caps = torch.zeros(meta['num_pins'] + meta['num_bypass'], device=self.device)
            
            if meta['num_pins'] > 0:
                target_caps[:meta['num_pins']] = global_pin_caps[meta['pin_global_indices']]
            if meta['num_bypass'] > 0:
                target_caps[meta['num_pins']:] = node_loads[meta['out_bypass_ids']]
                
            in_wire_loads = M_ij @ (target_caps + WIRE_CAP_PER_NET)
            for idx, w in enumerate(meta['in_wires']):
                node_loads[w] += in_wire_loads[idx]

        # 3. 前向波前推进 (Forward Wavefront Propagation)
        wire_ats = torch.zeros(self.total_virtual_nodes, device=self.device)
        wire_slews = torch.zeros(self.total_virtual_nodes, device=self.device)
        
        wire_ats[:self.num_pp] = pp_at
        wire_slews[:self.num_pp] = pp_slew
        
        expected_glitch = 0.0
        global_pin_ats_probe = torch.zeros(self.num_c * 3, device=self.device)

        # 严格按级逐列遍历，彻底封死越级通道
        for meta in self.local_meta:
            M_ij = local_M_probs[meta['matrix_idx']]
            in_w = meta['in_wires']
            
            in_ats = wire_ats[in_w]
            in_slews = wire_slews[in_w]
            
            # 张量广播推流
            routed_ats = in_ats @ M_ij
            routed_slews = in_slews @ M_ij
            
            num_pins = meta['num_pins']
            num_bypass = meta['num_bypass']
            
            # 3.1 处理 Bypass 透传线
            if num_bypass > 0:
                out_b_ids = meta['out_bypass_ids']
                wire_ats[out_b_ids] = routed_ats[num_pins:]
                wire_slews[out_b_ids] = routed_slews[num_pins:]
                
            # 3.2 处理压缩器物理计算
            pin_ats = routed_ats[:num_pins]
            pin_slews = routed_slews[:num_pins]
            
            if num_pins > 0:
                global_pin_ats_probe[meta['pin_global_indices']] = pin_ats
            
            pin_offset = 0
            
            # 全加器
            for c_id in meta['fa_ids']:
                p_j = P_c[c_id, :self.num_fa_impls]
                c_ats = pin_ats[pin_offset : pin_offset+3]
                c_slews = pin_slews[pin_offset : pin_offset+3]
                pin_offset += 3
                
                # 💥 极其纯粹的 Glitch Variance
                mean_at = torch.mean(c_ats)
                expected_glitch = expected_glitch + torch.sqrt(torch.sum((c_ats - mean_at)**2) + 1e-8)
                
                s_load = node_loads[self.num_pp + c_id]
                co_load = node_loads[self.num_pp + self.num_c + c_id]
                
                s_paths_at, s_paths_slew = [], []
                co_paths_at, co_paths_slew = [], []
                
                for p_idx, p_name in enumerate(['A', 'B', 'CI']):
                    arc_S = self.fa_arcs['S'][p_name]
                    d_S = diff_bilinear_interp(c_slews[p_idx], s_load, arc_S['index_1_slew'], arc_S['index_2_load'], arc_S['delay_lut'])
                    sl_S = diff_bilinear_interp(c_slews[p_idx], s_load, arc_S['index_1_slew'], arc_S['index_2_load'], arc_S['slew_lut'])
                    s_paths_at.append(c_ats[p_idx] + torch.sum(p_j * d_S))
                    s_paths_slew.append(torch.sum(p_j * sl_S))
                    
                    arc_CO = self.fa_arcs['CO'][p_name]
                    d_CO = diff_bilinear_interp(c_slews[p_idx], co_load, arc_CO['index_1_slew'], arc_CO['index_2_load'], arc_CO['delay_lut'])
                    sl_CO = diff_bilinear_interp(c_slews[p_idx], co_load, arc_CO['index_1_slew'], arc_CO['index_2_load'], arc_CO['slew_lut'])
                    co_paths_at.append(c_ats[p_idx] + torch.sum(p_j * d_CO))
                    co_paths_slew.append(torch.sum(p_j * sl_CO))
                    
                wire_ats[self.num_pp + c_id] = smooth_max_lse(s_paths_at, gamma=0.01)
                wire_slews[self.num_pp + c_id] = smooth_max_lse(s_paths_slew, gamma=0.01)
                wire_ats[self.num_pp + self.num_c + c_id] = smooth_max_lse(co_paths_at, gamma=0.01)
                wire_slews[self.num_pp + self.num_c + c_id] = smooth_max_lse(co_paths_slew, gamma=0.01)

            # 半加器
            for c_id in meta['ha_ids']:
                p_j = P_c[c_id, :self.num_ha_impls]
                c_ats = pin_ats[pin_offset : pin_offset+2]
                c_slews = pin_slews[pin_offset : pin_offset+2]
                pin_offset += 2
                
                mean_at = torch.mean(c_ats)
                expected_glitch = expected_glitch + torch.sqrt(torch.sum((c_ats - mean_at)**2) + 1e-8)
                
                s_load = node_loads[self.num_pp + c_id]
                co_load = node_loads[self.num_pp + self.num_c + c_id]
                
                s_paths_at, s_paths_slew = [], []
                co_paths_at, co_paths_slew = [], []
                
                for p_idx, p_name in enumerate(['A', 'B']):
                    arc_S = self.ha_arcs['S'][p_name]
                    d_S = diff_bilinear_interp(c_slews[p_idx], s_load, arc_S['index_1_slew'], arc_S['index_2_load'], arc_S['delay_lut'])
                    sl_S = diff_bilinear_interp(c_slews[p_idx], s_load, arc_S['index_1_slew'], arc_S['index_2_load'], arc_S['slew_lut'])
                    s_paths_at.append(c_ats[p_idx] + torch.sum(p_j * d_S))
                    s_paths_slew.append(torch.sum(p_j * sl_S))
                    
                    arc_CO = self.ha_arcs['CO'][p_name]
                    d_CO = diff_bilinear_interp(c_slews[p_idx], co_load, arc_CO['index_1_slew'], arc_CO['index_2_load'], arc_CO['delay_lut'])
                    sl_CO = diff_bilinear_interp(c_slews[p_idx], co_load, arc_CO['index_1_slew'], arc_CO['index_2_load'], arc_CO['slew_lut'])
                    co_paths_at.append(c_ats[p_idx] + torch.sum(p_j * d_CO))
                    co_paths_slew.append(torch.sum(p_j * sl_CO))
                    
                wire_ats[self.num_pp + c_id] = smooth_max_lse(s_paths_at, gamma=0.01)
                wire_slews[self.num_pp + c_id] = smooth_max_lse(s_paths_slew, gamma=0.01)
                wire_ats[self.num_pp + self.num_c + c_id] = smooth_max_lse(co_paths_at, gamma=0.01)
                wire_slews[self.num_pp + self.num_c + c_id] = smooth_max_lse(co_paths_slew, gamma=0.01)

        # 4. CPA (Sink) 时序重建与惩罚
        # 智能动态抓取：任何没有作为后续阶段 in_wires 被消耗掉的节点，必然全部流向 CPA
        all_in_wires = set()
        for meta in self.local_meta:
            all_in_wires.update(meta['in_wires'])
            
        sink_wires = [w for w in range(self.total_virtual_nodes) if w not in all_in_wires]
        sink_ats = wire_ats[sink_wires]
        sink_cols = self.virtual_node_cols[sink_wires]
        
        max_col = torch.max(self.virtual_node_cols)
        distance_to_msb = max_col - sink_cols.float()
        
        CPA_BIT_DELAY_RCA = 0.040 
        CPA_BASE_DELAY_RCA = 0.090 
        cpa_latency = CPA_BASE_DELAY_RCA + distance_to_msb * CPA_BIT_DELAY_RCA
        
        effective_ats = sink_ats + cpa_latency
        slacks = self.req_time - effective_ats
        # =========================================================================
        
        negative_slacks = torch.clamp(slacks, max=0.0)

        WNS = smooth_max_lse(-negative_slacks, gamma=0.01) 
        TNS = torch.sum(-negative_slacks)
        
        # ================= [新增：探针埋点] =================
        # 将当前周期的引脚期望AT和节点真实AT暂存，供训练探针解剖
        self._probe_pin_ats = global_pin_ats_probe.detach()
        self._probe_node_ats = wire_ats.detach()
        
        # 返回包含了所有局部矩阵的列表，供 objectives 和 legalizer 使用
        return WNS, TNS, expected_area, expected_glitch, local_M_probs, P_c
```

### `src/core/objectives.py`

```python
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

### `src/core/domac_utils_booth.py`

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
    """
    [DOMAC 终极架构] 任意位宽无符号 Radix-4 Booth 编码画布生成器
    动态模拟点阵分布，保证与 Verilog RTL 拓扑 100% 对齐。
    """
    print(f"\n[Canvas Generator] 动态推演 {bit_width}x{bit_width} 无符号 Radix-4 Booth 乘法器画布...")
    G = (bit_width + 2) // 2 
    max_cols = bit_width * 2
    
    # 不再只存数量，而是存每个点的具体延迟！
    # pp_matrix[col] = [delay1, delay2, ...]
    pp_matrix = [[] for _ in range(max_cols)]
    
    # 根据 28nm 工艺设定的真实到达时间基准 (ns)
    DELAY_NORMAL = 0.08  # 基础数据位 (混合了 +A, -A 的均值)
    DELAY_NEG    = 0.11  # 进位/符号控制位 (最慢)
    DELAY_CONST  = 0.00  # 常数 1 (最快)
    
    for i in range(G):
        start_col = i * 2
        
        # 1. 基础部分积数据位
        for j in range(bit_width + 1):
            col = start_col + j
            if col < max_cols:
                pp_matrix[col].append(DELAY_NORMAL)
                
        # 2. 负数补码的 +1 补偿位
        if start_col < max_cols:
            pp_matrix[start_col].append(DELAY_NEG)
            
        # 3. 符号位扩展技巧 (修改型扩展 - 修复版)
        sign_col = start_col + bit_width + 1
        if i == 0:
            if sign_col < max_cols:
                pp_matrix[sign_col].append(DELAY_NEG)   # ~neg_0
                pp_matrix[sign_col].append(DELAY_CONST) # 常数1
            if sign_col + 1 < max_cols:
                pp_matrix[sign_col + 1].append(DELAY_CONST) # 补偿的常数1
        elif i < G - 1:
            if sign_col < max_cols:
                pp_matrix[sign_col].append(DELAY_NEG)   # ~neg_i
            if sign_col + 1 < max_cols:
                pp_matrix[sign_col + 1].append(DELAY_CONST) # 常数1

    # 展开为 DOMAC 引擎所需的 1D 列表
    pp_cols = []
    pp_at_init = []
    
    for col in range(max_cols):
        for delay in pp_matrix[col]:
            pp_cols.append(col)
            pp_at_init.append(delay)

    print(f" -> Booth 编码组数: {G}")
    print(f" -> 动态分配的初始 PP 节点总数: {len(pp_cols)}")

    # ---------------------------------------------------------
    # Dadda 树目标高度推演与压缩分配 (自适应高度)
    # ---------------------------------------------------------
    dots_in_col = [len(col_dots) for col_dots in pp_matrix]
    
    dadda_seq = [2]
    while dadda_seq[-1] < max(dots_in_col):
        dadda_seq.append(int(dadda_seq[-1] * 1.5))
    dadda_seq.reverse() 
    
    targets = [t for t in dadda_seq if t < max(dots_in_col)]
    print(f" -> 动态 Dadda 收敛序列: {targets}")
    
    comp_cols_raw = []
    c_types_raw = []
    current_dots = list(dots_in_col)
    
    for stage_idx, target in enumerate(targets):
        current_len = len(current_dots)
        next_dots = [0] * current_len
        carry_from_prev = 0
        
        for col in range(current_len):
            V = current_dots[col]
            allowed_output = target - carry_from_prev
            
            if V > allowed_output:
                reduction_needed = V - allowed_output
                f = reduction_needed // 2
                h = reduction_needed % 2
                
                for _ in range(f):
                    comp_cols_raw.append(col)
                    c_types_raw.append('FA')
                for _ in range(h):
                    comp_cols_raw.append(col)
                    c_types_raw.append('HA')
                    
                dots_stay = V - reduction_needed
                next_dots[col] = dots_stay + carry_from_prev
                carry_from_prev = f + h
            else:
                next_dots[col] = V + carry_from_prev
                carry_from_prev = 0
                
        if carry_from_prev > 0:
            if len(next_dots) < max_cols + 1:
                next_dots.append(carry_from_prev)
            else:
                next_dots[-1] += carry_from_prev
                
        current_dots = next_dots
        
    final_max = max(current_dots)
    print(f" -> 申请 {len(comp_cols_raw)} 个压缩器画布 ({c_types_raw.count('FA')} FA, {c_types_raw.count('HA')} HA)。\n")
    
    combined = sorted(zip(comp_cols_raw, c_types_raw), key=lambda x: x[0])
    comp_cols = [x[0] for x in combined]
    c_types = [x[1] for x in combined]

    return pp_cols, comp_cols, c_types, pp_at_init
    
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
    #  
    # for i in range(bit_width):
    #     for j in range(bit_width):
    #         signals[i+j].append(k)
    #         k += 1
    # [修复] 1. 动态感知 Booth 阵列的 PP 信号源节点
    for k, col in enumerate(pp_cols):
        signals[col].append(k)
            
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
    print("\n[Evaluator] 正在对坍缩后的 0/1 离散硬连线进行最终物理时序与毛刺功耗核算...")
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
        # 【修改点 1】增加 eval_glitch 接收毛刺功耗方差
        eval_wns, eval_tns, eval_area, eval_glitch, eval_M, eval_P = model(pp_at, pp_slew, tau=1.0)
        
        # 【修改点 2】将 eval_glitch 传给 loss_engine
        eval_loss, eval_dict = loss_engine(
            eval_wns, eval_tns, eval_area, eval_glitch, eval_M, eval_P, trainer_hyperparams, 
            model.active_pin_mask, model.c_types
        )

        # 【修改点 3】在最终评估报告中打印出 Glitch 的数值
        print(f" -> [坍缩后真实指标] WNS: {eval_dict['wns'].item():.4f} ns | "
              f"Area: {eval_dict['area'].item():.4f} μm² | "
              f"Glitch (Var): {eval_dict['glitch'].item():.6f} | "
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
    node_cols = model.virtual_node_cols

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
def probe_post_legalization_eval(model, loss_engine, trainer_hyperparams, discrete_local_M, discrete_P, final_P, pp_at, pp_slew, REQ_TIME, PP_COLS, COMP_COLS):
    print("\n[Evaluator] 正在对坍缩后的 0/1 离散硬连线进行最终物理时序与毛刺功耗核算...")
    with torch.no_grad():
        # 1. 构造离散化物理尺寸的 One-Hot 张量
        discrete_P_tensor = torch.zeros_like(final_P)
        for i, idx in enumerate(discrete_P):
            discrete_P_tensor[i, idx] = 1.0

        # 2. 备份原本训练结束时的模糊 logits，防止污染模型状态
        orig_local_m_logits = [m.clone() for m in model.local_m_logits]
        orig_p_logits = model.p_logits.clone()

        # 3. [核心技巧] 注入极端 Logits 强制网络走硬连线 (局部矩阵版)
        for m_param, m_disc in zip(model.local_m_logits, discrete_local_M):
            new_m = torch.full_like(m_param, -1e4)
            new_m[m_disc == 1.0] = 1e4
            m_param.copy_(new_m)

        new_p = torch.full_like(orig_p_logits, -1e4)
        new_p[discrete_P_tensor == 1.0] = 1e4
        model.p_logits.copy_(new_p)

        # 4. 执行一次纯净的前向传播与 Loss 计算
        eval_wns, eval_tns, eval_area, eval_glitch, eval_local_M, eval_P = model(pp_at, pp_slew, tau=1.0)
        
        eval_loss, eval_dict = loss_engine(
            eval_wns, eval_tns, eval_area, eval_glitch, eval_local_M, eval_P, 
            trainer_hyperparams, model.local_meta
        )

        print(f" -> [坍缩后真实指标] WNS: {eval_dict['wns'].item():.4f} ns | "
              f"Area: {eval_dict['area'].item():.4f} μm² | "
              f"Glitch (Var): {eval_dict['glitch'].item():.6f} | "
              f"L_BM: {eval_dict['l_bm'].item():.4f} | "
              f"Total Loss: {eval_loss.item():.4f}")
        
        # ================= [WNS 计算过程溯源探针] =================
        print("\n" + "="*60)
        print(" 🧮 [DOMAC 探针] 离散化网表 WNS 内部计算逻辑核对")
        print("="*60)
        
        # 1. 提取离散化评估后的全图所有虚拟节点的 AT (到达时间)
        all_ats = model._probe_node_ats.detach().cpu().numpy()
        req_time = REQ_TIME 
        
        # 2. 计算每个节点的 Slack (容限)
        slacks = req_time - all_ats
        
        # 3. 找出全图 Slack 最差的节点 (即 AT 最大的节点)
        worst_idx = np.argmin(slacks)
        worst_at = all_ats[worst_idx]
        worst_slack = slacks[worst_idx]
        
        # 4. 翻译这个“罪魁祸首”节点的物理身份 (已适配 Bypass 虚拟线)
        num_pp = len(PP_COLS)
        num_c = len(COMP_COLS)
        if worst_idx < num_pp:
            node_name = f"原始输入信号 PP_in_{worst_idx}"
        elif worst_idx < num_pp + num_c:
            c_idx = worst_idx - num_pp
            node_name = f"压缩器 U_comp_{c_idx} 的 S (Sum) 输出引脚"
        elif worst_idx < num_pp + 2 * num_c:
            c_idx = worst_idx - num_pp - num_c
            node_name = f"压缩器 U_comp_{c_idx} 的 CO (Carry-Out) 输出引脚"
        else:
            node_name = f"虚拟透传线 (Bypass Wire) ID_{worst_idx}"
            
        print(f" -> 1. 设定的目标到达时间 (REQ_TIME) : {req_time:.4f} ns")
        print(f" -> 2. 全局最慢的关键节点判定为     : {node_name}")
        print(f" -> 3. 查表计算的该节点实际 AT      : {worst_at:.4f} ns")
        print(f" -> 4. 原始负超额 (Negative Slack)  : {min(0.0, worst_slack):.4f} ns")
        print(f" -> 5. AI 最终汇报的平滑 eval_wns   : {eval_wns.item():.4f} ns")
        print("="*60 + "\n")

        # 5. 恢复原本的 logits (保持代码状态安全)
        for m_param, orig_m in zip(model.local_m_logits, orig_local_m_logits):
            m_param.copy_(orig_m)
        model.p_logits.copy_(orig_p_logits)
        
# ================= [探针 3：波前到达时间 (Wavefront AT)] =================
def probe_wavefront_at(model, discrete_M):
    print("\n" + "="*65)
    print(" 🌊 [DOMAC 探针] CPA 输入波前到达时间 (Wavefront AT) 剖析")
    print("="*65)
    
    # 提取离散化评估后，全图节点的真实物理到达时间
    node_ats = model._probe_node_ats.detach().cpu().numpy()
    node_cols = model.virtual_node_cols
    
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

def build_local_routing_graph(bit_width, pp_cols, c_cols, c_types):
    """
    生成局部 M_{i,j} 矩阵所需的层级化物理路由元数据 (严格同步画布逻辑修复版)
    """
    num_pp = len(pp_cols)
    num_c = len(c_cols)
    max_cols = bit_width * 2
    
    # 1. 初始化连线池 (记录全局 Wire ID)
    wires = [[] for _ in range(max_cols)]
    for k, col in enumerate(pp_cols):
        if col >= len(wires):
            # 应对极其罕见的溢出列
            wires.extend([[] for _ in range(col - len(wires) + 1)])
        wires[col].append(k) 
        
    dadda_seq = [2]
    while dadda_seq[-1] < bit_width:
        dadda_seq.append(int(dadda_seq[-1] * 1.5))
    dadda_seq.reverse()
    targets = [t for t in dadda_seq if t < max([len(w) for w in wires])]
    
    # 预分配压缩器 ID (使用 defaultdict 防越界)
    from collections import defaultdict
    comp_queue = defaultdict(lambda: {'FA': [], 'HA': []})
    for j, (col, c_type) in enumerate(zip(c_cols, c_types)):
        comp_queue[col][c_type].append(j)
    comp_usage = defaultdict(lambda: {'FA': 0, 'HA': 0})
    
    routing_stages = []
    next_wire_id = num_pp + 2 * num_c # Bypass 虚拟线的 ID 从这里开始分配
    
    # 2. 逐级生成局部矩阵元数据
    for target in targets:
        stage_meta = []
        next_wires = [[] for _ in range(len(wires))]
        carry_from_prev = []
        
        for col in range(len(wires)):
            # [核心修复]: Native Wires 才是决定是否需要增加压缩器的基准
            native_wires = wires[col]
            in_wires = native_wires + carry_from_prev
            
            V = len(native_wires)
            num_carries_in = len(carry_from_prev)
            
            # 为刚刚到来的进位预留位置
            allowed_output = target - num_carries_in
            
            if V > allowed_output:
                reduction_needed = V - allowed_output
                f = reduction_needed // 2
                h = reduction_needed % 2
                
                fa_ids, ha_ids, carries_gen, pin_global_indices = [], [], [], []
                
                # 分配全加器
                for _ in range(f):
                    c_id = comp_queue[col]['FA'][comp_usage[col]['FA']]
                    comp_usage[col]['FA'] += 1
                    fa_ids.append(c_id)
                    next_wires[col].append(num_pp + c_id)             # S 输出
                    carries_gen.append(num_pp + num_c + c_id)         # CO 输出
                    pin_global_indices.extend([c_id*3, c_id*3+1, c_id*3+2])
                    
                # 分配半加器
                for _ in range(h):
                    c_id = comp_queue[col]['HA'][comp_usage[col]['HA']]
                    comp_usage[col]['HA'] += 1
                    ha_ids.append(c_id)
                    next_wires[col].append(num_pp + c_id)
                    carries_gen.append(num_pp + num_c + c_id)
                    pin_global_indices.extend([c_id*3, c_id*3+1])
                    
                # 剩余的信号走透传 Bypass 通道
                num_bypass = len(in_wires) - (f * 3 + h * 2)
                out_bypass_ids = []
                for _ in range(num_bypass):
                    out_bypass_ids.append(next_wire_id)
                    next_wires[col].append(next_wire_id)
                    next_wire_id += 1
                    
                stage_meta.append({
                    'col': col, 'in_wires': in_wires, 'fa_ids': fa_ids, 'ha_ids': ha_ids,
                    'out_bypass_ids': out_bypass_ids, 'pin_global_indices': pin_global_indices
                })
                # 本列生成的进位传给下一列
                carry_from_prev = carries_gen
                
            else:
                # 如果不需要压缩，所有进来的信号 (原生 + 进位) 全部走 Bypass
                num_bypass = len(in_wires)
                out_bypass_ids = []
                for _ in range(num_bypass):
                    out_bypass_ids.append(next_wire_id)
                    next_wires[col].append(next_wire_id)
                    next_wire_id += 1
                    
                if num_bypass > 0:
                    stage_meta.append({
                        'col': col, 'in_wires': in_wires, 'fa_ids': [], 'ha_ids': [],
                        'out_bypass_ids': out_bypass_ids, 'pin_global_indices': []
                    })
                carry_from_prev = []
                
        # 处理最高位溢出的进位
        if carry_from_prev:
            next_wires.append(carry_from_prev)
            
        routing_stages.append(stage_meta)
        wires = next_wires
        
    return routing_stages, next_wire_id
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

### `src/export/verilog_gen_booth.py`

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
        包含: 动态 Radix-4 Booth PPG + CT (DOMAC 压缩树) + CPA (末级加法器)
        """
        print(f"[VerilogGen] 正在组装完整乘法器顶层模块: {top_file} (启用动态 Radix-4 Booth)")
        
        out_width = bit_width * 2
        
        with open(top_file, 'w') as f:
            f.write(f"`timescale 1ns/1ps\n\n")
            f.write(f"module {top_module_name} (\n")
            f.write(f"    input  wire [{bit_width-1}:0] A,\n")
            f.write(f"    input  wire [{bit_width-1}:0] B,\n")
            f.write(f"    output wire [{out_width-1}:0] P\n")
            f.write(f");\n\n")
            
            f.write("    // ==========================================\n")
            f.write("    // 1. Dynamic Radix-4 Booth Encoding (PPG)\n")
            f.write("    // ==========================================\n")
            
            # 动态推演组数与补码长度
            G = (bit_width + 2) // 2 
            pad_len = 2 * G - bit_width
            max_cols = bit_width * 2
            
            # 操作数 B 扩展 (确保总长度为奇数 2G+1，最低位补0用于 Booth 初始位)
            f.write(f"    wire [{pad_len + bit_width}:0] B_pad = {{{pad_len}'b0, B, 1'b0}};\n")
            # 操作数 A 扩展 (防溢出)
            f.write(f"    wire [{bit_width}:0] A_pad = {{1'b0, A}};\n\n")

            pp_dots_by_col = [[] for _ in range(max_cols)]
            
            for i in range(G):
                f.write(f"    // --- Group {i} ---\n")
                f.write(f"    wire [2:0] b_win_{i} = B_pad[{i*2+2}:{i*2}];\n")
                
                f.write(f"    wire neg_{i}  = b_win_{i}[2];\n")
                f.write(f"    wire zero_{i} = (b_win_{i} == 3'b000) | (b_win_{i} == 3'b111);\n")
                f.write(f"    wire one_{i}  = b_win_{i}[0] ^ b_win_{i}[1];\n")
                f.write(f"    wire two_{i}  = ~zero_{i} & ~one_{i};\n\n")
                
                f.write(f"    wire [{bit_width}:0] pp_base_{i};\n")
                f.write(f"    assign pp_base_{i} = ({{{bit_width+1}{{one_{i}}}}} & A_pad) | ({{{bit_width+1}{{two_{i}}}}} & (A_pad << 1));\n")
                f.write(f"    wire [{bit_width}:0] pp_val_{i} = neg_{i} ? ~pp_base_{i} : pp_base_{i};\n\n")
                
                # 物理落位映射
                start_col = i * 2
                
                # (a) 基础数据落位
                for j in range(bit_width + 1):
                    col = start_col + j
                    if col < max_cols:
                        pp_dots_by_col[col].append(f"pp_val_{i}[{j}]")
                        
                # (b) 补偿位落位
                if start_col < max_cols:
                    pp_dots_by_col[start_col].append(f"neg_{i}")
                    
               # (c) 修改型符号扩展 (修复版)
                sign_col = start_col + bit_width + 1
                if i == 0:
                    if sign_col < max_cols:
                        pp_dots_by_col[sign_col].append(f"~neg_{i}") # [修正] 直接使用 ~neg_i 作为真·符号位
                        pp_dots_by_col[sign_col].append("1'b1")
                    if sign_col + 1 < max_cols:
                        pp_dots_by_col[sign_col + 1].append("1'b1")
                elif i < G - 1:
                    if sign_col < max_cols:
                        pp_dots_by_col[sign_col].append(f"~neg_{i}") # [修正] 使用 ~neg_i
                    if sign_col + 1 < max_cols:
                        pp_dots_by_col[sign_col + 1].append("1'b1")  # [修正] 补偿常数向左移 1 bit

            f.write("    // --- DOMAC Canvas Mapping ---\n")
            pp_index = 0
            for col in range(max_cols):
                dots_in_this_col = pp_dots_by_col[col]
                for dot_signal in dots_in_this_col:
                    f.write(f"    wire pp_in_{pp_index} = {dot_signal};\n")
                    pp_index += 1
                    
            f.write(f"    // Total Booth dots mapped to CT: {pp_index}\n\n")
            
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
            
           # ==========================================================
            # 3. Carry-Propagate Adder (CPA) 加法器
            # ==========================================================
            f.write("    // 动态重建向量: 捕获 Booth 压缩树可能外溢的冗余进位\n")
            
            # 1. 动态获取 CT 实际输出的最大位权（包含进位外溢）
            max_ct_weight = max([weight for _, weight in self.tb_output_ports])
            cpa_width = max(out_width, max_ct_weight + 1)
            
            # 2. 分类收集不同权重的信号
            col_signals = {w: [] for w in range(cpa_width)}
            for out_name, weight in self.tb_output_ports:
                col_signals[weight].append(out_name)
                
            # 3. 重组加法向量
            max_depth = max([len(sigs) for sigs in col_signals.values()])
            
            vec_names = []
            for d in range(max_depth):
                vec_name = f"cpa_vec_{d}"
                vec_names.append(vec_name)
                f.write(f"    wire [{cpa_width-1}:0] {vec_name};\n")
                
                # 为该向量的每一位赋值
                for w in range(cpa_width):
                    if d < len(col_signals[w]):
                        f.write(f"    assign {vec_name}[{w}] = {col_signals[w][d]};\n")
                    else:
                        f.write(f"    assign {vec_name}[{w}] = 1'b0; // 缺位补零\n")
                f.write("\n")
            
            f.write("    // 综合工具会自动推断并行前缀加法器，并安全截断高位的冗余进位\n")
            sum_expr = " + ".join(vec_names)
            f.write(f"    wire [{cpa_width-1}:0] cpa_sum_full = {sum_expr};\n")
            
            # 4. 物理截断，严丝合缝对齐顶层模块的 out_width
            f.write(f"    assign P = cpa_sum_full[{out_width-1}:0];\n\n")
            
            f.write("endmodule\n")
            
        print(f"[VerilogGen] 顶层模块封装完毕！包含自适应 Booth 阵列 (CPA 宽度自动扩展至 {cpa_width} bit)。")
        
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
        # k = 0
        # for i in range(bit_width):
        #     for j in range(bit_width):
        #         signals[i+j].append(f"pp_in_{k}")
        #         k += 1
        # [修复替换为]
        for k, col in enumerate(self.pp_cols):
            signals[col].append(f"pp_in_{k}")
                
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
            # inputs = [f"pp_in_{i}" for i in range(bit_width * bit_width)]
            inputs = [f"pp_in_{i}" for i in range(self.num_pp)]

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

