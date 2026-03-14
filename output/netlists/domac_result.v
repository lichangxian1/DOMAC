module domac_compressor_tree (
    input wire pp_in_0, pp_in_1, pp_in_2, pp_in_3, pp_in_4, pp_in_5, pp_in_6, pp_in_7, pp_in_8, pp_in_9, pp_in_10, pp_in_11, pp_in_12, pp_in_13, pp_in_14, pp_in_15, pp_in_16, pp_in_17, pp_in_18, pp_in_19, pp_in_20, pp_in_21, pp_in_22, pp_in_23, pp_in_24, pp_in_25, pp_in_26, pp_in_27, pp_in_28, pp_in_29, pp_in_30, pp_in_31, pp_in_32, pp_in_33, pp_in_34, pp_in_35, pp_in_36, pp_in_37, pp_in_38, pp_in_39, pp_in_40, pp_in_41, pp_in_42, pp_in_43, pp_in_44, pp_in_45, pp_in_46, pp_in_47, pp_in_48, pp_in_49, pp_in_50, pp_in_51, pp_in_52, pp_in_53, pp_in_54, pp_in_55, pp_in_56, pp_in_57, pp_in_58, pp_in_59, pp_in_60, pp_in_61, pp_in_62, pp_in_63,
    output wire out_pp_in_0, out_pp_in_1, out_pp_in_2, out_pp_in_63, comp_0_S, comp_2_S, comp_5_S, comp_9_S, comp_14_S, comp_0_CO, comp_1_CO, comp_2_CO, comp_3_CO, comp_4_CO, comp_5_CO, comp_6_CO, comp_7_CO, comp_8_CO, comp_9_CO, comp_10_CO, comp_11_CO, comp_12_CO, comp_13_CO, comp_14_CO, comp_15_CO, comp_16_CO, comp_17_CO, comp_18_CO, comp_19_CO, comp_20_CO, comp_21_CO, comp_22_CO, comp_23_CO, comp_24_CO, comp_25_CO, comp_26_CO, comp_27_CO, comp_28_CO, comp_29_CO, comp_30_CO, comp_31_CO, comp_32_CO, comp_33_CO, comp_34_CO, comp_35_CO, comp_36_CO, comp_37_CO, comp_38_CO, comp_39_CO, comp_40_CO, comp_41_CO
);

    // Internal wire declarations
    wire comp_1_S;
    wire comp_3_S;
    wire comp_4_S;
    wire comp_6_S;
    wire comp_7_S;
    wire comp_8_S;
    wire comp_10_S;
    wire comp_11_S;
    wire comp_12_S;
    wire comp_13_S;
    wire comp_15_S;
    wire comp_16_S;
    wire comp_17_S;
    wire comp_18_S;
    wire comp_19_S;
    wire comp_20_S;
    wire comp_21_S;
    wire comp_22_S;
    wire comp_23_S;
    wire comp_24_S;
    wire comp_25_S;
    wire comp_26_S;
    wire comp_27_S;
    wire comp_28_S;
    wire comp_29_S;
    wire comp_30_S;
    wire comp_31_S;
    wire comp_32_S;
    wire comp_33_S;
    wire comp_34_S;
    wire comp_35_S;
    wire comp_36_S;
    wire comp_37_S;
    wire comp_38_S;
    wire comp_39_S;
    wire comp_40_S;
    wire comp_41_S;

    // Feed-through assignments
    assign out_pp_in_0 = pp_in_0;
    assign out_pp_in_1 = pp_in_1;
    assign out_pp_in_2 = pp_in_2;
    assign out_pp_in_63 = pp_in_63;

    // Compressor Tree Instantiations
    FA1D1BWP12T40P140 U_comp_0 (
        .A(pp_in_3),
        .B(pp_in_5),
        .CI(pp_in_4),
        .S(comp_0_S),
        .CO(comp_0_CO)
    );

    HA1D1BWP12T40P140 U_comp_1 (
        .A(pp_in_7),
        .B(pp_in_6),
        .S(comp_1_S),
        .CO(comp_1_CO)
    );

    FA1D1BWP12T40P140 U_comp_2 (
        .A(comp_1_S),
        .B(pp_in_9),
        .CI(pp_in_8),
        .S(comp_2_S),
        .CO(comp_2_CO)
    );

    HA1D1BWP12T40P140 U_comp_3 (
        .A(pp_in_10),
        .B(pp_in_14),
        .S(comp_3_S),
        .CO(comp_3_CO)
    );

    HA1D1BWP12T40P140 U_comp_4 (
        .A(pp_in_11),
        .B(comp_3_S),
        .S(comp_4_S),
        .CO(comp_4_CO)
    );

    FA1D1BWP12T40P140 U_comp_5 (
        .A(pp_in_13),
        .B(comp_4_S),
        .CI(pp_in_12),
        .S(comp_5_S),
        .CO(comp_5_CO)
    );

    HA1D1BWP12T40P140 U_comp_6 (
        .A(pp_in_16),
        .B(pp_in_20),
        .S(comp_6_S),
        .CO(comp_6_CO)
    );

    HA1D1BWP12T40P140 U_comp_7 (
        .A(pp_in_15),
        .B(comp_6_S),
        .S(comp_7_S),
        .CO(comp_7_CO)
    );

    HA1D1BWP12T40P140 U_comp_8 (
        .A(pp_in_18),
        .B(comp_7_S),
        .S(comp_8_S),
        .CO(comp_8_CO)
    );

    FA1D1BWP12T40P140 U_comp_9 (
        .A(pp_in_17),
        .B(comp_8_S),
        .CI(pp_in_19),
        .S(comp_9_S),
        .CO(comp_9_CO)
    );

    HA1D1BWP12T40P140 U_comp_10 (
        .A(pp_in_21),
        .B(pp_in_22),
        .S(comp_10_S),
        .CO(comp_10_CO)
    );

    HA1D1BWP12T40P140 U_comp_11 (
        .A(pp_in_27),
        .B(comp_10_S),
        .S(comp_11_S),
        .CO(comp_11_CO)
    );

    HA1D1BWP12T40P140 U_comp_12 (
        .A(pp_in_26),
        .B(comp_11_S),
        .S(comp_12_S),
        .CO(comp_12_CO)
    );

    FA1D1BWP12T40P140 U_comp_13 (
        .A(pp_in_25),
        .B(comp_12_S),
        .CI(pp_in_23),
        .S(comp_13_S),
        .CO(comp_13_CO)
    );

    FA1D1BWP12T40P140 U_comp_14 (
        .A(pp_in_24),
        .B(comp_13_S),
        .CI(comp_20_S),
        .S(comp_14_S),
        .CO(comp_14_CO)
    );

    HA1D1BWP12T40P140 U_comp_15 (
        .A(pp_in_28),
        .B(pp_in_29),
        .S(comp_15_S),
        .CO(comp_15_CO)
    );

    HA1D1BWP12T40P140 U_comp_16 (
        .A(pp_in_32),
        .B(pp_in_34),
        .S(comp_16_S),
        .CO(comp_16_CO)
    );

    HA1D1BWP12T40P140 U_comp_17 (
        .A(comp_15_S),
        .B(comp_16_S),
        .S(comp_17_S),
        .CO(comp_17_CO)
    );

    HA1D1BWP12T40P140 U_comp_18 (
        .A(pp_in_35),
        .B(comp_17_S),
        .S(comp_18_S),
        .CO(comp_18_CO)
    );

    FA1D1BWP12T40P140 U_comp_19 (
        .A(pp_in_33),
        .B(comp_18_S),
        .CI(pp_in_31),
        .S(comp_19_S),
        .CO(comp_19_CO)
    );

    FA1D1BWP12T40P140 U_comp_20 (
        .A(pp_in_30),
        .B(comp_19_S),
        .CI(comp_26_S),
        .S(comp_20_S),
        .CO(comp_20_CO)
    );

    HA1D1BWP12T40P140 U_comp_21 (
        .A(pp_in_36),
        .B(pp_in_37),
        .S(comp_21_S),
        .CO(comp_21_CO)
    );

    HA1D1BWP12T40P140 U_comp_22 (
        .A(pp_in_39),
        .B(comp_21_S),
        .S(comp_22_S),
        .CO(comp_22_CO)
    );

    HA1D1BWP12T40P140 U_comp_23 (
        .A(pp_in_42),
        .B(comp_22_S),
        .S(comp_23_S),
        .CO(comp_23_CO)
    );

    HA1D1BWP12T40P140 U_comp_24 (
        .A(pp_in_41),
        .B(comp_23_S),
        .S(comp_24_S),
        .CO(comp_24_CO)
    );

    HA1D1BWP12T40P140 U_comp_25 (
        .A(pp_in_40),
        .B(comp_24_S),
        .S(comp_25_S),
        .CO(comp_25_CO)
    );

    FA1D1BWP12T40P140 U_comp_26 (
        .A(pp_in_38),
        .B(comp_25_S),
        .CI(comp_31_S),
        .S(comp_26_S),
        .CO(comp_26_CO)
    );

    HA1D1BWP12T40P140 U_comp_27 (
        .A(pp_in_43),
        .B(pp_in_44),
        .S(comp_27_S),
        .CO(comp_27_CO)
    );

    HA1D1BWP12T40P140 U_comp_28 (
        .A(pp_in_46),
        .B(comp_27_S),
        .S(comp_28_S),
        .CO(comp_28_CO)
    );

    HA1D1BWP12T40P140 U_comp_29 (
        .A(pp_in_48),
        .B(comp_28_S),
        .S(comp_29_S),
        .CO(comp_29_CO)
    );

    HA1D1BWP12T40P140 U_comp_30 (
        .A(pp_in_47),
        .B(comp_29_S),
        .S(comp_30_S),
        .CO(comp_30_CO)
    );

    FA1D1BWP12T40P140 U_comp_31 (
        .A(pp_in_45),
        .B(comp_30_S),
        .CI(comp_35_S),
        .S(comp_31_S),
        .CO(comp_31_CO)
    );

    HA1D1BWP12T40P140 U_comp_32 (
        .A(pp_in_50),
        .B(pp_in_49),
        .S(comp_32_S),
        .CO(comp_32_CO)
    );

    HA1D1BWP12T40P140 U_comp_33 (
        .A(pp_in_51),
        .B(comp_32_S),
        .S(comp_33_S),
        .CO(comp_33_CO)
    );

    HA1D1BWP12T40P140 U_comp_34 (
        .A(pp_in_53),
        .B(comp_33_S),
        .S(comp_34_S),
        .CO(comp_34_CO)
    );

    FA1D1BWP12T40P140 U_comp_35 (
        .A(pp_in_52),
        .B(comp_34_S),
        .CI(comp_38_S),
        .S(comp_35_S),
        .CO(comp_35_CO)
    );

    HA1D1BWP12T40P140 U_comp_36 (
        .A(pp_in_54),
        .B(pp_in_55),
        .S(comp_36_S),
        .CO(comp_36_CO)
    );

    HA1D1BWP12T40P140 U_comp_37 (
        .A(pp_in_56),
        .B(comp_36_S),
        .S(comp_37_S),
        .CO(comp_37_CO)
    );

    FA1D1BWP12T40P140 U_comp_38 (
        .A(comp_37_S),
        .B(pp_in_57),
        .CI(comp_40_S),
        .S(comp_38_S),
        .CO(comp_38_CO)
    );

    HA1D1BWP12T40P140 U_comp_39 (
        .A(pp_in_58),
        .B(pp_in_59),
        .S(comp_39_S),
        .CO(comp_39_CO)
    );

    FA1D1BWP12T40P140 U_comp_40 (
        .A(comp_39_S),
        .B(pp_in_60),
        .CI(comp_41_S),
        .S(comp_40_S),
        .CO(comp_40_CO)
    );

    HA1D1BWP12T40P140 U_comp_41 (
        .A(pp_in_61),
        .B(pp_in_62),
        .S(comp_41_S),
        .CO(comp_41_CO)
    );

endmodule
