module domac_compressor_tree (
    input wire pp_in_0, pp_in_1, pp_in_2, pp_in_3, pp_in_4, pp_in_5, pp_in_6, pp_in_7, pp_in_8, pp_in_9, pp_in_10, pp_in_11, pp_in_12, pp_in_13, pp_in_14, pp_in_15, pp_in_16, pp_in_17, pp_in_18, pp_in_19, pp_in_20, pp_in_21, pp_in_22, pp_in_23, pp_in_24, pp_in_25, pp_in_26, pp_in_27, pp_in_28, pp_in_29, pp_in_30, pp_in_31, pp_in_32, pp_in_33, pp_in_34, pp_in_35, pp_in_36, pp_in_37, pp_in_38, pp_in_39, pp_in_40, pp_in_41, pp_in_42, pp_in_43, pp_in_44, pp_in_45, pp_in_46, pp_in_47, pp_in_48, pp_in_49, pp_in_50, pp_in_51, pp_in_52, pp_in_53, pp_in_54, pp_in_55, pp_in_56, pp_in_57, pp_in_58, pp_in_59, pp_in_60, pp_in_61, pp_in_62, pp_in_63,
    output wire out_pp_0, out_pp_1, out_pp_8, out_pp_16, out_pp_63, comp_0_S, comp_1_S, comp_2_S, comp_4_S, comp_5_S, comp_8_S, comp_9_S, comp_13_S, comp_14_S, comp_19_S, comp_20_S, comp_25_S, comp_26_S, comp_30_S, comp_31_S, comp_34_S, comp_35_S, comp_37_S, comp_38_S, comp_39_S, comp_40_S, comp_41_S, comp_39_CO, comp_41_CO
);

    // Internal wire declarations
    wire comp_0_CO;
    wire comp_1_CO;
    wire comp_2_CO;
    wire comp_3_S;
    wire comp_3_CO;
    wire comp_4_CO;
    wire comp_5_CO;
    wire comp_6_S;
    wire comp_6_CO;
    wire comp_7_S;
    wire comp_7_CO;
    wire comp_8_CO;
    wire comp_9_CO;
    wire comp_10_S;
    wire comp_10_CO;
    wire comp_11_S;
    wire comp_11_CO;
    wire comp_12_S;
    wire comp_12_CO;
    wire comp_13_CO;
    wire comp_14_CO;
    wire comp_15_S;
    wire comp_15_CO;
    wire comp_16_S;
    wire comp_16_CO;
    wire comp_17_S;
    wire comp_17_CO;
    wire comp_18_S;
    wire comp_18_CO;
    wire comp_19_CO;
    wire comp_20_CO;
    wire comp_21_S;
    wire comp_21_CO;
    wire comp_22_S;
    wire comp_22_CO;
    wire comp_23_S;
    wire comp_23_CO;
    wire comp_24_S;
    wire comp_24_CO;
    wire comp_25_CO;
    wire comp_26_CO;
    wire comp_27_S;
    wire comp_27_CO;
    wire comp_28_S;
    wire comp_28_CO;
    wire comp_29_S;
    wire comp_29_CO;
    wire comp_30_CO;
    wire comp_31_CO;
    wire comp_32_S;
    wire comp_32_CO;
    wire comp_33_S;
    wire comp_33_CO;
    wire comp_34_CO;
    wire comp_35_CO;
    wire comp_36_S;
    wire comp_36_CO;
    wire comp_37_CO;
    wire comp_38_CO;
    wire comp_40_CO;

    // Feed-through assignments
    assign out_pp_0 = pp_in_0;
    assign out_pp_1 = pp_in_1;
    assign out_pp_8 = pp_in_8;
    assign out_pp_16 = pp_in_16;
    assign out_pp_63 = pp_in_63;

    // Compressor Tree Instantiations
    HA1D4BWP12T40P140 U_comp_0 (
        .A(pp_in_2),
        .B(pp_in_9),
        .S(comp_0_S),
        .CO(comp_0_CO)
    );

    HA1D4BWP12T40P140 U_comp_1 (
        .A(pp_in_3),
        .B(pp_in_10),
        .S(comp_1_S),
        .CO(comp_1_CO)
    );

    FA1D4BWP12T40P140 U_comp_2 (
        .A(comp_0_CO),
        .B(pp_in_24),
        .CI(pp_in_17),
        .S(comp_2_S),
        .CO(comp_2_CO)
    );

    HA1D4BWP12T40P140 U_comp_3 (
        .A(pp_in_11),
        .B(pp_in_4),
        .S(comp_3_S),
        .CO(comp_3_CO)
    );

    FA1D4BWP12T40P140 U_comp_4 (
        .A(pp_in_32),
        .B(pp_in_18),
        .CI(comp_3_S),
        .S(comp_4_S),
        .CO(comp_4_CO)
    );

    FA1D4BWP12T40P140 U_comp_5 (
        .A(pp_in_25),
        .B(comp_2_CO),
        .CI(comp_1_CO),
        .S(comp_5_S),
        .CO(comp_5_CO)
    );

    FA1D4BWP12T40P140 U_comp_6 (
        .A(pp_in_33),
        .B(pp_in_26),
        .CI(comp_3_CO),
        .S(comp_6_S),
        .CO(comp_6_CO)
    );

    HA1D4BWP12T40P140 U_comp_7 (
        .A(pp_in_5),
        .B(comp_6_S),
        .S(comp_7_S),
        .CO(comp_7_CO)
    );

    FA1D4BWP12T40P140 U_comp_8 (
        .A(comp_7_S),
        .B(pp_in_12),
        .CI(comp_4_CO),
        .S(comp_8_S),
        .CO(comp_8_CO)
    );

    FA1D4BWP12T40P140 U_comp_9 (
        .A(comp_5_CO),
        .B(pp_in_40),
        .CI(pp_in_19),
        .S(comp_9_S),
        .CO(comp_9_CO)
    );

    HA1D4BWP12T40P140 U_comp_10 (
        .A(pp_in_6),
        .B(comp_6_CO),
        .S(comp_10_S),
        .CO(comp_10_CO)
    );

    FA1D4BWP12T40P140 U_comp_11 (
        .A(pp_in_13),
        .B(pp_in_41),
        .CI(comp_10_S),
        .S(comp_11_S),
        .CO(comp_11_CO)
    );

    FA1D4BWP12T40P140 U_comp_12 (
        .A(pp_in_27),
        .B(comp_11_S),
        .CI(pp_in_20),
        .S(comp_12_S),
        .CO(comp_12_CO)
    );

    FA1D4BWP12T40P140 U_comp_13 (
        .A(pp_in_34),
        .B(pp_in_48),
        .CI(comp_7_CO),
        .S(comp_13_S),
        .CO(comp_13_CO)
    );

    FA1D4BWP12T40P140 U_comp_14 (
        .A(comp_12_S),
        .B(comp_9_CO),
        .CI(comp_8_CO),
        .S(comp_14_S),
        .CO(comp_14_CO)
    );

    FA1D4BWP12T40P140 U_comp_15 (
        .A(comp_13_CO),
        .B(pp_in_14),
        .CI(comp_12_CO),
        .S(comp_15_S),
        .CO(comp_15_CO)
    );

    HA1D4BWP12T40P140 U_comp_16 (
        .A(comp_14_CO),
        .B(pp_in_7),
        .S(comp_16_S),
        .CO(comp_16_CO)
    );

    FA1D4BWP12T40P140 U_comp_17 (
        .A(comp_16_S),
        .B(pp_in_28),
        .CI(comp_15_S),
        .S(comp_17_S),
        .CO(comp_17_CO)
    );

    FA1D4BWP12T40P140 U_comp_18 (
        .A(pp_in_42),
        .B(comp_17_S),
        .CI(comp_11_CO),
        .S(comp_18_S),
        .CO(comp_18_CO)
    );

    FA1D4BWP12T40P140 U_comp_19 (
        .A(pp_in_56),
        .B(pp_in_49),
        .CI(comp_10_CO),
        .S(comp_19_S),
        .CO(comp_19_CO)
    );

    FA1D4BWP12T40P140 U_comp_20 (
        .A(comp_18_S),
        .B(pp_in_35),
        .CI(pp_in_21),
        .S(comp_20_S),
        .CO(comp_20_CO)
    );

    FA1D4BWP12T40P140 U_comp_21 (
        .A(comp_19_CO),
        .B(pp_in_22),
        .CI(pp_in_15),
        .S(comp_21_S),
        .CO(comp_21_CO)
    );

    HA1D4BWP12T40P140 U_comp_22 (
        .A(comp_20_CO),
        .B(pp_in_29),
        .S(comp_22_S),
        .CO(comp_22_CO)
    );

    FA1D4BWP12T40P140 U_comp_23 (
        .A(comp_15_CO),
        .B(comp_21_S),
        .CI(comp_22_S),
        .S(comp_23_S),
        .CO(comp_23_CO)
    );

    FA1D4BWP12T40P140 U_comp_24 (
        .A(comp_17_CO),
        .B(comp_18_CO),
        .CI(comp_16_CO),
        .S(comp_24_S),
        .CO(comp_24_CO)
    );

    FA1D4BWP12T40P140 U_comp_25 (
        .A(comp_23_S),
        .B(pp_in_57),
        .CI(comp_24_S),
        .S(comp_25_S),
        .CO(comp_25_CO)
    );

    FA1D4BWP12T40P140 U_comp_26 (
        .A(pp_in_50),
        .B(pp_in_36),
        .CI(pp_in_43),
        .S(comp_26_S),
        .CO(comp_26_CO)
    );

    FA1D4BWP12T40P140 U_comp_27 (
        .A(comp_26_CO),
        .B(pp_in_23),
        .CI(pp_in_58),
        .S(comp_27_S),
        .CO(comp_27_CO)
    );

    FA1D4BWP12T40P140 U_comp_28 (
        .A(comp_27_S),
        .B(comp_23_CO),
        .CI(comp_24_CO),
        .S(comp_28_S),
        .CO(comp_28_CO)
    );

    FA1D4BWP12T40P140 U_comp_29 (
        .A(comp_28_S),
        .B(comp_25_CO),
        .CI(comp_22_CO),
        .S(comp_29_S),
        .CO(comp_29_CO)
    );

    FA1D4BWP12T40P140 U_comp_30 (
        .A(comp_21_CO),
        .B(comp_29_S),
        .CI(pp_in_51),
        .S(comp_30_S),
        .CO(comp_30_CO)
    );

    FA1D4BWP12T40P140 U_comp_31 (
        .A(pp_in_44),
        .B(pp_in_37),
        .CI(pp_in_30),
        .S(comp_31_S),
        .CO(comp_31_CO)
    );

    FA1D4BWP12T40P140 U_comp_32 (
        .A(comp_30_CO),
        .B(comp_31_CO),
        .CI(comp_29_CO),
        .S(comp_32_S),
        .CO(comp_32_CO)
    );

    FA1D4BWP12T40P140 U_comp_33 (
        .A(comp_32_S),
        .B(pp_in_59),
        .CI(comp_28_CO),
        .S(comp_33_S),
        .CO(comp_33_CO)
    );

    FA1D4BWP12T40P140 U_comp_34 (
        .A(pp_in_45),
        .B(pp_in_52),
        .CI(pp_in_38),
        .S(comp_34_S),
        .CO(comp_34_CO)
    );

    FA1D4BWP12T40P140 U_comp_35 (
        .A(comp_27_CO),
        .B(comp_33_S),
        .CI(pp_in_31),
        .S(comp_35_S),
        .CO(comp_35_CO)
    );

    FA1D4BWP12T40P140 U_comp_36 (
        .A(comp_34_CO),
        .B(comp_33_CO),
        .CI(comp_35_CO),
        .S(comp_36_S),
        .CO(comp_36_CO)
    );

    FA1D4BWP12T40P140 U_comp_37 (
        .A(comp_32_CO),
        .B(pp_in_60),
        .CI(comp_36_S),
        .S(comp_37_S),
        .CO(comp_37_CO)
    );

    FA1D4BWP12T40P140 U_comp_38 (
        .A(pp_in_46),
        .B(pp_in_53),
        .CI(pp_in_39),
        .S(comp_38_S),
        .CO(comp_38_CO)
    );

    FA1D4BWP12T40P140 U_comp_39 (
        .A(pp_in_54),
        .B(comp_37_CO),
        .CI(pp_in_47),
        .S(comp_39_S),
        .CO(comp_39_CO)
    );

    FA1D4BWP12T40P140 U_comp_40 (
        .A(comp_38_CO),
        .B(comp_36_CO),
        .CI(pp_in_61),
        .S(comp_40_S),
        .CO(comp_40_CO)
    );

    FA1D4BWP12T40P140 U_comp_41 (
        .A(pp_in_62),
        .B(pp_in_55),
        .CI(comp_40_CO),
        .S(comp_41_S),
        .CO(comp_41_CO)
    );

endmodule
