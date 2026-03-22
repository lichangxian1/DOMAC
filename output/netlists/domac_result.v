module domac_compressor_tree (
    input wire pp_in_0, pp_in_1, pp_in_2, pp_in_3, pp_in_4, pp_in_5, pp_in_6, pp_in_7, pp_in_8, pp_in_9, pp_in_10, pp_in_11, pp_in_12, pp_in_13, pp_in_14, pp_in_15, pp_in_16, pp_in_17, pp_in_18, pp_in_19, pp_in_20, pp_in_21, pp_in_22, pp_in_23, pp_in_24, pp_in_25, pp_in_26, pp_in_27, pp_in_28, pp_in_29, pp_in_30, pp_in_31, pp_in_32, pp_in_33, pp_in_34, pp_in_35, pp_in_36, pp_in_37, pp_in_38, pp_in_39, pp_in_40, pp_in_41, pp_in_42, pp_in_43, pp_in_44, pp_in_45, pp_in_46, pp_in_47, pp_in_48, pp_in_49, pp_in_50, pp_in_51, pp_in_52, pp_in_53, pp_in_54, pp_in_55, pp_in_56, pp_in_57, pp_in_58, pp_in_59, pp_in_60, pp_in_61, pp_in_62, pp_in_63,
    output wire out_pp_0, out_pp_1, out_pp_8, out_pp_16, out_pp_17, out_pp_21, out_pp_63, comp_0_S, comp_2_S, comp_4_S, comp_5_S, comp_8_S, comp_9_S, comp_10_S, comp_14_S, comp_20_S, comp_25_S, comp_26_S, comp_28_S, comp_31_S, comp_35_S, comp_37_S, comp_38_S, comp_40_S, comp_41_S, comp_28_CO, comp_38_CO, comp_39_CO, comp_41_CO
);

    // Internal wire declarations
    wire comp_0_CO;
    wire comp_1_S;
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
    wire comp_10_CO;
    wire comp_11_S;
    wire comp_11_CO;
    wire comp_12_S;
    wire comp_12_CO;
    wire comp_13_S;
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
    wire comp_19_S;
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
    wire comp_29_S;
    wire comp_29_CO;
    wire comp_30_S;
    wire comp_30_CO;
    wire comp_31_CO;
    wire comp_32_S;
    wire comp_32_CO;
    wire comp_33_S;
    wire comp_33_CO;
    wire comp_34_S;
    wire comp_34_CO;
    wire comp_35_CO;
    wire comp_36_S;
    wire comp_36_CO;
    wire comp_37_CO;
    wire comp_39_S;
    wire comp_40_CO;

    // Feed-through assignments
    assign out_pp_0 = pp_in_0;
    assign out_pp_1 = pp_in_1;
    assign out_pp_8 = pp_in_8;
    assign out_pp_16 = pp_in_16;
    assign out_pp_17 = pp_in_17;
    assign out_pp_21 = pp_in_21;
    assign out_pp_63 = pp_in_63;

    // Compressor Tree Instantiations
    HA1D1BWP12T40P140 U_comp_0 (
        .A(pp_in_9),
        .B(pp_in_2),
        .S(comp_0_S),
        .CO(comp_0_CO)
    );

    HA1D1BWP12T40P140 U_comp_1 (
        .A(pp_in_3),
        .B(pp_in_24),
        .S(comp_1_S),
        .CO(comp_1_CO)
    );

    FA1D1BWP12T40P140 U_comp_2 (
        .A(comp_0_CO),
        .B(pp_in_10),
        .CI(comp_1_S),
        .S(comp_2_S),
        .CO(comp_2_CO)
    );

    HA1D1BWP12T40P140 U_comp_3 (
        .A(pp_in_18),
        .B(pp_in_11),
        .S(comp_3_S),
        .CO(comp_3_CO)
    );

    FA1D1BWP12T40P140 U_comp_4 (
        .A(pp_in_4),
        .B(pp_in_25),
        .CI(pp_in_32),
        .S(comp_4_S),
        .CO(comp_4_CO)
    );

    FA1D1BWP12T40P140 U_comp_5 (
        .A(comp_3_S),
        .B(comp_2_CO),
        .CI(comp_1_CO),
        .S(comp_5_S),
        .CO(comp_5_CO)
    );

    FA1D1BWP12T40P140 U_comp_6 (
        .A(comp_3_CO),
        .B(pp_in_26),
        .CI(pp_in_40),
        .S(comp_6_S),
        .CO(comp_6_CO)
    );

    HA1D1BWP12T40P140 U_comp_7 (
        .A(pp_in_33),
        .B(pp_in_19),
        .S(comp_7_S),
        .CO(comp_7_CO)
    );

    FA1D1BWP12T40P140 U_comp_8 (
        .A(comp_7_S),
        .B(pp_in_12),
        .CI(pp_in_5),
        .S(comp_8_S),
        .CO(comp_8_CO)
    );

    FA1D1BWP12T40P140 U_comp_9 (
        .A(comp_5_CO),
        .B(comp_4_CO),
        .CI(comp_6_S),
        .S(comp_9_S),
        .CO(comp_9_CO)
    );

    HA1D1BWP12T40P140 U_comp_10 (
        .A(pp_in_34),
        .B(pp_in_41),
        .S(comp_10_S),
        .CO(comp_10_CO)
    );

    FA1D1BWP12T40P140 U_comp_11 (
        .A(pp_in_27),
        .B(pp_in_6),
        .CI(pp_in_20),
        .S(comp_11_S),
        .CO(comp_11_CO)
    );

    FA1D1BWP12T40P140 U_comp_12 (
        .A(comp_11_S),
        .B(comp_8_CO),
        .CI(comp_6_CO),
        .S(comp_12_S),
        .CO(comp_12_CO)
    );

    FA1D1BWP12T40P140 U_comp_13 (
        .A(pp_in_13),
        .B(comp_7_CO),
        .CI(pp_in_48),
        .S(comp_13_S),
        .CO(comp_13_CO)
    );

    FA1D1BWP12T40P140 U_comp_14 (
        .A(comp_13_S),
        .B(comp_12_S),
        .CI(comp_9_CO),
        .S(comp_14_S),
        .CO(comp_14_CO)
    );

    FA1D1BWP12T40P140 U_comp_15 (
        .A(pp_in_56),
        .B(comp_11_CO),
        .CI(comp_13_CO),
        .S(comp_15_S),
        .CO(comp_15_CO)
    );

    HA1D1BWP12T40P140 U_comp_16 (
        .A(pp_in_42),
        .B(pp_in_28),
        .S(comp_16_S),
        .CO(comp_16_CO)
    );

    FA1D1BWP12T40P140 U_comp_17 (
        .A(pp_in_35),
        .B(pp_in_14),
        .CI(comp_10_CO),
        .S(comp_17_S),
        .CO(comp_17_CO)
    );

    FA1D1BWP12T40P140 U_comp_18 (
        .A(comp_12_CO),
        .B(comp_17_S),
        .CI(comp_16_S),
        .S(comp_18_S),
        .CO(comp_18_CO)
    );

    FA1D1BWP12T40P140 U_comp_19 (
        .A(comp_15_S),
        .B(pp_in_49),
        .CI(pp_in_7),
        .S(comp_19_S),
        .CO(comp_19_CO)
    );

    FA1D1BWP12T40P140 U_comp_20 (
        .A(comp_19_S),
        .B(comp_18_S),
        .CI(comp_14_CO),
        .S(comp_20_S),
        .CO(comp_20_CO)
    );

    FA1D1BWP12T40P140 U_comp_21 (
        .A(comp_18_CO),
        .B(comp_17_CO),
        .CI(comp_19_CO),
        .S(comp_21_S),
        .CO(comp_21_CO)
    );

    HA1D1BWP12T40P140 U_comp_22 (
        .A(pp_in_57),
        .B(pp_in_43),
        .S(comp_22_S),
        .CO(comp_22_CO)
    );

    FA1D1BWP12T40P140 U_comp_23 (
        .A(pp_in_15),
        .B(pp_in_29),
        .CI(pp_in_50),
        .S(comp_23_S),
        .CO(comp_23_CO)
    );

    FA1D1BWP12T40P140 U_comp_24 (
        .A(pp_in_36),
        .B(comp_15_CO),
        .CI(pp_in_22),
        .S(comp_24_S),
        .CO(comp_24_CO)
    );

    FA1D1BWP12T40P140 U_comp_25 (
        .A(comp_21_S),
        .B(comp_16_CO),
        .CI(comp_22_S),
        .S(comp_25_S),
        .CO(comp_25_CO)
    );

    FA1D1BWP12T40P140 U_comp_26 (
        .A(comp_24_S),
        .B(comp_23_S),
        .CI(comp_20_CO),
        .S(comp_26_S),
        .CO(comp_26_CO)
    );

    FA1D1BWP12T40P140 U_comp_27 (
        .A(pp_in_30),
        .B(pp_in_44),
        .CI(pp_in_58),
        .S(comp_27_S),
        .CO(comp_27_CO)
    );

    FA1D1BWP12T40P140 U_comp_28 (
        .A(comp_25_CO),
        .B(comp_26_CO),
        .CI(comp_24_CO),
        .S(comp_28_S),
        .CO(comp_28_CO)
    );

    FA1D1BWP12T40P140 U_comp_29 (
        .A(comp_23_CO),
        .B(comp_21_CO),
        .CI(pp_in_23),
        .S(comp_29_S),
        .CO(comp_29_CO)
    );

    FA1D1BWP12T40P140 U_comp_30 (
        .A(pp_in_51),
        .B(pp_in_37),
        .CI(comp_22_CO),
        .S(comp_30_S),
        .CO(comp_30_CO)
    );

    FA1D1BWP12T40P140 U_comp_31 (
        .A(comp_29_S),
        .B(comp_30_S),
        .CI(comp_27_S),
        .S(comp_31_S),
        .CO(comp_31_CO)
    );

    FA1D1BWP12T40P140 U_comp_32 (
        .A(pp_in_59),
        .B(pp_in_45),
        .CI(pp_in_31),
        .S(comp_32_S),
        .CO(comp_32_CO)
    );

    FA1D1BWP12T40P140 U_comp_33 (
        .A(comp_27_CO),
        .B(comp_30_CO),
        .CI(comp_29_CO),
        .S(comp_33_S),
        .CO(comp_33_CO)
    );

    FA1D1BWP12T40P140 U_comp_34 (
        .A(pp_in_52),
        .B(pp_in_38),
        .CI(comp_31_CO),
        .S(comp_34_S),
        .CO(comp_34_CO)
    );

    FA1D1BWP12T40P140 U_comp_35 (
        .A(comp_32_S),
        .B(comp_33_S),
        .CI(comp_34_S),
        .S(comp_35_S),
        .CO(comp_35_CO)
    );

    FA1D1BWP12T40P140 U_comp_36 (
        .A(pp_in_53),
        .B(pp_in_46),
        .CI(pp_in_39),
        .S(comp_36_S),
        .CO(comp_36_CO)
    );

    FA1D1BWP12T40P140 U_comp_37 (
        .A(pp_in_60),
        .B(comp_36_S),
        .CI(comp_32_CO),
        .S(comp_37_S),
        .CO(comp_37_CO)
    );

    FA1D1BWP12T40P140 U_comp_38 (
        .A(comp_34_CO),
        .B(comp_35_CO),
        .CI(comp_33_CO),
        .S(comp_38_S),
        .CO(comp_38_CO)
    );

    FA1D1BWP12T40P140 U_comp_39 (
        .A(comp_37_CO),
        .B(pp_in_47),
        .CI(pp_in_54),
        .S(comp_39_S),
        .CO(comp_39_CO)
    );

    FA1D1BWP12T40P140 U_comp_40 (
        .A(comp_36_CO),
        .B(comp_39_S),
        .CI(pp_in_61),
        .S(comp_40_S),
        .CO(comp_40_CO)
    );

    FA1D1BWP12T40P140 U_comp_41 (
        .A(pp_in_55),
        .B(comp_40_CO),
        .CI(pp_in_62),
        .S(comp_41_S),
        .CO(comp_41_CO)
    );

endmodule
