module dadda_baseline_ct (
    input wire pp_in_0, pp_in_1, pp_in_2, pp_in_3, pp_in_4, pp_in_5, pp_in_6, pp_in_7, pp_in_8, pp_in_9, pp_in_10, pp_in_11, pp_in_12, pp_in_13, pp_in_14, pp_in_15, pp_in_16, pp_in_17, pp_in_18, pp_in_19, pp_in_20, pp_in_21, pp_in_22, pp_in_23, pp_in_24, pp_in_25, pp_in_26, pp_in_27, pp_in_28, pp_in_29, pp_in_30, pp_in_31, pp_in_32, pp_in_33, pp_in_34, pp_in_35, pp_in_36, pp_in_37, pp_in_38, pp_in_39, pp_in_40, pp_in_41, pp_in_42, pp_in_43, pp_in_44, pp_in_45, pp_in_46, pp_in_47, pp_in_48, pp_in_49, pp_in_50, pp_in_51, pp_in_52, pp_in_53, pp_in_54, pp_in_55, pp_in_56, pp_in_57, pp_in_58, pp_in_59, pp_in_60, pp_in_61, pp_in_62, pp_in_63,
    output wire out_pp_in_0, out_pp_in_1, out_pp_in_8, comp_30_S, out_pp_in_2, comp_31_S, comp_20_S, comp_32_S, comp_21_S, comp_33_S, comp_22_S, comp_34_S, comp_23_S, comp_35_S, comp_24_S, comp_36_S, comp_25_S, comp_37_S, comp_26_S, comp_38_S, comp_27_S, comp_39_S, comp_28_S, comp_40_S, comp_29_S, comp_41_S, out_pp_in_55, out_pp_in_63, comp_41_CO
);

    wire comp_0_S, comp_1_S, comp_2_S, comp_3_S, comp_4_S, comp_5_S, comp_6_S, comp_7_S, comp_8_S, comp_9_S, 
         comp_10_S, comp_11_S, comp_12_S, comp_13_S, comp_14_S, comp_15_S, comp_16_S, comp_17_S, comp_18_S, comp_19_S, 
         comp_0_CO, comp_1_CO, comp_2_CO, comp_3_CO, comp_4_CO, comp_5_CO, comp_6_CO, comp_7_CO, comp_8_CO, comp_9_CO, 
         comp_10_CO, comp_11_CO, comp_12_CO, comp_13_CO, comp_14_CO, comp_15_CO, comp_16_CO, comp_17_CO, comp_18_CO, comp_19_CO, 
         comp_20_CO, comp_21_CO, comp_22_CO, comp_23_CO, comp_24_CO, comp_25_CO, comp_26_CO, comp_27_CO, comp_28_CO, comp_29_CO, 
         comp_30_CO, comp_31_CO, comp_32_CO, comp_33_CO, comp_34_CO, comp_35_CO, comp_36_CO, comp_37_CO, comp_38_CO, comp_39_CO, 
         comp_40_CO;

    assign out_pp_in_0 = pp_in_0;
    assign out_pp_in_1 = pp_in_1;
    assign out_pp_in_8 = pp_in_8;
    assign out_pp_in_2 = pp_in_2;
    assign out_pp_in_55 = pp_in_55;
    assign out_pp_in_63 = pp_in_63;

    HA1D0BWP12T40P140 U_comp_0 (.A(pp_in_48), .B(pp_in_41), .S(comp_0_S), .CO(comp_0_CO));
    FA1D0BWP12T40P140 U_comp_1 (.A(comp_0_CO), .B(pp_in_56), .CI(pp_in_49), .S(comp_1_S), .CO(comp_1_CO));
    HA1D0BWP12T40P140 U_comp_2 (.A(pp_in_42), .B(pp_in_35), .S(comp_2_S), .CO(comp_2_CO));
    FA1D0BWP12T40P140 U_comp_3 (.A(comp_2_CO), .B(comp_1_CO), .CI(pp_in_57), .S(comp_3_S), .CO(comp_3_CO));
    HA1D0BWP12T40P140 U_comp_4 (.A(pp_in_50), .B(pp_in_43), .S(comp_4_S), .CO(comp_4_CO));
    FA1D0BWP12T40P140 U_comp_5 (.A(comp_4_CO), .B(comp_3_CO), .CI(pp_in_58), .S(comp_5_S), .CO(comp_5_CO));
    HA1D0BWP12T40P140 U_comp_6 (.A(pp_in_32), .B(pp_in_25), .S(comp_6_S), .CO(comp_6_CO));
    FA1D0BWP12T40P140 U_comp_7 (.A(comp_6_CO), .B(pp_in_40), .CI(pp_in_33), .S(comp_7_S), .CO(comp_7_CO));
    HA1D0BWP12T40P140 U_comp_8 (.A(pp_in_26), .B(pp_in_19), .S(comp_8_S), .CO(comp_8_CO));
    FA1D0BWP12T40P140 U_comp_9 (.A(comp_8_CO), .B(comp_7_CO), .CI(pp_in_34), .S(comp_9_S), .CO(comp_9_CO));
    FA1D0BWP12T40P140 U_comp_10 (.A(pp_in_27), .B(pp_in_20), .CI(pp_in_13), .S(comp_10_S), .CO(comp_10_CO));
    FA1D0BWP12T40P140 U_comp_11 (.A(comp_10_CO), .B(comp_9_CO), .CI(pp_in_28), .S(comp_11_S), .CO(comp_11_CO));
    FA1D0BWP12T40P140 U_comp_12 (.A(pp_in_21), .B(pp_in_14), .CI(pp_in_7), .S(comp_12_S), .CO(comp_12_CO));
    FA1D0BWP12T40P140 U_comp_13 (.A(comp_12_CO), .B(comp_11_CO), .CI(pp_in_36), .S(comp_13_S), .CO(comp_13_CO));
    FA1D0BWP12T40P140 U_comp_14 (.A(pp_in_29), .B(pp_in_22), .CI(pp_in_15), .S(comp_14_S), .CO(comp_14_CO));
    FA1D0BWP12T40P140 U_comp_15 (.A(comp_14_CO), .B(comp_13_CO), .CI(pp_in_51), .S(comp_15_S), .CO(comp_15_CO));
    FA1D0BWP12T40P140 U_comp_16 (.A(pp_in_44), .B(pp_in_37), .CI(pp_in_30), .S(comp_16_S), .CO(comp_16_CO));
    FA1D0BWP12T40P140 U_comp_17 (.A(comp_16_CO), .B(comp_15_CO), .CI(comp_5_CO), .S(comp_17_S), .CO(comp_17_CO));
    FA1D0BWP12T40P140 U_comp_18 (.A(pp_in_59), .B(pp_in_52), .CI(pp_in_45), .S(comp_18_S), .CO(comp_18_CO));
    FA1D0BWP12T40P140 U_comp_19 (.A(comp_18_CO), .B(comp_17_CO), .CI(pp_in_60), .S(comp_19_S), .CO(comp_19_CO));
    HA1D0BWP12T40P140 U_comp_20 (.A(pp_in_24), .B(pp_in_17), .S(comp_20_S), .CO(comp_20_CO));
    FA1D0BWP12T40P140 U_comp_21 (.A(comp_20_CO), .B(pp_in_18), .CI(pp_in_11), .S(comp_21_S), .CO(comp_21_CO));
    FA1D0BWP12T40P140 U_comp_22 (.A(comp_21_CO), .B(pp_in_12), .CI(pp_in_5), .S(comp_22_S), .CO(comp_22_CO));
    FA1D0BWP12T40P140 U_comp_23 (.A(comp_22_CO), .B(pp_in_6), .CI(comp_0_S), .S(comp_23_S), .CO(comp_23_CO));
    FA1D0BWP12T40P140 U_comp_24 (.A(comp_23_CO), .B(comp_2_S), .CI(comp_1_S), .S(comp_24_S), .CO(comp_24_CO));
    FA1D0BWP12T40P140 U_comp_25 (.A(comp_24_CO), .B(comp_4_S), .CI(comp_3_S), .S(comp_25_S), .CO(comp_25_CO));
    FA1D0BWP12T40P140 U_comp_26 (.A(comp_25_CO), .B(pp_in_23), .CI(comp_5_S), .S(comp_26_S), .CO(comp_26_CO));
    FA1D0BWP12T40P140 U_comp_27 (.A(comp_26_CO), .B(pp_in_38), .CI(pp_in_31), .S(comp_27_S), .CO(comp_27_CO));
    FA1D0BWP12T40P140 U_comp_28 (.A(comp_27_CO), .B(pp_in_53), .CI(pp_in_46), .S(comp_28_S), .CO(comp_28_CO));
    FA1D0BWP12T40P140 U_comp_29 (.A(comp_28_CO), .B(comp_19_CO), .CI(pp_in_61), .S(comp_29_S), .CO(comp_29_CO));
    HA1D0BWP12T40P140 U_comp_30 (.A(pp_in_16), .B(pp_in_9), .S(comp_30_S), .CO(comp_30_CO));
    FA1D0BWP12T40P140 U_comp_31 (.A(comp_30_CO), .B(pp_in_10), .CI(pp_in_3), .S(comp_31_S), .CO(comp_31_CO));
    FA1D0BWP12T40P140 U_comp_32 (.A(comp_31_CO), .B(pp_in_4), .CI(comp_6_S), .S(comp_32_S), .CO(comp_32_CO));
    FA1D0BWP12T40P140 U_comp_33 (.A(comp_32_CO), .B(comp_8_S), .CI(comp_7_S), .S(comp_33_S), .CO(comp_33_CO));
    FA1D0BWP12T40P140 U_comp_34 (.A(comp_33_CO), .B(comp_10_S), .CI(comp_9_S), .S(comp_34_S), .CO(comp_34_CO));
    FA1D0BWP12T40P140 U_comp_35 (.A(comp_34_CO), .B(comp_12_S), .CI(comp_11_S), .S(comp_35_S), .CO(comp_35_CO));
    FA1D0BWP12T40P140 U_comp_36 (.A(comp_35_CO), .B(comp_14_S), .CI(comp_13_S), .S(comp_36_S), .CO(comp_36_CO));
    FA1D0BWP12T40P140 U_comp_37 (.A(comp_36_CO), .B(comp_16_S), .CI(comp_15_S), .S(comp_37_S), .CO(comp_37_CO));
    FA1D0BWP12T40P140 U_comp_38 (.A(comp_37_CO), .B(comp_18_S), .CI(comp_17_S), .S(comp_38_S), .CO(comp_38_CO));
    FA1D0BWP12T40P140 U_comp_39 (.A(comp_38_CO), .B(pp_in_39), .CI(comp_19_S), .S(comp_39_S), .CO(comp_39_CO));
    FA1D0BWP12T40P140 U_comp_40 (.A(comp_39_CO), .B(pp_in_54), .CI(pp_in_47), .S(comp_40_S), .CO(comp_40_CO));
    FA1D0BWP12T40P140 U_comp_41 (.A(comp_40_CO), .B(comp_29_CO), .CI(pp_in_62), .S(comp_41_S), .CO(comp_41_CO));
endmodule
