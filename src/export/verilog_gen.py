import torch

class VerilogGenerator:
    def __init__(self, num_pp, num_c, module_name="domac_compressor_tree"):
        """
        DOMAC Verilog 网表生成引擎
        将合法的离散化矩阵转换为标准的结构化 Verilog 代码。
        """
        self.num_pp = num_pp
        self.num_c = num_c
        self.module_name = module_name
        
        # 对应 TSMC 28nm HPC+ 真实物理单元的引脚定义
        # 注意: 这里的引脚名 (A, B, CI, S, CO) 必须与你 .lib 中的定义完全一致！
        self.cell_map = {
            0: {'name': 'FA1D1BWP12T40P140', 'inputs': ['A', 'B', 'CI'], 'outputs': ['S', 'CO']},
            1: {'name': 'HA1D1BWP12T40P140', 'inputs': ['A', 'B'],       'outputs': ['S', 'CO']}
        }

    def generate(self, discrete_M, discrete_P, output_file="output_netlist.v"):
        """
        执行 Verilog 生成
        
        参数:
        discrete_M (Tensor/numpy): 仅包含0/1的连接矩阵 [num_pp + num_c, num_c]
        discrete_P (list): 长度为 num_c 的实现类型列表 (0=FA, 1=HA)
        """
        print(f"\n[VerilogGen] 正在将矩阵拓扑编译为 RTL 网表: {output_file}")
        
        total_nodes = self.num_pp + self.num_c
        
        # 存储所有节点的线网名字
        # 前 num_pp 个是模块的输入，后面的节点是内部压缩器的输出
        wire_names = []
        for i in range(self.num_pp):
            wire_names.append(f"pp_in_{i}")
        
        for j in range(self.num_c):
            # 简单起见，我们将每个压缩器的 S (Sum) 引脚视为它的主要向下传递节点
            # CO (Carry Out) 进位引脚通常连向更高权重的列，我们在这里先定义出来
            wire_names.append(f"comp_{j}_S")
            
        with open(output_file, 'w') as f:
            # 1. 模块声明与端口定义
            f.write(f"module {self.module_name} (\n")
            
            # 声明部分积输入
            input_ports = [f"pp_in_{i}" for i in range(self.num_pp)]
            f.write(f"    input wire {', '.join(input_ports)},\n")
            
            # 声明外部输出 (凡是没有连向任何内部压缩器的线，都视为最终输出)
            # 在 M 矩阵中，如果某行的和为 0，说明它流向了外部 Sink
            row_sums = torch.sum(discrete_M, dim=1).tolist()
            output_ports = []
            for i in range(total_nodes):
                if row_sums[i] == 0:
                    output_ports.append(wire_names[i])
            
            # 如果存在孤立的进位引脚(CO)，也作为输出暴露
            for j in range(self.num_c):
                 output_ports.append(f"comp_{j}_CO")
                 
            f.write(f"    output wire {', '.join(output_ports)}\n")
            f.write(");\n\n")
            
            # 2. 内部线网声明 (Wire Declaration)
            f.write("    // Internal wire declarations\n")
            for j in range(self.num_c):
                f.write(f"    wire comp_{j}_S;\n")
                f.write(f"    wire comp_{j}_CO;\n")
            f.write("\n")
            
            # 3. 实例化物理单元 (Cell Instantiation)
            f.write("    // Compressor Tree Instantiations\n")
            for j in range(self.num_c):
                cell_type = discrete_P[j]
                cell_info = self.cell_map[cell_type]
                
                # 寻找连向当前压缩器 j 的所有源节点 (M 矩阵第 j 列为 1 的行)
                connected_sources = []
                for i in range(total_nodes):
                    if discrete_M[i, j] == 1.0:
                        connected_sources.append(wire_names[i])
                
                # 安全校验：连线数必须等于引脚数
                if len(connected_sources) != len(cell_info['inputs']):
                    raise ValueError(f"严重物理错误！压缩器 {j} 需要 {len(cell_info['inputs'])} 根线，但只分配了 {len(connected_sources)} 根。")
                
                # 构建例化字符串
                f.write(f"    {cell_info['name']} U_comp_{j} (\n")
                
                # 绑定输入引脚
                for p_idx, pin_name in enumerate(cell_info['inputs']):
                    f.write(f"        .{pin_name}({connected_sources[p_idx]}),\n")
                
                # 绑定输出引脚
                f.write(f"        .S(comp_{j}_S),\n")
                f.write(f"        .CO(comp_{j}_CO)\n")
                f.write("    );\n\n")
                
            f.write("endmodule\n")
            
        print("[VerilogGen] RTL 网表生成成功。可以交付给 Design Compiler 综合了！")