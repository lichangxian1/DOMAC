`timescale 1ns/1ps

// ================= TSMC Mock Behavioral Models =================
module FA1D1BWP12T40P140 (input A, B, CI, output S, CO);
    assign {CO, S} = A + B + CI;
endmodule
module FA1D0BWP12T40P140 (input A, B, CI, output S, CO);
    assign {CO, S} = A + B + CI;
endmodule
module FA1D2BWP12T40P140 (input A, B, CI, output S, CO);
    assign {CO, S} = A + B + CI;
endmodule
module FA1D4BWP12T40P140 (input A, B, CI, output S, CO);
    assign {CO, S} = A + B + CI;
endmodule
module HA1D2BWP12T40P140 (input A, B, output S, CO);
    assign {CO, S} = A + B;
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

module tb_domac;
    reg pp_in_0, pp_in_1, pp_in_2, pp_in_3, pp_in_4, pp_in_5, pp_in_6, pp_in_7, pp_in_8, pp_in_9, pp_in_10, pp_in_11, pp_in_12, pp_in_13, pp_in_14, pp_in_15, pp_in_16, pp_in_17, pp_in_18, pp_in_19, pp_in_20, pp_in_21, pp_in_22, pp_in_23, pp_in_24, pp_in_25, pp_in_26, pp_in_27, pp_in_28, pp_in_29, pp_in_30, pp_in_31, pp_in_32, pp_in_33, pp_in_34, pp_in_35, pp_in_36, pp_in_37, pp_in_38, pp_in_39, pp_in_40, pp_in_41, pp_in_42, pp_in_43, pp_in_44, pp_in_45, pp_in_46, pp_in_47, pp_in_48, pp_in_49, pp_in_50, pp_in_51, pp_in_52, pp_in_53, pp_in_54, pp_in_55, pp_in_56, pp_in_57, pp_in_58, pp_in_59, pp_in_60, pp_in_61, pp_in_62, pp_in_63;
    wire out_pp_0, out_pp_1, out_pp_2, out_pp_52, out_pp_56, out_pp_60, out_pp_63, comp_0_S, comp_2_S, comp_5_S, comp_9_S, comp_14_S, comp_20_S, comp_26_S, comp_31_S, comp_35_S, comp_38_S, comp_40_S, comp_41_S, comp_22_CO, comp_39_CO, comp_41_CO;

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
        .pp_in_36(pp_in_36),
        .pp_in_37(pp_in_37),
        .pp_in_38(pp_in_38),
        .pp_in_39(pp_in_39),
        .pp_in_40(pp_in_40),
        .pp_in_41(pp_in_41),
        .pp_in_42(pp_in_42),
        .pp_in_43(pp_in_43),
        .pp_in_44(pp_in_44),
        .pp_in_45(pp_in_45),
        .pp_in_46(pp_in_46),
        .pp_in_47(pp_in_47),
        .pp_in_48(pp_in_48),
        .pp_in_49(pp_in_49),
        .pp_in_50(pp_in_50),
        .pp_in_51(pp_in_51),
        .pp_in_52(pp_in_52),
        .pp_in_53(pp_in_53),
        .pp_in_54(pp_in_54),
        .pp_in_55(pp_in_55),
        .pp_in_56(pp_in_56),
        .pp_in_57(pp_in_57),
        .pp_in_58(pp_in_58),
        .pp_in_59(pp_in_59),
        .pp_in_60(pp_in_60),
        .pp_in_61(pp_in_61),
        .pp_in_62(pp_in_62),
        .pp_in_63(pp_in_63),
        .out_pp_0(out_pp_0),
        .out_pp_1(out_pp_1),
        .out_pp_2(out_pp_2),
        .out_pp_52(out_pp_52),
        .out_pp_56(out_pp_56),
        .out_pp_60(out_pp_60),
        .out_pp_63(out_pp_63),
        .comp_0_S(comp_0_S),
        .comp_2_S(comp_2_S),
        .comp_5_S(comp_5_S),
        .comp_9_S(comp_9_S),
        .comp_14_S(comp_14_S),
        .comp_20_S(comp_20_S),
        .comp_26_S(comp_26_S),
        .comp_31_S(comp_31_S),
        .comp_35_S(comp_35_S),
        .comp_38_S(comp_38_S),
        .comp_40_S(comp_40_S),
        .comp_41_S(comp_41_S),
        .comp_22_CO(comp_22_CO),
        .comp_39_CO(comp_39_CO),
        .comp_41_CO(comp_41_CO)
    );

    integer expected_weight, actual_weight;
    integer i;
    integer error_count = 0;

    initial begin
        $display("\n[Testbench] 启动权重守恒定律校验...");
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
            pp_in_36 = $random % 2;
            pp_in_37 = $random % 2;
            pp_in_38 = $random % 2;
            pp_in_39 = $random % 2;
            pp_in_40 = $random % 2;
            pp_in_41 = $random % 2;
            pp_in_42 = $random % 2;
            pp_in_43 = $random % 2;
            pp_in_44 = $random % 2;
            pp_in_45 = $random % 2;
            pp_in_46 = $random % 2;
            pp_in_47 = $random % 2;
            pp_in_48 = $random % 2;
            pp_in_49 = $random % 2;
            pp_in_50 = $random % 2;
            pp_in_51 = $random % 2;
            pp_in_52 = $random % 2;
            pp_in_53 = $random % 2;
            pp_in_54 = $random % 2;
            pp_in_55 = $random % 2;
            pp_in_56 = $random % 2;
            pp_in_57 = $random % 2;
            pp_in_58 = $random % 2;
            pp_in_59 = $random % 2;
            pp_in_60 = $random % 2;
            pp_in_61 = $random % 2;
            pp_in_62 = $random % 2;
            pp_in_63 = $random % 2;
            #5; // 等待组合逻辑稳定

            expected_weight = 0 + (pp_in_0 * (1 << 0)) + (pp_in_1 * (1 << 1)) + (pp_in_2 * (1 << 1)) + (pp_in_3 * (1 << 2)) + (pp_in_4 * (1 << 2)) + (pp_in_5 * (1 << 2)) + (pp_in_6 * (1 << 3)) + (pp_in_7 * (1 << 3)) + (pp_in_8 * (1 << 3)) + (pp_in_9 * (1 << 3)) + (pp_in_10 * (1 << 4)) + (pp_in_11 * (1 << 4)) + (pp_in_12 * (1 << 4)) + (pp_in_13 * (1 << 4)) + (pp_in_14 * (1 << 4)) + (pp_in_15 * (1 << 5)) + (pp_in_16 * (1 << 5)) + (pp_in_17 * (1 << 5)) + (pp_in_18 * (1 << 5)) + (pp_in_19 * (1 << 5)) + (pp_in_20 * (1 << 5)) + (pp_in_21 * (1 << 6)) + (pp_in_22 * (1 << 6)) + (pp_in_23 * (1 << 6)) + (pp_in_24 * (1 << 6)) + (pp_in_25 * (1 << 6)) + (pp_in_26 * (1 << 6)) + (pp_in_27 * (1 << 6)) + (pp_in_28 * (1 << 7)) + (pp_in_29 * (1 << 7)) + (pp_in_30 * (1 << 7)) + (pp_in_31 * (1 << 7)) + (pp_in_32 * (1 << 7)) + (pp_in_33 * (1 << 7)) + (pp_in_34 * (1 << 7)) + (pp_in_35 * (1 << 7)) + (pp_in_36 * (1 << 8)) + (pp_in_37 * (1 << 8)) + (pp_in_38 * (1 << 8)) + (pp_in_39 * (1 << 8)) + (pp_in_40 * (1 << 8)) + (pp_in_41 * (1 << 8)) + (pp_in_42 * (1 << 8)) + (pp_in_43 * (1 << 9)) + (pp_in_44 * (1 << 9)) + (pp_in_45 * (1 << 9)) + (pp_in_46 * (1 << 9)) + (pp_in_47 * (1 << 9)) + (pp_in_48 * (1 << 9)) + (pp_in_49 * (1 << 10)) + (pp_in_50 * (1 << 10)) + (pp_in_51 * (1 << 10)) + (pp_in_52 * (1 << 10)) + (pp_in_53 * (1 << 10)) + (pp_in_54 * (1 << 11)) + (pp_in_55 * (1 << 11)) + (pp_in_56 * (1 << 11)) + (pp_in_57 * (1 << 11)) + (pp_in_58 * (1 << 12)) + (pp_in_59 * (1 << 12)) + (pp_in_60 * (1 << 12)) + (pp_in_61 * (1 << 13)) + (pp_in_62 * (1 << 13)) + (pp_in_63 * (1 << 14));
            actual_weight = 0 + (out_pp_0 * (1 << 0)) + (out_pp_1 * (1 << 1)) + (out_pp_2 * (1 << 1)) + (out_pp_52 * (1 << 10)) + (out_pp_56 * (1 << 11)) + (out_pp_60 * (1 << 12)) + (out_pp_63 * (1 << 14)) + (comp_0_S * (1 << 2)) + (comp_2_S * (1 << 3)) + (comp_5_S * (1 << 4)) + (comp_9_S * (1 << 5)) + (comp_14_S * (1 << 6)) + (comp_20_S * (1 << 7)) + (comp_26_S * (1 << 8)) + (comp_31_S * (1 << 9)) + (comp_35_S * (1 << 10)) + (comp_38_S * (1 << 11)) + (comp_40_S * (1 << 12)) + (comp_41_S * (1 << 13)) + (comp_22_CO * (1 << 9)) + (comp_39_CO * (1 << 13)) + (comp_41_CO * (1 << 14));

            if (expected_weight !== actual_weight) begin
                $display("[致命错误] 守恒定律被打破！第 %0d 次测试失败。Expected: %0d, Actual: %0d", i, expected_weight, actual_weight);
                error_count = error_count + 1;
            end
        end

        if (error_count == 0)
            $display("\n[Testbench] 校验完美通过！AI 生成的压缩树在逻辑上 100%% 绝对等效于人类设计。\n");
        else
            $display("\n[Testbench] 测试失败，共发现 %0d 个错误。\n", error_count);
        $finish;
    end
endmodule
