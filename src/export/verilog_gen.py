import torch

class VerilogGenerator:
    def __init__(self, num_pp, num_c, module_name="domac_compressor_tree"):
        self.num_pp = num_pp
        self.num_c = num_c
        self.module_name = module_name
        self.cell_map = {
            0: {'name': 'FA1D1BWP12T40P140', 'inputs': ['A', 'B', 'CI'], 'outputs': ['S', 'CO']},
            1: {'name': 'HA1D1BWP12T40P140', 'inputs': ['A', 'B'],       'outputs': ['S', 'CO']}
        }

    def generate(self, discrete_M, discrete_P, output_file="output_netlist.v"):
        print(f"\n[VerilogGen] 正在将矩阵拓扑编译为 RTL 网表: {output_file}")
        
        total_nodes = self.num_pp + self.num_c
        wire_names = [f"pp_in_{i}" for i in range(self.num_pp)] + [f"comp_{j}_S" for j in range(self.num_c)]
            
        with open(output_file, 'w') as f:
            f.write(f"module {self.module_name} (\n")
            f.write(f"    input wire {', '.join(wire_names[:self.num_pp])},\n")
            
            # 1. 智能分配输出端口，处理 Feed-through (直通信号)
            output_ports = []
            assign_statements = []
            row_sums = torch.sum(discrete_M, dim=1).tolist()
            
            for i in range(total_nodes):
                if row_sums[i] == 0: # 如果该节点没连向任何后续的压缩器
                    if i < self.num_pp:
                        # 这是一个初级输入 (PP)，它没被处理就直接流出了
                        out_name = f"out_{wire_names[i]}"
                        output_ports.append(out_name)
                        assign_statements.append(f"    assign {out_name} = {wire_names[i]};")
                    else:
                        # 这是某台压缩器的 S 输出
                        output_ports.append(wire_names[i])
                        
            # CO 信号永远是输出
            for j in range(self.num_c):
                 output_ports.append(f"comp_{j}_CO")
                 
            f.write(f"    output wire {', '.join(output_ports)}\n);\n\n")
            
            # 2. 内部线网声明 (防重复)
            f.write("    // Internal wire declarations\n")
            for j in range(self.num_c):
                s_wire = f"comp_{j}_S"
                # 如果 S 线网没有作为 Output 抛出，才需要在内部声明为 wire
                if s_wire not in output_ports:
                    f.write(f"    wire {s_wire};\n")
                # CO 必然在 output_ports 中，所以不需要在这里重复声明 wire！
            f.write("\n")
            
            # 3. 直通信号赋值
            if assign_statements:
                f.write("    // Feed-through assignments\n")
                f.write("\n".join(assign_statements) + "\n\n")

            # 4. 例化压缩树
            f.write("    // Compressor Tree Instantiations\n")
            for j in range(self.num_c):
                cell_info = self.cell_map[discrete_P[j]]
                f.write(f"    {cell_info['name']} U_comp_{j} (\n")
                
                for p_idx, pin_name in enumerate(cell_info['inputs']):
                    col_idx = j * 3 + p_idx
                    connected_source = None
                    for i in range(total_nodes):
                        if discrete_M[i, col_idx] == 1.0:
                            connected_source = wire_names[i]
                            break
                            
                    if connected_source is None:
                        raise ValueError(f"严重物理错误！压缩器 {j} 的 {pin_name} 引脚没有接线！")
                        
                    f.write(f"        .{pin_name}({connected_source}),\n")
                
                f.write(f"        .S(comp_{j}_S),\n        .CO(comp_{j}_CO)\n    );\n\n")
                
            f.write("endmodule\n")
            
        print("[VerilogGen] RTL 网表生成成功。可以交付给 Design Compiler 综合了！")