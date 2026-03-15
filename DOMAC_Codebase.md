# DOMAC_TSMC28 工程代码全局快照

**Root Directory:** `/home/changxian/DOMAC_TSMC28`

### `domac.py`

```python
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

    pp_at = torch.linspace(0.0, 0.1, NUM_PP) 
    pp_slew = torch.full((NUM_PP,), 0.05)
    REQ_TIME = 0.1 
    print("REQ_TIME：" + str(REQ_TIME))

    print(f"\n[Engine] 构建异构可微压缩树...")
    model = DOMAC_CompressorTree(PP_COLS, COMP_COLS, fa_tensors, ha_tensors, C_TYPES, REQ_TIME)

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
        DOMAC 训练引擎 (Dr. Gemini 性能探针版)
        """
        self.model = model
        self.loss_engine = loss_engine
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)
        
# [Dr. Gemini 的极权统治：初期只看速度和合法性]
        self.hyperparams = {
            't1': 100.0,     # WNS 权重拉到极致，逼迫网络突破延迟极限
            't2': 1.0,       # TNS 辅助全局路径寻优
            'alpha': 0.0,    # 【封印】前期绝对不许管面积！
            'lambda1': 1.0,  # 连线合法性是必须的
            'lambda2': 0.0,  # 【封印】前期不许进行二值化坍缩！让概率保持连续，充分探索！
        }

    # def update_hyperparameters(self, epoch):
    #     if epoch >= 100:
    #         self.hyperparams['alpha'] *= 1.003
    #         self.hyperparams['t1'] *= 1.005
    #         self.hyperparams['t2'] *= 1.005
    #         self.hyperparams['lambda1'] *= 1.01
    #         self.hyperparams['lambda2'] *= 1.01

    def update_hyperparameters(self, epoch):
        """
        动态退火调度器：分阶段释放约束
        """
        # 阶段 1 (Epoch 0-99)：野蛮生长，全力追求 WNS 和合法拓扑
        
        # 阶段 2 (Epoch 100 触发)：拓扑基本成型，开始施加面积与二值化压力
        if epoch == 100:
            print("\n[Scheduler] Epoch 100 抵达！解封 Area 与 二值化 (L_D) 约束！")
            self.hyperparams['alpha'] = 0.05   
            self.hyperparams['lambda2'] = 0.1  
            
        # 阶段 3 (Epoch 100-300)：温水煮青蛙，逐步收紧离散化和合法性，逼迫最终坍缩
        if epoch > 100:
            self.hyperparams['lambda1'] *= 1.02  # 越来越严苛的合法性
            self.hyperparams['lambda2'] *= 1.05  # 逼迫概率走向 0 或 1
            self.hyperparams['alpha'] *= 1.005   # 轻微压缩面积

    def train(self, pp_at, pp_slew, max_epochs=300):
        print(f"[Optimizer] 启动 DOMAC 训练循环，最大迭代次数: {max_epochs}")
        print(f"[Profiler] 性能探针已植入。正在监控 Forward, Loss, Backward, Step 耗时...")
        
        # 性能累加器
        acc_forward, acc_loss, acc_backward, acc_step = 0.0, 0.0, 0.0, 0.0
        
        for epoch in range(max_epochs):
            self.update_hyperparameters(epoch)
            self.optimizer.zero_grad()
            
            # ================= [探针 1: 前向传播 STA] =================
            t0 = time.time()
            wns, tns, area, M, P_c = self.model(pp_at, pp_slew)
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
            
            # 每 20 步打印一次物理指标与性能报告
            if epoch % 5 == 0 or epoch == max_epochs - 1:
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
    def __init__(self, pp_cols, c_cols, fa_tensors, ha_tensors, c_types, req_time):
        super(DOMAC_CompressorTree, self).__init__()
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
        
        # 预编译为 3D 张量的物理库
        self.fa_areas, self.fa_caps, self.fa_arcs = self._parse_tensors(fa_tensors)
        self.ha_areas, self.ha_caps, self.ha_arcs = self._parse_tensors(ha_tensors)
        
        self.p_logits = nn.Parameter(torch.zeros(self.num_c, self.max_impls))
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
        
        total_target_pins = self.num_c * self.num_pins_per_c 
        self.m_logits = nn.Parameter(torch.zeros(total_nodes, total_target_pins + 1))
        
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
        
        # 寻找基准坐标轴
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

        for ct in tensors:
            areas.append(ct.get('cell_area', 1.0))
            p_caps = [ct.get('pin_cap', {}).get(p, 0.001) for p in self.pin_names]
            caps.append(p_caps)

            for out_p in ['S', 'CO']:
                for in_p in self.pin_names:
                    arc = ct.get(out_p, {}).get(in_p)
                    if arc:
                        stacked_arcs[out_p][in_p]['delay_lut'].append(arc['delay_lut'])
                        stacked_arcs[out_p][in_p]['slew_lut'].append(arc['slew_lut'])
                    else:
                        # 用 10.0 填充无用的空白时序弧，保证矩阵维度规整
                        stacked_arcs[out_p][in_p]['delay_lut'].append(torch.full((7,7), 10.0))
                        stacked_arcs[out_p][in_p]['slew_lut'].append(torch.full((7,7), 10.0))

        # 将所有 2D 矩阵沿着实现维度叠成 3D 张量！
        for out_p in ['S', 'CO']:
            for in_p in self.pin_names:
                stacked_arcs[out_p][in_p]['delay_lut'] = torch.stack(stacked_arcs[out_p][in_p]['delay_lut'])
                stacked_arcs[out_p][in_p]['slew_lut'] = torch.stack(stacked_arcs[out_p][in_p]['slew_lut'])
                stacked_arcs[out_p][in_p]['index_1_slew'] = index_1_slew
                stacked_arcs[out_p][in_p]['index_2_load'] = index_2_load

        return torch.tensor(areas, dtype=torch.float32), torch.tensor(caps, dtype=torch.float32), stacked_arcs

    def forward(self, pp_at, pp_slew):
        P_c = F.softmax(self.p_logits + self.p_mask, dim=-1) 
        M_full = F.softmax(self.m_logits + self.dag_mask, dim=-1) 
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
        loads = M_internal @ flat_expected_pin_caps 
        
        pp_ats_t = torch.stack(list(pp_at))
        pp_slews_t = torch.stack(list(pp_slew))
        
        s_ats, s_slews = [], []
        co_ats, co_slews = [], []

        for j in range(self.num_c):
            col_start = j * self.num_pins_per_c
            col_end = col_start + self.num_pins_per_c
            
            m_pp = M_internal[:self.num_pp, col_start:col_end]
            pin_ats = pp_ats_t @ m_pp
            pin_slews = pp_slews_t @ m_pp
            
            if j > 0:
                s_ats_t = torch.stack(s_ats)
                s_slews_t = torch.stack(s_slews)
                m_s = M_internal[self.num_pp : self.num_pp + j, col_start:col_end]
                pin_ats = pin_ats + s_ats_t @ m_s
                pin_slews = pin_slews + s_slews_t @ m_s
                
                co_ats_t = torch.stack(co_ats)
                co_slews_t = torch.stack(co_slews)
                m_co = M_internal[self.num_pp + self.num_c : self.num_pp + self.num_c + j, col_start:col_end]
                pin_ats = pin_ats + co_ats_t @ m_co
                pin_slews = pin_slews + co_slews_t @ m_co

            s_load = loads[self.num_pp + j]
            co_load = loads[self.num_pp + self.num_c + j]
            
            is_fa = (self.c_types[j] == 'FA')
            cell_arcs = self.fa_arcs if is_fa else self.ha_arcs
            P_j = P_c[j, :self.num_fa_impls] if is_fa else P_c[j, :self.num_ha_impls]
            
            s_paths_at, s_paths_slew = [], []
            co_paths_at, co_paths_slew = [], []
            
            for p_idx, p_name in enumerate(self.pin_names):
                if self.active_pin_mask[j * 3 + p_idx] > 0.5:
                    
                    # =========================================================================
                    # [核弹级向量化] S 弧延迟计算 (无需 for 循环，一次插出 4 种门的数值！)
                    arc_S = cell_arcs['S'][p_name]
                    delays_S = diff_bilinear_interp(pin_slews[p_idx], s_load, arc_S['index_1_slew'], arc_S['index_2_load'], arc_S['delay_lut'])
                    slews_S = diff_bilinear_interp(pin_slews[p_idx], s_load, arc_S['index_1_slew'], arc_S['index_2_load'], arc_S['slew_lut'])
                    
                    # 直接点乘概率矩阵，收割！
                    s_paths_at.append(pin_ats[p_idx] + torch.sum(P_j * delays_S))
                    s_paths_slew.append(torch.sum(P_j * slews_S))
                    
                    # CO 弧同理
                    arc_CO = cell_arcs['CO'][p_name]
                    delays_CO = diff_bilinear_interp(pin_slews[p_idx], co_load, arc_CO['index_1_slew'], arc_CO['index_2_load'], arc_CO['delay_lut'])
                    slews_CO = diff_bilinear_interp(pin_slews[p_idx], co_load, arc_CO['index_1_slew'], arc_CO['index_2_load'], arc_CO['slew_lut'])
                    
                    co_paths_at.append(pin_ats[p_idx] + torch.sum(P_j * delays_CO))
                    co_paths_slew.append(torch.sum(P_j * slews_CO))
                    # =========================================================================

            expected_s_at = smooth_max_lse(s_paths_at, gamma=0.01) if s_paths_at else torch.tensor(10.0, device=P_c.device)
            expected_s_slew = smooth_max_lse(s_paths_slew, gamma=0.01) if s_paths_at else torch.tensor(10.0, device=P_c.device)
            expected_co_at = smooth_max_lse(co_paths_at, gamma=0.01) if co_paths_at else torch.tensor(10.0, device=P_c.device)
            expected_co_slew = smooth_max_lse(co_paths_slew, gamma=0.01) if co_paths_at else torch.tensor(10.0, device=P_c.device)
            
            s_ats.append(expected_s_at)
            s_slews.append(expected_s_slew)
            co_ats.append(expected_co_at)
            co_slews.append(expected_co_slew)
            
        node_ats = list(pp_at) + s_ats + co_ats
        all_ats_tensor = torch.stack(node_ats)
        
        slacks = self.req_time - all_ats_tensor
        negative_slacks = torch.clamp(slacks, max=0.0)
        
        WNS = smooth_max_lse(-negative_slacks, gamma=0.01) 
        TNS = torch.sum(-negative_slacks)
        
        return WNS, TNS, expected_area, M_internal, P_c
```

