module domac_compressor_tree (
    input wire pp_in_0, pp_in_1, pp_in_2, pp_in_3, pp_in_4, pp_in_5, pp_in_6, pp_in_7,
    output wire pp_in_2, comp_5_S, comp_0_CO, comp_1_CO, comp_2_CO, comp_3_CO, comp_4_CO, comp_5_CO
);

    // Internal wire declarations
    wire comp_0_S;
    wire comp_0_CO;
    wire comp_1_S;
    wire comp_1_CO;
    wire comp_2_S;
    wire comp_2_CO;
    wire comp_3_S;
    wire comp_3_CO;
    wire comp_4_S;
    wire comp_4_CO;
    wire comp_5_S;
    wire comp_5_CO;

    // Compressor Tree Instantiations
    HA1D1BWP12T40P140 U_comp_0 (
        .A(pp_in_5),
        .B(pp_in_7),
        .S(comp_0_S),
        .CO(comp_0_CO)
    );

    HA1D1BWP12T40P140 U_comp_1 (
        .A(pp_in_0),
        .B(pp_in_1),
        .S(comp_1_S),
        .CO(comp_1_CO)
    );

    HA1D1BWP12T40P140 U_comp_2 (
        .A(pp_in_4),
        .B(comp_0_S),
        .S(comp_2_S),
        .CO(comp_2_CO)
    );

    HA1D1BWP12T40P140 U_comp_3 (
        .A(pp_in_6),
        .B(comp_1_S),
        .S(comp_3_S),
        .CO(comp_3_CO)
    );

    HA1D1BWP12T40P140 U_comp_4 (
        .A(comp_2_S),
        .B(comp_3_S),
        .S(comp_4_S),
        .CO(comp_4_CO)
    );

    HA1D1BWP12T40P140 U_comp_5 (
        .A(pp_in_3),
        .B(comp_4_S),
        .S(comp_5_S),
        .CO(comp_5_CO)
    );

endmodule
