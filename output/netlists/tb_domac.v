`timescale 1ns/1ps

// ================= TSMC Mock Behavioral Models =================
module FA1D0BWP12T40P140 (input A, B, CI, output S, CO);
    assign {CO, S} = A + B + CI;
endmodule
module FA1D1BWP12T40P140 (input A, B, CI, output S, CO);
    assign {CO, S} = A + B + CI;
endmodule
module FA1D4BWP12T40P140 (input A, B, CI, output S, CO);
    assign {CO, S} = A + B + CI;
endmodule
module FA1D2BWP12T40P140 (input A, B, CI, output S, CO);
    assign {CO, S} = A + B + CI;
endmodule
module HA1D1BWP12T40P140 (input A, B, output S, CO);
    assign {CO, S} = A + B;
endmodule

module HA1D0BWP12T40P140 (input A, B, output S, CO);
    assign {CO, S} = A + B;
endmodule

module HA1D4BWP12T40P140 (input A, B, output S, CO);
    assign {CO, S} = A + B;
endmodule

module HA1D2BWP12T40P140 (input A, B, output S, CO);
    assign {CO, S} = A + B;
endmodule

module tb_domac;
    reg pp_in_0, pp_in_1, pp_in_2, pp_in_3, pp_in_4, pp_in_5, pp_in_6, pp_in_7, pp_in_8, pp_in_9, pp_in_10, pp_in_11, pp_in_12, pp_in_13, pp_in_14, pp_in_15, pp_in_16, pp_in_17, pp_in_18, pp_in_19, pp_in_20, pp_in_21, pp_in_22, pp_in_23, pp_in_24, pp_in_25, pp_in_26, pp_in_27, pp_in_28, pp_in_29, pp_in_30, pp_in_31, pp_in_32, pp_in_33, pp_in_34, pp_in_35;
    wire out_pp_0, out_pp_1, out_pp_2, out_pp_34, out_pp_35, comp_0_S, comp_2_S, comp_5_S, comp_9_S, comp_13_S, comp_16_S, comp_18_S, comp_19_S, comp_12_CO, comp_14_CO, comp_19_CO;

    domac_compressor_tree DUT (
        .pp_in_0(pp_in_0),
        .pp_in_1(pp_in_1),
        .pp_in_2(pp_in_2),
        .pp_in_3(pp_in_3),
        .pp_in_4(pp_in_4),
        .pp_in_5(pp_in_5),
        .pp_in_6(pp_in_6),
        .pp_in_7(pp_in_7),
        .pp_in_8(pp_in_8),
        .pp_in_9(pp_in_9),
        .pp_in_10(pp_in_10),
        .pp_in_11(pp_in_11),
        .pp_in_12(pp_in_12),
        .pp_in_13(pp_in_13),
        .pp_in_14(pp_in_14),
        .pp_in_15(pp_in_15),
        .pp_in_16(pp_in_16),
        .pp_in_17(pp_in_17),
        .pp_in_18(pp_in_18),
        .pp_in_19(pp_in_19),
        .pp_in_20(pp_in_20),
        .pp_in_21(pp_in_21),
        .pp_in_22(pp_in_22),
        .pp_in_23(pp_in_23),
        .pp_in_24(pp_in_24),
        .pp_in_25(pp_in_25),
        .pp_in_26(pp_in_26),
        .pp_in_27(pp_in_27),
        .pp_in_28(pp_in_28),
        .pp_in_29(pp_in_29),
        .pp_in_30(pp_in_30),
        .pp_in_31(pp_in_31),
        .pp_in_32(pp_in_32),
        .pp_in_33(pp_in_33),
        .pp_in_34(pp_in_34),
        .pp_in_35(pp_in_35),
        .out_pp_0(out_pp_0),
        .out_pp_1(out_pp_1),
        .out_pp_2(out_pp_2),
        .out_pp_34(out_pp_34),
        .out_pp_35(out_pp_35),
        .comp_0_S(comp_0_S),
        .comp_2_S(comp_2_S),
        .comp_5_S(comp_5_S),
        .comp_9_S(comp_9_S),
        .comp_13_S(comp_13_S),
        .comp_16_S(comp_16_S),
        .comp_18_S(comp_18_S),
        .comp_19_S(comp_19_S),
        .comp_12_CO(comp_12_CO),
        .comp_14_CO(comp_14_CO),
        .comp_19_CO(comp_19_CO)
    );

    reg [63:0] expected_weight, actual_weight;
    integer i;
    integer error_count = 0;

    initial begin
        $display("\n============================================================");
        $display(" [DOMAC 算术验证中心] 启动权重守恒算式核对");
        $display("============================================================\n");
        for (i = 0; i < 1000; i = i + 1) begin
            pp_in_0 = $random % 2;
            pp_in_1 = $random % 2;
            pp_in_2 = $random % 2;
            pp_in_3 = $random % 2;
            pp_in_4 = $random % 2;
            pp_in_5 = $random % 2;
            pp_in_6 = $random % 2;
            pp_in_7 = $random % 2;
            pp_in_8 = $random % 2;
            pp_in_9 = $random % 2;
            pp_in_10 = $random % 2;
            pp_in_11 = $random % 2;
            pp_in_12 = $random % 2;
            pp_in_13 = $random % 2;
            pp_in_14 = $random % 2;
            pp_in_15 = $random % 2;
            pp_in_16 = $random % 2;
            pp_in_17 = $random % 2;
            pp_in_18 = $random % 2;
            pp_in_19 = $random % 2;
            pp_in_20 = $random % 2;
            pp_in_21 = $random % 2;
            pp_in_22 = $random % 2;
            pp_in_23 = $random % 2;
            pp_in_24 = $random % 2;
            pp_in_25 = $random % 2;
            pp_in_26 = $random % 2;
            pp_in_27 = $random % 2;
            pp_in_28 = $random % 2;
            pp_in_29 = $random % 2;
            pp_in_30 = $random % 2;
            pp_in_31 = $random % 2;
            pp_in_32 = $random % 2;
            pp_in_33 = $random % 2;
            pp_in_34 = $random % 2;
            pp_in_35 = $random % 2;
            #5; // 模拟信号穿过组合逻辑的延迟

            expected_weight = 0 + (pp_in_0 * (64'h1 << 0)) + (pp_in_1 * (64'h1 << 1)) + (pp_in_2 * (64'h1 << 1)) + (pp_in_3 * (64'h1 << 2)) + (pp_in_4 * (64'h1 << 2)) + (pp_in_5 * (64'h1 << 2)) + (pp_in_6 * (64'h1 << 3)) + (pp_in_7 * (64'h1 << 3)) + (pp_in_8 * (64'h1 << 3)) + (pp_in_9 * (64'h1 << 3)) + (pp_in_10 * (64'h1 << 4)) + (pp_in_11 * (64'h1 << 4)) + (pp_in_12 * (64'h1 << 4)) + (pp_in_13 * (64'h1 << 4)) + (pp_in_14 * (64'h1 << 4)) + (pp_in_15 * (64'h1 << 5)) + (pp_in_16 * (64'h1 << 5)) + (pp_in_17 * (64'h1 << 5)) + (pp_in_18 * (64'h1 << 5)) + (pp_in_19 * (64'h1 << 5)) + (pp_in_20 * (64'h1 << 5)) + (pp_in_21 * (64'h1 << 6)) + (pp_in_22 * (64'h1 << 6)) + (pp_in_23 * (64'h1 << 6)) + (pp_in_24 * (64'h1 << 6)) + (pp_in_25 * (64'h1 << 6)) + (pp_in_26 * (64'h1 << 7)) + (pp_in_27 * (64'h1 << 7)) + (pp_in_28 * (64'h1 << 7)) + (pp_in_29 * (64'h1 << 7)) + (pp_in_30 * (64'h1 << 8)) + (pp_in_31 * (64'h1 << 8)) + (pp_in_32 * (64'h1 << 8)) + (pp_in_33 * (64'h1 << 9)) + (pp_in_34 * (64'h1 << 9)) + (pp_in_35 * (64'h1 << 10));
            actual_weight = 0 + (out_pp_0 * (64'h1 << 0)) + (out_pp_1 * (64'h1 << 1)) + (out_pp_2 * (64'h1 << 1)) + (out_pp_34 * (64'h1 << 9)) + (out_pp_35 * (64'h1 << 10)) + (comp_0_S * (64'h1 << 2)) + (comp_2_S * (64'h1 << 3)) + (comp_5_S * (64'h1 << 4)) + (comp_9_S * (64'h1 << 5)) + (comp_13_S * (64'h1 << 6)) + (comp_16_S * (64'h1 << 7)) + (comp_18_S * (64'h1 << 8)) + (comp_19_S * (64'h1 << 9)) + (comp_12_CO * (64'h1 << 7)) + (comp_14_CO * (64'h1 << 8)) + (comp_19_CO * (64'h1 << 10));

            // 打印前 20 次和每 100 次的详细算式，防止终端刷屏卡死
            if (i < 20 || i % 100 == 0) begin
                if (expected_weight === actual_weight)
                    $display("  [Test %04d] 算式成立: 📥 进件总值 %10d  ===  📤 产出总值 %10d   [✔ PASS]", i, expected_weight, actual_weight);
                else
                    $display("  [Test %04d] 算式崩塌: 📥 进件总值 %10d  =!=  📤 产出总值 %10d   [❌ FAIL]", i, expected_weight, actual_weight);
            end
            if (expected_weight !== actual_weight) begin
                error_count = error_count + 1;
            end
        end

        $display("\n============================================================");
        if (error_count == 0)
            $display(" 🎉 [Testbench] 1000 次算式核对完美通过！拓扑绝对守恒！");
        else
            $display(" 💥 [Testbench] 验证失败，共发现 %0d 个权重流失错误！", error_count);
        $display("============================================================\n");
        $finish;
    end
endmodule