### `src/core/objectives.py`

```python
import torch
import torch.nn as nn
import torch.nn.functional as F

class DOMACLossFunction(nn.Module):
    def __init__(self, pin_counts_lib=[3.0, 2.0]):
        """
        DOMAC 联合目标与约束损失函数引擎
        """
        super(DOMACLossFunction, self).__init__()
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

    def calc_sink_loss(self, M_internal, target_max_signals=2.0):
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
        l_sink, actual_sink_count = self.calc_sink_loss(M, target_max_signals=62.0)
        
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

### `src/export/verilog_gen.py`

```python
import torch

class VerilogGenerator:
    def __init__(self, pp_cols, c_cols, c_types, fa_cell_names, ha_cell_names, module_name="domac_compressor_tree"):
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

    def generate_testbench(self, tb_file="tb_domac.v", netlist_file="domac_result.v"):
        """
        [Dr. Gemini 可视化版] 动态生成带“算式直播”的权重守恒测试平台
        """
        print(f"[VerilogGen] 正在锻造带算式输出的自校验 Testbench: {tb_file}")
        with open(tb_file, 'w') as f:
            f.write("`timescale 1ns/1ps\n\n")
            
            f.write("// ================= TSMC Mock Behavioral Models =================\n")
            for fa_name in set(self.fa_cell_names):
                f.write(f"module {fa_name} (input A, B, CI, output S, CO);\n")
                f.write("    assign {CO, S} = A + B + CI;\n")
                f.write("endmodule\n")
            for ha_name in set(self.ha_cell_names):
                f.write(f"module {ha_name} (input A, B, output S, CO);\n")
                f.write("    assign {CO, S} = A + B;\n")
                f.write("endmodule\n\n")
                
            f.write("module tb_domac;\n")
            
            pp_regs = [f"pp_in_{i}" for i in range(self.num_pp)]
            f.write(f"    reg {', '.join(pp_regs)};\n")
            
            out_wires = [port[0] for port in self.tb_output_ports]
            f.write(f"    wire {', '.join(out_wires)};\n\n")
            
            f.write(f"    {self.module_name} DUT (\n")
            all_ports = pp_regs + out_wires
            f.write(",\n".join([f"        .{p}({p})" for p in all_ports]))
            f.write("\n    );\n\n")
            
            # 使用 64 位整数 (reg [63:0]) 防止大位宽乘法器权重溢出
            f.write("    reg [63:0] expected_weight, actual_weight;\n")
            f.write("    integer i;\n")
            f.write("    integer error_count = 0;\n\n")
            
            f.write("    initial begin\n")
            f.write("        $display(\"\\n============================================================\");\n")
            f.write("        $display(\" [DOMAC 算术验证中心] 启动权重守恒算式核对\");\n")
            f.write("        $display(\"============================================================\\n\");\n")
            
            f.write("        for (i = 0; i < 1000; i = i + 1) begin\n")
            
            for i, p_reg in enumerate(pp_regs):
                f.write(f"            {p_reg} = $random % 2;\n")
                
            f.write("            #5; // 模拟信号穿过组合逻辑的延迟\n\n")
            
            f.write("            expected_weight = 0")
            for i, p_reg in enumerate(pp_regs):
                f.write(f" + ({p_reg} * (64'h1 << {self.pp_cols[i]}))")
            f.write(";\n")
            
            f.write("            actual_weight = 0")
            for out_name, weight in self.tb_output_ports:
                f.write(f" + ({out_name} * (64'h1 << {weight}))")
            f.write(";\n\n")
            
            # ======== [核心修改：终端直播打印] ========
            f.write("            // 打印前 20 次和每 100 次的详细算式，防止终端刷屏卡死\n")
            f.write("            if (i < 20 || i % 100 == 0) begin\n")
            f.write("                if (expected_weight === actual_weight)\n")
            f.write("                    $display(\"  [Test %04d] 算式成立: 📥 进件总值 %10d  ===  📤 产出总值 %10d   [✔ PASS]\", i, expected_weight, actual_weight);\n")
            f.write("                else\n")
            f.write("                    $display(\"  [Test %04d] 算式崩塌: 📥 进件总值 %10d  =!=  📤 产出总值 %10d   [❌ FAIL]\", i, expected_weight, actual_weight);\n")
            f.write("            end\n")
            
            f.write("            if (expected_weight !== actual_weight) begin\n")
            f.write("                error_count = error_count + 1;\n")
            f.write("            end\n")
            f.write("        end\n\n")
            
            f.write("        $display(\"\\n============================================================\");\n")
            f.write("        if (error_count == 0)\n")
            f.write("            $display(\" 🎉 [Testbench] 1000 次算式核对完美通过！拓扑绝对守恒！\");\n")
            f.write("        else\n")
            f.write("            $display(\" 💥 [Testbench] 验证失败，共发现 %0d 个权重流失错误！\", error_count);\n")
            f.write("        $display(\"============================================================\\n\");\n")
            
            f.write("        $finish;\n")
            f.write("    end\n")
            f.write("endmodule\n")
            
        print(f"[VerilogGen] Testbench 可视化升级完毕！")
```

