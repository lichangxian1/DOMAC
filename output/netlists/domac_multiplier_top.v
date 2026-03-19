`timescale 1ns/1ps

module domac_multiplier_top (
    input  wire [7:0] A,
    input  wire [7:0] B,
    output wire [15:0] P
);

    // ==========================================
    // 1. Partial Product Generator (PPG) 阵列
    // ==========================================
    wire pp_in_0 = A[0] & B[0];
    wire pp_in_1 = A[0] & B[1];
    wire pp_in_2 = A[0] & B[2];
    wire pp_in_3 = A[0] & B[3];
    wire pp_in_4 = A[0] & B[4];
    wire pp_in_5 = A[0] & B[5];
    wire pp_in_6 = A[0] & B[6];
    wire pp_in_7 = A[0] & B[7];
    wire pp_in_8 = A[1] & B[0];
    wire pp_in_9 = A[1] & B[1];
    wire pp_in_10 = A[1] & B[2];
    wire pp_in_11 = A[1] & B[3];
    wire pp_in_12 = A[1] & B[4];
    wire pp_in_13 = A[1] & B[5];
    wire pp_in_14 = A[1] & B[6];
    wire pp_in_15 = A[1] & B[7];
    wire pp_in_16 = A[2] & B[0];
    wire pp_in_17 = A[2] & B[1];
    wire pp_in_18 = A[2] & B[2];
    wire pp_in_19 = A[2] & B[3];
    wire pp_in_20 = A[2] & B[4];
    wire pp_in_21 = A[2] & B[5];
    wire pp_in_22 = A[2] & B[6];
    wire pp_in_23 = A[2] & B[7];
    wire pp_in_24 = A[3] & B[0];
    wire pp_in_25 = A[3] & B[1];
    wire pp_in_26 = A[3] & B[2];
    wire pp_in_27 = A[3] & B[3];
    wire pp_in_28 = A[3] & B[4];
    wire pp_in_29 = A[3] & B[5];
    wire pp_in_30 = A[3] & B[6];
    wire pp_in_31 = A[3] & B[7];
    wire pp_in_32 = A[4] & B[0];
    wire pp_in_33 = A[4] & B[1];
    wire pp_in_34 = A[4] & B[2];
    wire pp_in_35 = A[4] & B[3];
    wire pp_in_36 = A[4] & B[4];
    wire pp_in_37 = A[4] & B[5];
    wire pp_in_38 = A[4] & B[6];
    wire pp_in_39 = A[4] & B[7];
    wire pp_in_40 = A[5] & B[0];
    wire pp_in_41 = A[5] & B[1];
    wire pp_in_42 = A[5] & B[2];
    wire pp_in_43 = A[5] & B[3];
    wire pp_in_44 = A[5] & B[4];
    wire pp_in_45 = A[5] & B[5];
    wire pp_in_46 = A[5] & B[6];
    wire pp_in_47 = A[5] & B[7];
    wire pp_in_48 = A[6] & B[0];
    wire pp_in_49 = A[6] & B[1];
    wire pp_in_50 = A[6] & B[2];
    wire pp_in_51 = A[6] & B[3];
    wire pp_in_52 = A[6] & B[4];
    wire pp_in_53 = A[6] & B[5];
    wire pp_in_54 = A[6] & B[6];
    wire pp_in_55 = A[6] & B[7];
    wire pp_in_56 = A[7] & B[0];
    wire pp_in_57 = A[7] & B[1];
    wire pp_in_58 = A[7] & B[2];
    wire pp_in_59 = A[7] & B[3];
    wire pp_in_60 = A[7] & B[4];
    wire pp_in_61 = A[7] & B[5];
    wire pp_in_62 = A[7] & B[6];
    wire pp_in_63 = A[7] & B[7];

    // ==========================================
    // 2. DOMAC AI 优化压缩树 (CT)
    // ==========================================
    wire out_pp_0, out_pp_1, out_pp_2, out_pp_8, out_pp_63, comp_0_S, comp_1_S, comp_2_S, comp_4_S, comp_5_S, comp_8_S, comp_9_S, comp_13_S, comp_14_S, comp_19_S, comp_20_S, comp_25_S, comp_26_S, comp_30_S, comp_31_S, comp_34_S, comp_35_S, comp_37_S, comp_38_S, comp_39_S, comp_40_S, comp_41_S, comp_40_CO, comp_41_CO;

    domac_compressor_tree U_CT (
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
        .out_pp_8(out_pp_8),
        .out_pp_63(out_pp_63),
        .comp_0_S(comp_0_S),
        .comp_1_S(comp_1_S),
        .comp_2_S(comp_2_S),
        .comp_4_S(comp_4_S),
        .comp_5_S(comp_5_S),
        .comp_8_S(comp_8_S),
        .comp_9_S(comp_9_S),
        .comp_13_S(comp_13_S),
        .comp_14_S(comp_14_S),
        .comp_19_S(comp_19_S),
        .comp_20_S(comp_20_S),
        .comp_25_S(comp_25_S),
        .comp_26_S(comp_26_S),
        .comp_30_S(comp_30_S),
        .comp_31_S(comp_31_S),
        .comp_34_S(comp_34_S),
        .comp_35_S(comp_35_S),
        .comp_37_S(comp_37_S),
        .comp_38_S(comp_38_S),
        .comp_39_S(comp_39_S),
        .comp_40_S(comp_40_S),
        .comp_41_S(comp_41_S),
        .comp_40_CO(comp_40_CO),
        .comp_41_CO(comp_41_CO)
    );

    // ==========================================
    // 3. Carry-Propagate Adder (CPA) 加法器
    // ==========================================
    // 将压缩树残留的杂散信号按二进制权重对齐重建，送入高速 CPA
    wire [15:0] cpa_vec_0;
    assign cpa_vec_0[0] = out_pp_0;
    assign cpa_vec_0[1] = out_pp_1;
    assign cpa_vec_0[2] = out_pp_2;
    assign cpa_vec_0[3] = comp_1_S;
    assign cpa_vec_0[4] = comp_4_S;
    assign cpa_vec_0[5] = comp_8_S;
    assign cpa_vec_0[6] = comp_13_S;
    assign cpa_vec_0[7] = comp_19_S;
    assign cpa_vec_0[8] = comp_25_S;
    assign cpa_vec_0[9] = comp_30_S;
    assign cpa_vec_0[10] = comp_34_S;
    assign cpa_vec_0[11] = comp_37_S;
    assign cpa_vec_0[12] = comp_39_S;
    assign cpa_vec_0[13] = comp_41_S;
    assign cpa_vec_0[14] = out_pp_63;
    assign cpa_vec_0[15] = 1'b0; // 缺位补零

    wire [15:0] cpa_vec_1;
    assign cpa_vec_1[0] = 1'b0; // 缺位补零
    assign cpa_vec_1[1] = out_pp_8;
    assign cpa_vec_1[2] = comp_0_S;
    assign cpa_vec_1[3] = comp_2_S;
    assign cpa_vec_1[4] = comp_5_S;
    assign cpa_vec_1[5] = comp_9_S;
    assign cpa_vec_1[6] = comp_14_S;
    assign cpa_vec_1[7] = comp_20_S;
    assign cpa_vec_1[8] = comp_26_S;
    assign cpa_vec_1[9] = comp_31_S;
    assign cpa_vec_1[10] = comp_35_S;
    assign cpa_vec_1[11] = comp_38_S;
    assign cpa_vec_1[12] = comp_40_S;
    assign cpa_vec_1[13] = comp_40_CO;
    assign cpa_vec_1[14] = comp_41_CO;
    assign cpa_vec_1[15] = 1'b0; // 缺位补零

    // 综合工具 (Design Compiler) 会将下述加法自动推断为极速并行前缀加法器
    assign P = cpa_vec_0 + cpa_vec_1;

endmodule
