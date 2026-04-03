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