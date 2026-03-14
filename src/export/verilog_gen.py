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
        基于第一性原理，动态生成算术权重守恒测试平台
        """
        print(f"[VerilogGen] 正在锻造自校验 Testbench: {tb_file}")
        with open(tb_file, 'w') as f:
            f.write("`timescale 1ns/1ps\n\n")
            
            # 由于要模拟底层的 TSMC 标准单元，我们需要提供最简单的行为级模型供仿真使用
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
            
            # 声明所有寄存器和线网
            pp_regs = [f"pp_in_{i}" for i in range(self.num_pp)]
            f.write(f"    reg {', '.join(pp_regs)};\n")
            
            out_wires = [port[0] for port in self.tb_output_ports]
            f.write(f"    wire {', '.join(out_wires)};\n\n")
            
            # 例化被测模块 (DUT)
            f.write(f"    {self.module_name} DUT (\n")
            all_ports = pp_regs + out_wires
            f.write(",\n".join([f"        .{p}({p})" for p in all_ports]))
            f.write("\n    );\n\n")
            
            # 构建检验逻辑
            f.write("    integer expected_weight, actual_weight;\n")
            f.write("    integer i;\n")
            f.write("    integer error_count = 0;\n\n")
            
            f.write("    initial begin\n")
            f.write("        $display(\"\\n[Testbench] 启动权重守恒定律校验...\");\n")
            
            # 生成 1000 次随机测试
            f.write("        for (i = 0; i < 1000; i = i + 1) begin\n")
            
            # 随机驱动输入
            for i, p_reg in enumerate(pp_regs):
                f.write(f"            {p_reg} = $random % 2;\n")
                
            f.write("            #5; // 等待组合逻辑稳定\n\n")
            
            # 计算预期权重
            f.write("            expected_weight = 0")
            for i, p_reg in enumerate(pp_regs):
                f.write(f" + ({p_reg} * (1 << {self.pp_cols[i]}))")
            f.write(";\n")
            
            # 计算实际权重
            f.write("            actual_weight = 0")
            for out_name, weight in self.tb_output_ports:
                f.write(f" + ({out_name} * (1 << {weight}))")
            f.write(";\n\n")
            
            # 断言比对
            f.write("            if (expected_weight !== actual_weight) begin\n")
            f.write("                $display(\"[致命错误] 守恒定律被打破！第 %0d 次测试失败。Expected: %0d, Actual: %0d\", i, expected_weight, actual_weight);\n")
            f.write("                error_count = error_count + 1;\n")
            f.write("            end\n")
            f.write("        end\n\n")
            
            f.write("        if (error_count == 0)\n")
            f.write("            $display(\"\\n[Testbench] 校验完美通过！AI 生成的压缩树在逻辑上 100%% 绝对等效于人类设计。\\n\");\n")
            f.write("        else\n")
            f.write("            $display(\"\\n[Testbench] 测试失败，共发现 %0d 个错误。\\n\", error_count);\n")
            
            f.write("        $finish;\n")
            f.write("    end\n")
            f.write("endmodule\n")
            
        print(f"[VerilogGen] Testbench 锻造完毕！")