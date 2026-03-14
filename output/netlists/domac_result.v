module domac_compressor_tree (
    input wire pp_in_0, pp_in_1, pp_in_2, pp_in_3, pp_in_4, pp_in_5, pp_in_6, pp_in_7, pp_in_8, pp_in_9, pp_in_10, pp_in_11, pp_in_12, pp_in_13, pp_in_14, pp_in_15, pp_in_16, pp_in_17, pp_in_18, pp_in_19, pp_in_20, pp_in_21, pp_in_22, pp_in_23, pp_in_24, pp_in_25, pp_in_26, pp_in_27, pp_in_28, pp_in_29, pp_in_30, pp_in_31, pp_in_32, pp_in_33, pp_in_34, pp_in_35, pp_in_36, pp_in_37, pp_in_38, pp_in_39, pp_in_40, pp_in_41, pp_in_42, pp_in_43, pp_in_44, pp_in_45, pp_in_46, pp_in_47, pp_in_48, pp_in_49, pp_in_50, pp_in_51, pp_in_52, pp_in_53, pp_in_54, pp_in_55, pp_in_56, pp_in_57, pp_in_58, pp_in_59, pp_in_60, pp_in_61, pp_in_62, pp_in_63,
    output wire out_pp_0, out_pp_1, out_pp_2, out_pp_52, out_pp_56, out_pp_60, out_pp_63, comp_0_S, comp_2_S, comp_5_S, comp_9_S, comp_14_S, comp_20_S, comp_26_S, comp_31_S, comp_35_S, comp_38_S, comp_40_S, comp_41_S, comp_22_CO, comp_39_CO, comp_41_CO
);

    // Internal wire declarations
    wire comp_0_CO;
    wire comp_1_S;
    wire comp_1_CO;
    wire comp_2_CO;
    wire comp_3_S;
    wire comp_3_CO;
    wire comp_4_S;
    wire comp_4_CO;
    wire comp_5_CO;
    wire comp_6_S;
    wire comp_6_CO;
    wire comp_7_S;
    wire comp_7_CO;
    wire comp_8_S;
    wire comp_8_CO;
    wire comp_9_CO;
    wire comp_10_S;
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
    wire comp_23_S;
    wire comp_23_CO;
    wire comp_24_S;
    wire comp_24_CO;
    wire comp_25_S;
    wire comp_25_CO;
    wire comp_26_CO;
    wire comp_27_S;
    wire comp_27_CO;
    wire comp_28_S;
    wire comp_28_CO;
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
    wire comp_37_S;
    wire comp_37_CO;
    wire comp_38_CO;
    wire comp_39_S;
    wire comp_40_CO;

    // Feed-through assignments
    assign out_pp_0 = pp_in_0;
    assign out_pp_1 = pp_in_1;
    assign out_pp_2 = pp_in_2;
    assign out_pp_52 = pp_in_52;
    assign out_pp_56 = pp_in_56;
    assign out_pp_60 = pp_in_60;
    assign out_pp_63 = pp_in_63;

    // Compressor Tree Instantiations
    FA1D0BWP12T40P140 U_comp_0 (
        .A(pp_in_4),
        .B(pp_in_5),
        .CI(pp_in_3),
        .S(comp_0_S),
        .CO(comp_0_CO)
    );

    FA1D0BWP12T40P140 U_comp_1 (
        .A(pp_in_7),
        .B(pp_in_8),
        .CI(comp_0_CO),
        .S(comp_1_S),
        .CO(comp_1_CO)
    );

    FA1D0BWP12T40P140 U_comp_2 (
        .A(pp_in_6),
        .B(comp_1_S),
        .CI(pp_in_9),
        .S(comp_2_S),
        .CO(comp_2_CO)
    );

    FA1D0BWP12T40P140 U_comp_3 (
        .A(pp_in_12),
        .B(pp_in_13),
        .CI(comp_2_CO),
        .S(comp_3_S),
        .CO(comp_3_CO)
    );

    FA1D0BWP12T40P140 U_comp_4 (
        .A(pp_in_10),
        .B(comp_3_S),
        .CI(pp_in_11),
        .S(comp_4_S),
        .CO(comp_4_CO)
    );

    FA1D0BWP12T40P140 U_comp_5 (
        .A(pp_in_14),
        .B(comp_4_S),
        .CI(comp_1_CO),
        .S(comp_5_S),
        .CO(comp_5_CO)
    );

    FA1D0BWP12T40P140 U_comp_6 (
        .A(pp_in_15),
        .B(pp_in_17),
        .CI(comp_5_CO),
        .S(comp_6_S),
        .CO(comp_6_CO)
    );

    FA1D0BWP12T40P140 U_comp_7 (
        .A(pp_in_16),
        .B(comp_6_S),
        .CI(comp_3_CO),
        .S(comp_7_S),
        .CO(comp_7_CO)
    );

    FA1D0BWP12T40P140 U_comp_8 (
        .A(pp_in_19),
        .B(comp_7_S),
        .CI(pp_in_20),
        .S(comp_8_S),
        .CO(comp_8_CO)
    );

    FA1D0BWP12T40P140 U_comp_9 (
        .A(pp_in_18),
        .B(comp_8_S),
        .CI(comp_4_CO),
        .S(comp_9_S),
        .CO(comp_9_CO)
    );

    FA1D0BWP12T40P140 U_comp_10 (
        .A(pp_in_23),
        .B(pp_in_21),
        .CI(comp_9_CO),
        .S(comp_10_S),
        .CO(comp_10_CO)
    );

    FA1D0BWP12T40P140 U_comp_11 (
        .A(pp_in_24),
        .B(comp_10_S),
        .CI(comp_8_CO),
        .S(comp_11_S),
        .CO(comp_11_CO)
    );

    FA1D0BWP12T40P140 U_comp_12 (
        .A(pp_in_26),
        .B(comp_11_S),
        .CI(comp_6_CO),
        .S(comp_12_S),
        .CO(comp_12_CO)
    );

    FA1D0BWP12T40P140 U_comp_13 (
        .A(pp_in_22),
        .B(comp_12_S),
        .CI(pp_in_25),
        .S(comp_13_S),
        .CO(comp_13_CO)
    );

    FA1D0BWP12T40P140 U_comp_14 (
        .A(pp_in_27),
        .B(comp_13_S),
        .CI(comp_7_CO),
        .S(comp_14_S),
        .CO(comp_14_CO)
    );

    FA1D0BWP12T40P140 U_comp_15 (
        .A(pp_in_30),
        .B(pp_in_28),
        .CI(comp_14_CO),
        .S(comp_15_S),
        .CO(comp_15_CO)
    );

    FA1D0BWP12T40P140 U_comp_16 (
        .A(pp_in_29),
        .B(comp_15_S),
        .CI(comp_13_CO),
        .S(comp_16_S),
        .CO(comp_16_CO)
    );

    FA1D0BWP12T40P140 U_comp_17 (
        .A(pp_in_31),
        .B(comp_16_S),
        .CI(comp_12_CO),
        .S(comp_17_S),
        .CO(comp_17_CO)
    );

    FA1D0BWP12T40P140 U_comp_18 (
        .A(pp_in_32),
        .B(comp_17_S),
        .CI(comp_10_CO),
        .S(comp_18_S),
        .CO(comp_18_CO)
    );

    FA1D0BWP12T40P140 U_comp_19 (
        .A(pp_in_33),
        .B(comp_18_S),
        .CI(pp_in_35),
        .S(comp_19_S),
        .CO(comp_19_CO)
    );

    FA1D0BWP12T40P140 U_comp_20 (
        .A(pp_in_34),
        .B(comp_19_S),
        .CI(comp_11_CO),
        .S(comp_20_S),
        .CO(comp_20_CO)
    );

    FA1D0BWP12T40P140 U_comp_21 (
        .A(pp_in_38),
        .B(pp_in_39),
        .CI(comp_20_CO),
        .S(comp_21_S),
        .CO(comp_21_CO)
    );

    FA1D0BWP12T40P140 U_comp_22 (
        .A(pp_in_36),
        .B(comp_21_S),
        .CI(comp_19_CO),
        .S(comp_22_S),
        .CO(comp_22_CO)
    );

    FA1D0BWP12T40P140 U_comp_23 (
        .A(pp_in_37),
        .B(comp_22_S),
        .CI(comp_18_CO),
        .S(comp_23_S),
        .CO(comp_23_CO)
    );

    FA1D0BWP12T40P140 U_comp_24 (
        .A(pp_in_41),
        .B(comp_23_S),
        .CI(comp_17_CO),
        .S(comp_24_S),
        .CO(comp_24_CO)
    );

    FA1D0BWP12T40P140 U_comp_25 (
        .A(pp_in_40),
        .B(comp_24_S),
        .CI(comp_15_CO),
        .S(comp_25_S),
        .CO(comp_25_CO)
    );

    FA1D0BWP12T40P140 U_comp_26 (
        .A(pp_in_42),
        .B(comp_25_S),
        .CI(comp_16_CO),
        .S(comp_26_S),
        .CO(comp_26_CO)
    );

    FA1D0BWP12T40P140 U_comp_27 (
        .A(pp_in_44),
        .B(pp_in_48),
        .CI(comp_26_CO),
        .S(comp_27_S),
        .CO(comp_27_CO)
    );

    FA1D0BWP12T40P140 U_comp_28 (
        .A(pp_in_46),
        .B(comp_27_S),
        .CI(comp_25_CO),
        .S(comp_28_S),
        .CO(comp_28_CO)
    );

    FA1D0BWP12T40P140 U_comp_29 (
        .A(pp_in_45),
        .B(comp_28_S),
        .CI(comp_24_CO),
        .S(comp_29_S),
        .CO(comp_29_CO)
    );

    FA1D0BWP12T40P140 U_comp_30 (
        .A(pp_in_47),
        .B(comp_29_S),
        .CI(comp_23_CO),
        .S(comp_30_S),
        .CO(comp_30_CO)
    );

    FA1D0BWP12T40P140 U_comp_31 (
        .A(pp_in_43),
        .B(comp_30_S),
        .CI(comp_21_CO),
        .S(comp_31_S),
        .CO(comp_31_CO)
    );

    FA1D0BWP12T40P140 U_comp_32 (
        .A(comp_27_CO),
        .B(comp_29_CO),
        .CI(comp_31_CO),
        .S(comp_32_S),
        .CO(comp_32_CO)
    );

    FA1D0BWP12T40P140 U_comp_33 (
        .A(pp_in_53),
        .B(comp_32_S),
        .CI(comp_30_CO),
        .S(comp_33_S),
        .CO(comp_33_CO)
    );

    FA1D0BWP12T40P140 U_comp_34 (
        .A(pp_in_51),
        .B(comp_33_S),
        .CI(comp_28_CO),
        .S(comp_34_S),
        .CO(comp_34_CO)
    );

    FA1D0BWP12T40P140 U_comp_35 (
        .A(pp_in_49),
        .B(comp_34_S),
        .CI(pp_in_50),
        .S(comp_35_S),
        .CO(comp_35_CO)
    );

    FA1D0BWP12T40P140 U_comp_36 (
        .A(comp_32_CO),
        .B(comp_34_CO),
        .CI(comp_35_CO),
        .S(comp_36_S),
        .CO(comp_36_CO)
    );

    FA1D0BWP12T40P140 U_comp_37 (
        .A(pp_in_57),
        .B(comp_36_S),
        .CI(comp_33_CO),
        .S(comp_37_S),
        .CO(comp_37_CO)
    );

    FA1D0BWP12T40P140 U_comp_38 (
        .A(pp_in_54),
        .B(comp_37_S),
        .CI(pp_in_55),
        .S(comp_38_S),
        .CO(comp_38_CO)
    );

    FA1D0BWP12T40P140 U_comp_39 (
        .A(comp_36_CO),
        .B(comp_37_CO),
        .CI(comp_38_CO),
        .S(comp_39_S),
        .CO(comp_39_CO)
    );

    FA1D0BWP12T40P140 U_comp_40 (
        .A(pp_in_58),
        .B(comp_39_S),
        .CI(pp_in_59),
        .S(comp_40_S),
        .CO(comp_40_CO)
    );

    FA1D0BWP12T40P140 U_comp_41 (
        .A(pp_in_61),
        .B(pp_in_62),
        .CI(comp_40_CO),
        .S(comp_41_S),
        .CO(comp_41_CO)
    );

endmodule
