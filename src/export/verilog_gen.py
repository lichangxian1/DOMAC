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

    def generate_multiplier_top(self, bit_width, top_file="domac.v", ct_module_name="domac_compressor_tree", top_module_name="domac"):
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
