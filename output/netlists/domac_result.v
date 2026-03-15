module domac_compressor_tree (
    input wire pp_in_0, pp_in_1, pp_in_2, pp_in_3, pp_in_4, pp_in_5, pp_in_6, pp_in_7, pp_in_8, pp_in_9, pp_in_10, pp_in_11, pp_in_12, pp_in_13, pp_in_14, pp_in_15, pp_in_16, pp_in_17, pp_in_18, pp_in_19, pp_in_20, pp_in_21, pp_in_22, pp_in_23, pp_in_24, pp_in_25, pp_in_26, pp_in_27, pp_in_28, pp_in_29, pp_in_30, pp_in_31, pp_in_32, pp_in_33, pp_in_34, pp_in_35,
    output wire out_pp_0, out_pp_1, out_pp_2, out_pp_34, out_pp_35, comp_0_S, comp_2_S, comp_5_S, comp_9_S, comp_13_S, comp_16_S, comp_18_S, comp_19_S, comp_12_CO, comp_14_CO, comp_19_CO
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
    wire comp_13_CO;
    wire comp_14_S;
    wire comp_15_S;
    wire comp_15_CO;
    wire comp_16_CO;
    wire comp_17_S;
    wire comp_17_CO;
    wire comp_18_CO;

    // Feed-through assignments
    assign out_pp_0 = pp_in_0;
    assign out_pp_1 = pp_in_1;
    assign out_pp_2 = pp_in_2;
    assign out_pp_34 = pp_in_34;
    assign out_pp_35 = pp_in_35;

    // Compressor Tree Instantiations
    FA1D1BWP12T40P140 U_comp_0 (
        .A(pp_in_5),
        .B(pp_in_3),
        .CI(pp_in_4),
        .S(comp_0_S),
        .CO(comp_0_CO)
    );

    FA1D1BWP12T40P140 U_comp_1 (
        .A(pp_in_6),
        .B(pp_in_7),
        .CI(comp_0_CO),
        .S(comp_1_S),
        .CO(comp_1_CO)
    );

    FA1D1BWP12T40P140 U_comp_2 (
        .A(pp_in_8),
        .B(pp_in_9),
        .CI(comp_1_S),
        .S(comp_2_S),
        .CO(comp_2_CO)
    );

    FA1D1BWP12T40P140 U_comp_3 (
        .A(pp_in_10),
        .B(pp_in_11),
        .CI(comp_2_CO),
        .S(comp_3_S),
        .CO(comp_3_CO)
    );

    FA1D1BWP12T40P140 U_comp_4 (
        .A(pp_in_12),
        .B(pp_in_13),
        .CI(comp_3_S),
        .S(comp_4_S),
        .CO(comp_4_CO)
    );

    FA1D1BWP12T40P140 U_comp_5 (
        .A(pp_in_14),
        .B(comp_1_CO),
        .CI(comp_4_S),
        .S(comp_5_S),
        .CO(comp_5_CO)
    );

    FA1D1BWP12T40P140 U_comp_6 (
        .A(pp_in_15),
        .B(pp_in_18),
        .CI(comp_5_CO),
        .S(comp_6_S),
        .CO(comp_6_CO)
    );

    FA1D1BWP12T40P140 U_comp_7 (
        .A(pp_in_16),
        .B(pp_in_20),
        .CI(comp_6_S),
        .S(comp_7_S),
        .CO(comp_7_CO)
    );

    FA1D1BWP12T40P140 U_comp_8 (
        .A(pp_in_17),
        .B(pp_in_19),
        .CI(comp_7_S),
        .S(comp_8_S),
        .CO(comp_8_CO)
    );

    FA1D1BWP12T40P140 U_comp_9 (
        .A(comp_3_CO),
        .B(comp_4_CO),
        .CI(comp_8_S),
        .S(comp_9_S),
        .CO(comp_9_CO)
    );

    FA1D1BWP12T40P140 U_comp_10 (
        .A(pp_in_22),
        .B(pp_in_23),
        .CI(comp_9_CO),
        .S(comp_10_S),
        .CO(comp_10_CO)
    );

    FA1D1BWP12T40P140 U_comp_11 (
        .A(pp_in_21),
        .B(pp_in_24),
        .CI(comp_10_S),
        .S(comp_11_S),
        .CO(comp_11_CO)
    );

    FA1D1BWP12T40P140 U_comp_12 (
        .A(pp_in_25),
        .B(comp_6_CO),
        .CI(comp_11_S),
        .S(comp_12_S),
        .CO(comp_12_CO)
    );

    FA1D1BWP12T40P140 U_comp_13 (
        .A(comp_7_CO),
        .B(comp_8_CO),
        .CI(comp_12_S),
        .S(comp_13_S),
        .CO(comp_13_CO)
    );

    FA1D1BWP12T40P140 U_comp_14 (
        .A(pp_in_26),
        .B(pp_in_29),
        .CI(comp_13_CO),
        .S(comp_14_S),
        .CO(comp_14_CO)
    );

    FA1D1BWP12T40P140 U_comp_15 (
        .A(pp_in_27),
        .B(comp_11_CO),
        .CI(comp_14_S),
        .S(comp_15_S),
        .CO(comp_15_CO)
    );

    FA1D1BWP12T40P140 U_comp_16 (
        .A(pp_in_28),
        .B(comp_10_CO),
        .CI(comp_15_S),
        .S(comp_16_S),
        .CO(comp_16_CO)
    );

    FA1D1BWP12T40P140 U_comp_17 (
        .A(pp_in_32),
        .B(comp_15_CO),
        .CI(comp_16_CO),
        .S(comp_17_S),
        .CO(comp_17_CO)
    );

    FA1D1BWP12T40P140 U_comp_18 (
        .A(pp_in_30),
        .B(pp_in_31),
        .CI(comp_17_S),
        .S(comp_18_S),
        .CO(comp_18_CO)
    );

    FA1D0BWP12T40P140 U_comp_19 (
        .A(pp_in_33),
        .B(comp_17_CO),
        .CI(comp_18_CO),
        .S(comp_19_S),
        .CO(comp_19_CO)
    );

endmodule
