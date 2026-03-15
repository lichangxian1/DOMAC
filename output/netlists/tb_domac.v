`timescale 1ns/1ps

// ================= TSMC Mock Behavioral Models =================
module FA1D2BWP12T40P140 (input A, B, CI, output S, CO);
    assign {CO, S} = A + B + CI;
endmodule
module FA1D0BWP12T40P140 (input A, B, CI, output S, CO);
    assign {CO, S} = A + B + CI;
endmodule
module FA1D1BWP12T40P140 (input A, B, CI, output S, CO);
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
    reg pp_in_0, pp_in_1, pp_in_2, pp_in_3, pp_in_4, pp_in_5, pp_in_6, pp_in_7, pp_in_8, pp_in_9, pp_in_10, pp_in_11, pp_in_12, pp_in_13, pp_in_14, pp_in_15, pp_in_16, pp_in_17, pp_in_18, pp_in_19, pp_in_20, pp_in_21, pp_in_22, pp_in_23, pp_in_24, pp_in_25, pp_in_26, pp_in_27, pp_in_28, pp_in_29, pp_in_30, pp_in_31, pp_in_32, pp_in_33, pp_in_34, pp_in_35, pp_in_36, pp_in_37, pp_in_38, pp_in_39, pp_in_40, pp_in_41, pp_in_42, pp_in_43, pp_in_44, pp_in_45, pp_in_46, pp_in_47, pp_in_48, pp_in_49, pp_in_50, pp_in_51, pp_in_52, pp_in_53, pp_in_54, pp_in_55, pp_in_56, pp_in_57, pp_in_58, pp_in_59, pp_in_60, pp_in_61, pp_in_62, pp_in_63, pp_in_64, pp_in_65, pp_in_66, pp_in_67, pp_in_68, pp_in_69, pp_in_70, pp_in_71, pp_in_72, pp_in_73, pp_in_74, pp_in_75, pp_in_76, pp_in_77, pp_in_78, pp_in_79, pp_in_80, pp_in_81, pp_in_82, pp_in_83, pp_in_84, pp_in_85, pp_in_86, pp_in_87, pp_in_88, pp_in_89, pp_in_90, pp_in_91, pp_in_92, pp_in_93, pp_in_94, pp_in_95, pp_in_96, pp_in_97, pp_in_98, pp_in_99, pp_in_100, pp_in_101, pp_in_102, pp_in_103, pp_in_104, pp_in_105, pp_in_106, pp_in_107, pp_in_108, pp_in_109, pp_in_110, pp_in_111, pp_in_112, pp_in_113, pp_in_114, pp_in_115, pp_in_116, pp_in_117, pp_in_118, pp_in_119, pp_in_120, pp_in_121, pp_in_122, pp_in_123, pp_in_124, pp_in_125, pp_in_126, pp_in_127, pp_in_128, pp_in_129, pp_in_130, pp_in_131, pp_in_132, pp_in_133, pp_in_134, pp_in_135, pp_in_136, pp_in_137, pp_in_138, pp_in_139, pp_in_140, pp_in_141, pp_in_142, pp_in_143, pp_in_144, pp_in_145, pp_in_146, pp_in_147, pp_in_148, pp_in_149, pp_in_150, pp_in_151, pp_in_152, pp_in_153, pp_in_154, pp_in_155, pp_in_156, pp_in_157, pp_in_158, pp_in_159, pp_in_160, pp_in_161, pp_in_162, pp_in_163, pp_in_164, pp_in_165, pp_in_166, pp_in_167, pp_in_168, pp_in_169, pp_in_170, pp_in_171, pp_in_172, pp_in_173, pp_in_174, pp_in_175, pp_in_176, pp_in_177, pp_in_178, pp_in_179, pp_in_180, pp_in_181, pp_in_182, pp_in_183, pp_in_184, pp_in_185, pp_in_186, pp_in_187, pp_in_188, pp_in_189, pp_in_190, pp_in_191, pp_in_192, pp_in_193, pp_in_194, pp_in_195, pp_in_196, pp_in_197, pp_in_198, pp_in_199, pp_in_200, pp_in_201, pp_in_202, pp_in_203, pp_in_204, pp_in_205, pp_in_206, pp_in_207, pp_in_208, pp_in_209, pp_in_210, pp_in_211, pp_in_212, pp_in_213, pp_in_214, pp_in_215, pp_in_216, pp_in_217, pp_in_218, pp_in_219, pp_in_220, pp_in_221, pp_in_222, pp_in_223, pp_in_224, pp_in_225, pp_in_226, pp_in_227, pp_in_228, pp_in_229, pp_in_230, pp_in_231, pp_in_232, pp_in_233, pp_in_234, pp_in_235, pp_in_236, pp_in_237, pp_in_238, pp_in_239, pp_in_240, pp_in_241, pp_in_242, pp_in_243, pp_in_244, pp_in_245, pp_in_246, pp_in_247, pp_in_248, pp_in_249, pp_in_250, pp_in_251, pp_in_252, pp_in_253, pp_in_254, pp_in_255;
    wire out_pp_0, out_pp_1, out_pp_2, out_pp_171, out_pp_185, out_pp_195, out_pp_206, out_pp_215, out_pp_224, out_pp_233, out_pp_255, comp_0_S, comp_2_S, comp_5_S, comp_9_S, comp_14_S, comp_20_S, comp_27_S, comp_35_S, comp_44_S, comp_54_S, comp_65_S, comp_77_S, comp_90_S, comp_104_S, comp_118_S, comp_131_S, comp_143_S, comp_154_S, comp_164_S, comp_173_S, comp_181_S, comp_188_S, comp_194_S, comp_199_S, comp_203_S, comp_206_S, comp_208_S, comp_209_S, comp_106_CO, comp_190_CO, comp_196_CO, comp_200_CO, comp_204_CO, comp_207_CO, comp_209_CO;

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
        .pp_in_64(pp_in_64),
        .pp_in_65(pp_in_65),
        .pp_in_66(pp_in_66),
        .pp_in_67(pp_in_67),
        .pp_in_68(pp_in_68),
        .pp_in_69(pp_in_69),
        .pp_in_70(pp_in_70),
        .pp_in_71(pp_in_71),
        .pp_in_72(pp_in_72),
        .pp_in_73(pp_in_73),
        .pp_in_74(pp_in_74),
        .pp_in_75(pp_in_75),
        .pp_in_76(pp_in_76),
        .pp_in_77(pp_in_77),
        .pp_in_78(pp_in_78),
        .pp_in_79(pp_in_79),
        .pp_in_80(pp_in_80),
        .pp_in_81(pp_in_81),
        .pp_in_82(pp_in_82),
        .pp_in_83(pp_in_83),
        .pp_in_84(pp_in_84),
        .pp_in_85(pp_in_85),
        .pp_in_86(pp_in_86),
        .pp_in_87(pp_in_87),
        .pp_in_88(pp_in_88),
        .pp_in_89(pp_in_89),
        .pp_in_90(pp_in_90),
        .pp_in_91(pp_in_91),
        .pp_in_92(pp_in_92),
        .pp_in_93(pp_in_93),
        .pp_in_94(pp_in_94),
        .pp_in_95(pp_in_95),
        .pp_in_96(pp_in_96),
        .pp_in_97(pp_in_97),
        .pp_in_98(pp_in_98),
        .pp_in_99(pp_in_99),
        .pp_in_100(pp_in_100),
        .pp_in_101(pp_in_101),
        .pp_in_102(pp_in_102),
        .pp_in_103(pp_in_103),
        .pp_in_104(pp_in_104),
        .pp_in_105(pp_in_105),
        .pp_in_106(pp_in_106),
        .pp_in_107(pp_in_107),
        .pp_in_108(pp_in_108),
        .pp_in_109(pp_in_109),
        .pp_in_110(pp_in_110),
        .pp_in_111(pp_in_111),
        .pp_in_112(pp_in_112),
        .pp_in_113(pp_in_113),
        .pp_in_114(pp_in_114),
        .pp_in_115(pp_in_115),
        .pp_in_116(pp_in_116),
        .pp_in_117(pp_in_117),
        .pp_in_118(pp_in_118),
        .pp_in_119(pp_in_119),
        .pp_in_120(pp_in_120),
        .pp_in_121(pp_in_121),
        .pp_in_122(pp_in_122),
        .pp_in_123(pp_in_123),
        .pp_in_124(pp_in_124),
        .pp_in_125(pp_in_125),
        .pp_in_126(pp_in_126),
        .pp_in_127(pp_in_127),
        .pp_in_128(pp_in_128),
        .pp_in_129(pp_in_129),
        .pp_in_130(pp_in_130),
        .pp_in_131(pp_in_131),
        .pp_in_132(pp_in_132),
        .pp_in_133(pp_in_133),
        .pp_in_134(pp_in_134),
        .pp_in_135(pp_in_135),
        .pp_in_136(pp_in_136),
        .pp_in_137(pp_in_137),
        .pp_in_138(pp_in_138),
        .pp_in_139(pp_in_139),
        .pp_in_140(pp_in_140),
        .pp_in_141(pp_in_141),
        .pp_in_142(pp_in_142),
        .pp_in_143(pp_in_143),
        .pp_in_144(pp_in_144),
        .pp_in_145(pp_in_145),
        .pp_in_146(pp_in_146),
        .pp_in_147(pp_in_147),
        .pp_in_148(pp_in_148),
        .pp_in_149(pp_in_149),
        .pp_in_150(pp_in_150),
        .pp_in_151(pp_in_151),
        .pp_in_152(pp_in_152),
        .pp_in_153(pp_in_153),
        .pp_in_154(pp_in_154),
        .pp_in_155(pp_in_155),
        .pp_in_156(pp_in_156),
        .pp_in_157(pp_in_157),
        .pp_in_158(pp_in_158),
        .pp_in_159(pp_in_159),
        .pp_in_160(pp_in_160),
        .pp_in_161(pp_in_161),
        .pp_in_162(pp_in_162),
        .pp_in_163(pp_in_163),
        .pp_in_164(pp_in_164),
        .pp_in_165(pp_in_165),
        .pp_in_166(pp_in_166),
        .pp_in_167(pp_in_167),
        .pp_in_168(pp_in_168),
        .pp_in_169(pp_in_169),
        .pp_in_170(pp_in_170),
        .pp_in_171(pp_in_171),
        .pp_in_172(pp_in_172),
        .pp_in_173(pp_in_173),
        .pp_in_174(pp_in_174),
        .pp_in_175(pp_in_175),
        .pp_in_176(pp_in_176),
        .pp_in_177(pp_in_177),
        .pp_in_178(pp_in_178),
        .pp_in_179(pp_in_179),
        .pp_in_180(pp_in_180),
        .pp_in_181(pp_in_181),
        .pp_in_182(pp_in_182),
        .pp_in_183(pp_in_183),
        .pp_in_184(pp_in_184),
        .pp_in_185(pp_in_185),
        .pp_in_186(pp_in_186),
        .pp_in_187(pp_in_187),
        .pp_in_188(pp_in_188),
        .pp_in_189(pp_in_189),
        .pp_in_190(pp_in_190),
        .pp_in_191(pp_in_191),
        .pp_in_192(pp_in_192),
        .pp_in_193(pp_in_193),
        .pp_in_194(pp_in_194),
        .pp_in_195(pp_in_195),
        .pp_in_196(pp_in_196),
        .pp_in_197(pp_in_197),
        .pp_in_198(pp_in_198),
        .pp_in_199(pp_in_199),
        .pp_in_200(pp_in_200),
        .pp_in_201(pp_in_201),
        .pp_in_202(pp_in_202),
        .pp_in_203(pp_in_203),
        .pp_in_204(pp_in_204),
        .pp_in_205(pp_in_205),
        .pp_in_206(pp_in_206),
        .pp_in_207(pp_in_207),
        .pp_in_208(pp_in_208),
        .pp_in_209(pp_in_209),
        .pp_in_210(pp_in_210),
        .pp_in_211(pp_in_211),
        .pp_in_212(pp_in_212),
        .pp_in_213(pp_in_213),
        .pp_in_214(pp_in_214),
        .pp_in_215(pp_in_215),
        .pp_in_216(pp_in_216),
        .pp_in_217(pp_in_217),
        .pp_in_218(pp_in_218),
        .pp_in_219(pp_in_219),
        .pp_in_220(pp_in_220),
        .pp_in_221(pp_in_221),
        .pp_in_222(pp_in_222),
        .pp_in_223(pp_in_223),
        .pp_in_224(pp_in_224),
        .pp_in_225(pp_in_225),
        .pp_in_226(pp_in_226),
        .pp_in_227(pp_in_227),
        .pp_in_228(pp_in_228),
        .pp_in_229(pp_in_229),
        .pp_in_230(pp_in_230),
        .pp_in_231(pp_in_231),
        .pp_in_232(pp_in_232),
        .pp_in_233(pp_in_233),
        .pp_in_234(pp_in_234),
        .pp_in_235(pp_in_235),
        .pp_in_236(pp_in_236),
        .pp_in_237(pp_in_237),
        .pp_in_238(pp_in_238),
        .pp_in_239(pp_in_239),
        .pp_in_240(pp_in_240),
        .pp_in_241(pp_in_241),
        .pp_in_242(pp_in_242),
        .pp_in_243(pp_in_243),
        .pp_in_244(pp_in_244),
        .pp_in_245(pp_in_245),
        .pp_in_246(pp_in_246),
        .pp_in_247(pp_in_247),
        .pp_in_248(pp_in_248),
        .pp_in_249(pp_in_249),
        .pp_in_250(pp_in_250),
        .pp_in_251(pp_in_251),
        .pp_in_252(pp_in_252),
        .pp_in_253(pp_in_253),
        .pp_in_254(pp_in_254),
        .pp_in_255(pp_in_255),
        .out_pp_0(out_pp_0),
        .out_pp_1(out_pp_1),
        .out_pp_2(out_pp_2),
        .out_pp_171(out_pp_171),
        .out_pp_185(out_pp_185),
        .out_pp_195(out_pp_195),
        .out_pp_206(out_pp_206),
        .out_pp_215(out_pp_215),
        .out_pp_224(out_pp_224),
        .out_pp_233(out_pp_233),
        .out_pp_255(out_pp_255),
        .comp_0_S(comp_0_S),
        .comp_2_S(comp_2_S),
        .comp_5_S(comp_5_S),
        .comp_9_S(comp_9_S),
        .comp_14_S(comp_14_S),
        .comp_20_S(comp_20_S),
        .comp_27_S(comp_27_S),
        .comp_35_S(comp_35_S),
        .comp_44_S(comp_44_S),
        .comp_54_S(comp_54_S),
        .comp_65_S(comp_65_S),
        .comp_77_S(comp_77_S),
        .comp_90_S(comp_90_S),
        .comp_104_S(comp_104_S),
        .comp_118_S(comp_118_S),
        .comp_131_S(comp_131_S),
        .comp_143_S(comp_143_S),
        .comp_154_S(comp_154_S),
        .comp_164_S(comp_164_S),
        .comp_173_S(comp_173_S),
        .comp_181_S(comp_181_S),
        .comp_188_S(comp_188_S),
        .comp_194_S(comp_194_S),
        .comp_199_S(comp_199_S),
        .comp_203_S(comp_203_S),
        .comp_206_S(comp_206_S),
        .comp_208_S(comp_208_S),
        .comp_209_S(comp_209_S),
        .comp_106_CO(comp_106_CO),
        .comp_190_CO(comp_190_CO),
        .comp_196_CO(comp_196_CO),
        .comp_200_CO(comp_200_CO),
        .comp_204_CO(comp_204_CO),
        .comp_207_CO(comp_207_CO),
        .comp_209_CO(comp_209_CO)
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
            pp_in_64 = $random % 2;
            pp_in_65 = $random % 2;
            pp_in_66 = $random % 2;
            pp_in_67 = $random % 2;
            pp_in_68 = $random % 2;
            pp_in_69 = $random % 2;
            pp_in_70 = $random % 2;
            pp_in_71 = $random % 2;
            pp_in_72 = $random % 2;
            pp_in_73 = $random % 2;
            pp_in_74 = $random % 2;
            pp_in_75 = $random % 2;
            pp_in_76 = $random % 2;
            pp_in_77 = $random % 2;
            pp_in_78 = $random % 2;
            pp_in_79 = $random % 2;
            pp_in_80 = $random % 2;
            pp_in_81 = $random % 2;
            pp_in_82 = $random % 2;
            pp_in_83 = $random % 2;
            pp_in_84 = $random % 2;
            pp_in_85 = $random % 2;
            pp_in_86 = $random % 2;
            pp_in_87 = $random % 2;
            pp_in_88 = $random % 2;
            pp_in_89 = $random % 2;
            pp_in_90 = $random % 2;
            pp_in_91 = $random % 2;
            pp_in_92 = $random % 2;
            pp_in_93 = $random % 2;
            pp_in_94 = $random % 2;
            pp_in_95 = $random % 2;
            pp_in_96 = $random % 2;
            pp_in_97 = $random % 2;
            pp_in_98 = $random % 2;
            pp_in_99 = $random % 2;
            pp_in_100 = $random % 2;
            pp_in_101 = $random % 2;
            pp_in_102 = $random % 2;
            pp_in_103 = $random % 2;
            pp_in_104 = $random % 2;
            pp_in_105 = $random % 2;
            pp_in_106 = $random % 2;
            pp_in_107 = $random % 2;
            pp_in_108 = $random % 2;
            pp_in_109 = $random % 2;
            pp_in_110 = $random % 2;
            pp_in_111 = $random % 2;
            pp_in_112 = $random % 2;
            pp_in_113 = $random % 2;
            pp_in_114 = $random % 2;
            pp_in_115 = $random % 2;
            pp_in_116 = $random % 2;
            pp_in_117 = $random % 2;
            pp_in_118 = $random % 2;
            pp_in_119 = $random % 2;
            pp_in_120 = $random % 2;
            pp_in_121 = $random % 2;
            pp_in_122 = $random % 2;
            pp_in_123 = $random % 2;
            pp_in_124 = $random % 2;
            pp_in_125 = $random % 2;
            pp_in_126 = $random % 2;
            pp_in_127 = $random % 2;
            pp_in_128 = $random % 2;
            pp_in_129 = $random % 2;
            pp_in_130 = $random % 2;
            pp_in_131 = $random % 2;
            pp_in_132 = $random % 2;
            pp_in_133 = $random % 2;
            pp_in_134 = $random % 2;
            pp_in_135 = $random % 2;
            pp_in_136 = $random % 2;
            pp_in_137 = $random % 2;
            pp_in_138 = $random % 2;
            pp_in_139 = $random % 2;
            pp_in_140 = $random % 2;
            pp_in_141 = $random % 2;
            pp_in_142 = $random % 2;
            pp_in_143 = $random % 2;
            pp_in_144 = $random % 2;
            pp_in_145 = $random % 2;
            pp_in_146 = $random % 2;
            pp_in_147 = $random % 2;
            pp_in_148 = $random % 2;
            pp_in_149 = $random % 2;
            pp_in_150 = $random % 2;
            pp_in_151 = $random % 2;
            pp_in_152 = $random % 2;
            pp_in_153 = $random % 2;
            pp_in_154 = $random % 2;
            pp_in_155 = $random % 2;
            pp_in_156 = $random % 2;
            pp_in_157 = $random % 2;
            pp_in_158 = $random % 2;
            pp_in_159 = $random % 2;
            pp_in_160 = $random % 2;
            pp_in_161 = $random % 2;
            pp_in_162 = $random % 2;
            pp_in_163 = $random % 2;
            pp_in_164 = $random % 2;
            pp_in_165 = $random % 2;
            pp_in_166 = $random % 2;
            pp_in_167 = $random % 2;
            pp_in_168 = $random % 2;
            pp_in_169 = $random % 2;
            pp_in_170 = $random % 2;
            pp_in_171 = $random % 2;
            pp_in_172 = $random % 2;
            pp_in_173 = $random % 2;
            pp_in_174 = $random % 2;
            pp_in_175 = $random % 2;
            pp_in_176 = $random % 2;
            pp_in_177 = $random % 2;
            pp_in_178 = $random % 2;
            pp_in_179 = $random % 2;
            pp_in_180 = $random % 2;
            pp_in_181 = $random % 2;
            pp_in_182 = $random % 2;
            pp_in_183 = $random % 2;
            pp_in_184 = $random % 2;
            pp_in_185 = $random % 2;
            pp_in_186 = $random % 2;
            pp_in_187 = $random % 2;
            pp_in_188 = $random % 2;
            pp_in_189 = $random % 2;
            pp_in_190 = $random % 2;
            pp_in_191 = $random % 2;
            pp_in_192 = $random % 2;
            pp_in_193 = $random % 2;
            pp_in_194 = $random % 2;
            pp_in_195 = $random % 2;
            pp_in_196 = $random % 2;
            pp_in_197 = $random % 2;
            pp_in_198 = $random % 2;
            pp_in_199 = $random % 2;
            pp_in_200 = $random % 2;
            pp_in_201 = $random % 2;
            pp_in_202 = $random % 2;
            pp_in_203 = $random % 2;
            pp_in_204 = $random % 2;
            pp_in_205 = $random % 2;
            pp_in_206 = $random % 2;
            pp_in_207 = $random % 2;
            pp_in_208 = $random % 2;
            pp_in_209 = $random % 2;
            pp_in_210 = $random % 2;
            pp_in_211 = $random % 2;
            pp_in_212 = $random % 2;
            pp_in_213 = $random % 2;
            pp_in_214 = $random % 2;
            pp_in_215 = $random % 2;
            pp_in_216 = $random % 2;
            pp_in_217 = $random % 2;
            pp_in_218 = $random % 2;
            pp_in_219 = $random % 2;
            pp_in_220 = $random % 2;
            pp_in_221 = $random % 2;
            pp_in_222 = $random % 2;
            pp_in_223 = $random % 2;
            pp_in_224 = $random % 2;
            pp_in_225 = $random % 2;
            pp_in_226 = $random % 2;
            pp_in_227 = $random % 2;
            pp_in_228 = $random % 2;
            pp_in_229 = $random % 2;
            pp_in_230 = $random % 2;
            pp_in_231 = $random % 2;
            pp_in_232 = $random % 2;
            pp_in_233 = $random % 2;
            pp_in_234 = $random % 2;
            pp_in_235 = $random % 2;
            pp_in_236 = $random % 2;
            pp_in_237 = $random % 2;
            pp_in_238 = $random % 2;
            pp_in_239 = $random % 2;
            pp_in_240 = $random % 2;
            pp_in_241 = $random % 2;
            pp_in_242 = $random % 2;
            pp_in_243 = $random % 2;
            pp_in_244 = $random % 2;
            pp_in_245 = $random % 2;
            pp_in_246 = $random % 2;
            pp_in_247 = $random % 2;
            pp_in_248 = $random % 2;
            pp_in_249 = $random % 2;
            pp_in_250 = $random % 2;
            pp_in_251 = $random % 2;
            pp_in_252 = $random % 2;
            pp_in_253 = $random % 2;
            pp_in_254 = $random % 2;
            pp_in_255 = $random % 2;
            #5; // 模拟信号穿过组合逻辑的延迟

            expected_weight = 0 + (pp_in_0 * (64'h1 << 0)) + (pp_in_1 * (64'h1 << 1)) + (pp_in_2 * (64'h1 << 1)) + (pp_in_3 * (64'h1 << 2)) + (pp_in_4 * (64'h1 << 2)) + (pp_in_5 * (64'h1 << 2)) + (pp_in_6 * (64'h1 << 3)) + (pp_in_7 * (64'h1 << 3)) + (pp_in_8 * (64'h1 << 3)) + (pp_in_9 * (64'h1 << 3)) + (pp_in_10 * (64'h1 << 4)) + (pp_in_11 * (64'h1 << 4)) + (pp_in_12 * (64'h1 << 4)) + (pp_in_13 * (64'h1 << 4)) + (pp_in_14 * (64'h1 << 4)) + (pp_in_15 * (64'h1 << 5)) + (pp_in_16 * (64'h1 << 5)) + (pp_in_17 * (64'h1 << 5)) + (pp_in_18 * (64'h1 << 5)) + (pp_in_19 * (64'h1 << 5)) + (pp_in_20 * (64'h1 << 5)) + (pp_in_21 * (64'h1 << 6)) + (pp_in_22 * (64'h1 << 6)) + (pp_in_23 * (64'h1 << 6)) + (pp_in_24 * (64'h1 << 6)) + (pp_in_25 * (64'h1 << 6)) + (pp_in_26 * (64'h1 << 6)) + (pp_in_27 * (64'h1 << 6)) + (pp_in_28 * (64'h1 << 7)) + (pp_in_29 * (64'h1 << 7)) + (pp_in_30 * (64'h1 << 7)) + (pp_in_31 * (64'h1 << 7)) + (pp_in_32 * (64'h1 << 7)) + (pp_in_33 * (64'h1 << 7)) + (pp_in_34 * (64'h1 << 7)) + (pp_in_35 * (64'h1 << 7)) + (pp_in_36 * (64'h1 << 8)) + (pp_in_37 * (64'h1 << 8)) + (pp_in_38 * (64'h1 << 8)) + (pp_in_39 * (64'h1 << 8)) + (pp_in_40 * (64'h1 << 8)) + (pp_in_41 * (64'h1 << 8)) + (pp_in_42 * (64'h1 << 8)) + (pp_in_43 * (64'h1 << 8)) + (pp_in_44 * (64'h1 << 8)) + (pp_in_45 * (64'h1 << 9)) + (pp_in_46 * (64'h1 << 9)) + (pp_in_47 * (64'h1 << 9)) + (pp_in_48 * (64'h1 << 9)) + (pp_in_49 * (64'h1 << 9)) + (pp_in_50 * (64'h1 << 9)) + (pp_in_51 * (64'h1 << 9)) + (pp_in_52 * (64'h1 << 9)) + (pp_in_53 * (64'h1 << 9)) + (pp_in_54 * (64'h1 << 9)) + (pp_in_55 * (64'h1 << 10)) + (pp_in_56 * (64'h1 << 10)) + (pp_in_57 * (64'h1 << 10)) + (pp_in_58 * (64'h1 << 10)) + (pp_in_59 * (64'h1 << 10)) + (pp_in_60 * (64'h1 << 10)) + (pp_in_61 * (64'h1 << 10)) + (pp_in_62 * (64'h1 << 10)) + (pp_in_63 * (64'h1 << 10)) + (pp_in_64 * (64'h1 << 10)) + (pp_in_65 * (64'h1 << 10)) + (pp_in_66 * (64'h1 << 11)) + (pp_in_67 * (64'h1 << 11)) + (pp_in_68 * (64'h1 << 11)) + (pp_in_69 * (64'h1 << 11)) + (pp_in_70 * (64'h1 << 11)) + (pp_in_71 * (64'h1 << 11)) + (pp_in_72 * (64'h1 << 11)) + (pp_in_73 * (64'h1 << 11)) + (pp_in_74 * (64'h1 << 11)) + (pp_in_75 * (64'h1 << 11)) + (pp_in_76 * (64'h1 << 11)) + (pp_in_77 * (64'h1 << 11)) + (pp_in_78 * (64'h1 << 12)) + (pp_in_79 * (64'h1 << 12)) + (pp_in_80 * (64'h1 << 12)) + (pp_in_81 * (64'h1 << 12)) + (pp_in_82 * (64'h1 << 12)) + (pp_in_83 * (64'h1 << 12)) + (pp_in_84 * (64'h1 << 12)) + (pp_in_85 * (64'h1 << 12)) + (pp_in_86 * (64'h1 << 12)) + (pp_in_87 * (64'h1 << 12)) + (pp_in_88 * (64'h1 << 12)) + (pp_in_89 * (64'h1 << 12)) + (pp_in_90 * (64'h1 << 12)) + (pp_in_91 * (64'h1 << 13)) + (pp_in_92 * (64'h1 << 13)) + (pp_in_93 * (64'h1 << 13)) + (pp_in_94 * (64'h1 << 13)) + (pp_in_95 * (64'h1 << 13)) + (pp_in_96 * (64'h1 << 13)) + (pp_in_97 * (64'h1 << 13)) + (pp_in_98 * (64'h1 << 13)) + (pp_in_99 * (64'h1 << 13)) + (pp_in_100 * (64'h1 << 13)) + (pp_in_101 * (64'h1 << 13)) + (pp_in_102 * (64'h1 << 13)) + (pp_in_103 * (64'h1 << 13)) + (pp_in_104 * (64'h1 << 13)) + (pp_in_105 * (64'h1 << 14)) + (pp_in_106 * (64'h1 << 14)) + (pp_in_107 * (64'h1 << 14)) + (pp_in_108 * (64'h1 << 14)) + (pp_in_109 * (64'h1 << 14)) + (pp_in_110 * (64'h1 << 14)) + (pp_in_111 * (64'h1 << 14)) + (pp_in_112 * (64'h1 << 14)) + (pp_in_113 * (64'h1 << 14)) + (pp_in_114 * (64'h1 << 14)) + (pp_in_115 * (64'h1 << 14)) + (pp_in_116 * (64'h1 << 14)) + (pp_in_117 * (64'h1 << 14)) + (pp_in_118 * (64'h1 << 14)) + (pp_in_119 * (64'h1 << 14)) + (pp_in_120 * (64'h1 << 15)) + (pp_in_121 * (64'h1 << 15)) + (pp_in_122 * (64'h1 << 15)) + (pp_in_123 * (64'h1 << 15)) + (pp_in_124 * (64'h1 << 15)) + (pp_in_125 * (64'h1 << 15)) + (pp_in_126 * (64'h1 << 15)) + (pp_in_127 * (64'h1 << 15)) + (pp_in_128 * (64'h1 << 15)) + (pp_in_129 * (64'h1 << 15)) + (pp_in_130 * (64'h1 << 15)) + (pp_in_131 * (64'h1 << 15)) + (pp_in_132 * (64'h1 << 15)) + (pp_in_133 * (64'h1 << 15)) + (pp_in_134 * (64'h1 << 15)) + (pp_in_135 * (64'h1 << 15)) + (pp_in_136 * (64'h1 << 16)) + (pp_in_137 * (64'h1 << 16)) + (pp_in_138 * (64'h1 << 16)) + (pp_in_139 * (64'h1 << 16)) + (pp_in_140 * (64'h1 << 16)) + (pp_in_141 * (64'h1 << 16)) + (pp_in_142 * (64'h1 << 16)) + (pp_in_143 * (64'h1 << 16)) + (pp_in_144 * (64'h1 << 16)) + (pp_in_145 * (64'h1 << 16)) + (pp_in_146 * (64'h1 << 16)) + (pp_in_147 * (64'h1 << 16)) + (pp_in_148 * (64'h1 << 16)) + (pp_in_149 * (64'h1 << 16)) + (pp_in_150 * (64'h1 << 16)) + (pp_in_151 * (64'h1 << 17)) + (pp_in_152 * (64'h1 << 17)) + (pp_in_153 * (64'h1 << 17)) + (pp_in_154 * (64'h1 << 17)) + (pp_in_155 * (64'h1 << 17)) + (pp_in_156 * (64'h1 << 17)) + (pp_in_157 * (64'h1 << 17)) + (pp_in_158 * (64'h1 << 17)) + (pp_in_159 * (64'h1 << 17)) + (pp_in_160 * (64'h1 << 17)) + (pp_in_161 * (64'h1 << 17)) + (pp_in_162 * (64'h1 << 17)) + (pp_in_163 * (64'h1 << 17)) + (pp_in_164 * (64'h1 << 17)) + (pp_in_165 * (64'h1 << 18)) + (pp_in_166 * (64'h1 << 18)) + (pp_in_167 * (64'h1 << 18)) + (pp_in_168 * (64'h1 << 18)) + (pp_in_169 * (64'h1 << 18)) + (pp_in_170 * (64'h1 << 18)) + (pp_in_171 * (64'h1 << 18)) + (pp_in_172 * (64'h1 << 18)) + (pp_in_173 * (64'h1 << 18)) + (pp_in_174 * (64'h1 << 18)) + (pp_in_175 * (64'h1 << 18)) + (pp_in_176 * (64'h1 << 18)) + (pp_in_177 * (64'h1 << 18)) + (pp_in_178 * (64'h1 << 19)) + (pp_in_179 * (64'h1 << 19)) + (pp_in_180 * (64'h1 << 19)) + (pp_in_181 * (64'h1 << 19)) + (pp_in_182 * (64'h1 << 19)) + (pp_in_183 * (64'h1 << 19)) + (pp_in_184 * (64'h1 << 19)) + (pp_in_185 * (64'h1 << 19)) + (pp_in_186 * (64'h1 << 19)) + (pp_in_187 * (64'h1 << 19)) + (pp_in_188 * (64'h1 << 19)) + (pp_in_189 * (64'h1 << 19)) + (pp_in_190 * (64'h1 << 20)) + (pp_in_191 * (64'h1 << 20)) + (pp_in_192 * (64'h1 << 20)) + (pp_in_193 * (64'h1 << 20)) + (pp_in_194 * (64'h1 << 20)) + (pp_in_195 * (64'h1 << 20)) + (pp_in_196 * (64'h1 << 20)) + (pp_in_197 * (64'h1 << 20)) + (pp_in_198 * (64'h1 << 20)) + (pp_in_199 * (64'h1 << 20)) + (pp_in_200 * (64'h1 << 20)) + (pp_in_201 * (64'h1 << 21)) + (pp_in_202 * (64'h1 << 21)) + (pp_in_203 * (64'h1 << 21)) + (pp_in_204 * (64'h1 << 21)) + (pp_in_205 * (64'h1 << 21)) + (pp_in_206 * (64'h1 << 21)) + (pp_in_207 * (64'h1 << 21)) + (pp_in_208 * (64'h1 << 21)) + (pp_in_209 * (64'h1 << 21)) + (pp_in_210 * (64'h1 << 21)) + (pp_in_211 * (64'h1 << 22)) + (pp_in_212 * (64'h1 << 22)) + (pp_in_213 * (64'h1 << 22)) + (pp_in_214 * (64'h1 << 22)) + (pp_in_215 * (64'h1 << 22)) + (pp_in_216 * (64'h1 << 22)) + (pp_in_217 * (64'h1 << 22)) + (pp_in_218 * (64'h1 << 22)) + (pp_in_219 * (64'h1 << 22)) + (pp_in_220 * (64'h1 << 23)) + (pp_in_221 * (64'h1 << 23)) + (pp_in_222 * (64'h1 << 23)) + (pp_in_223 * (64'h1 << 23)) + (pp_in_224 * (64'h1 << 23)) + (pp_in_225 * (64'h1 << 23)) + (pp_in_226 * (64'h1 << 23)) + (pp_in_227 * (64'h1 << 23)) + (pp_in_228 * (64'h1 << 24)) + (pp_in_229 * (64'h1 << 24)) + (pp_in_230 * (64'h1 << 24)) + (pp_in_231 * (64'h1 << 24)) + (pp_in_232 * (64'h1 << 24)) + (pp_in_233 * (64'h1 << 24)) + (pp_in_234 * (64'h1 << 24)) + (pp_in_235 * (64'h1 << 25)) + (pp_in_236 * (64'h1 << 25)) + (pp_in_237 * (64'h1 << 25)) + (pp_in_238 * (64'h1 << 25)) + (pp_in_239 * (64'h1 << 25)) + (pp_in_240 * (64'h1 << 25)) + (pp_in_241 * (64'h1 << 26)) + (pp_in_242 * (64'h1 << 26)) + (pp_in_243 * (64'h1 << 26)) + (pp_in_244 * (64'h1 << 26)) + (pp_in_245 * (64'h1 << 26)) + (pp_in_246 * (64'h1 << 27)) + (pp_in_247 * (64'h1 << 27)) + (pp_in_248 * (64'h1 << 27)) + (pp_in_249 * (64'h1 << 27)) + (pp_in_250 * (64'h1 << 28)) + (pp_in_251 * (64'h1 << 28)) + (pp_in_252 * (64'h1 << 28)) + (pp_in_253 * (64'h1 << 29)) + (pp_in_254 * (64'h1 << 29)) + (pp_in_255 * (64'h1 << 30));
            actual_weight = 0 + (out_pp_0 * (64'h1 << 0)) + (out_pp_1 * (64'h1 << 1)) + (out_pp_2 * (64'h1 << 1)) + (out_pp_171 * (64'h1 << 18)) + (out_pp_185 * (64'h1 << 19)) + (out_pp_195 * (64'h1 << 20)) + (out_pp_206 * (64'h1 << 21)) + (out_pp_215 * (64'h1 << 22)) + (out_pp_224 * (64'h1 << 23)) + (out_pp_233 * (64'h1 << 24)) + (out_pp_255 * (64'h1 << 30)) + (comp_0_S * (64'h1 << 2)) + (comp_2_S * (64'h1 << 3)) + (comp_5_S * (64'h1 << 4)) + (comp_9_S * (64'h1 << 5)) + (comp_14_S * (64'h1 << 6)) + (comp_20_S * (64'h1 << 7)) + (comp_27_S * (64'h1 << 8)) + (comp_35_S * (64'h1 << 9)) + (comp_44_S * (64'h1 << 10)) + (comp_54_S * (64'h1 << 11)) + (comp_65_S * (64'h1 << 12)) + (comp_77_S * (64'h1 << 13)) + (comp_90_S * (64'h1 << 14)) + (comp_104_S * (64'h1 << 15)) + (comp_118_S * (64'h1 << 16)) + (comp_131_S * (64'h1 << 17)) + (comp_143_S * (64'h1 << 18)) + (comp_154_S * (64'h1 << 19)) + (comp_164_S * (64'h1 << 20)) + (comp_173_S * (64'h1 << 21)) + (comp_181_S * (64'h1 << 22)) + (comp_188_S * (64'h1 << 23)) + (comp_194_S * (64'h1 << 24)) + (comp_199_S * (64'h1 << 25)) + (comp_203_S * (64'h1 << 26)) + (comp_206_S * (64'h1 << 27)) + (comp_208_S * (64'h1 << 28)) + (comp_209_S * (64'h1 << 29)) + (comp_106_CO * (64'h1 << 17)) + (comp_190_CO * (64'h1 << 25)) + (comp_196_CO * (64'h1 << 26)) + (comp_200_CO * (64'h1 << 27)) + (comp_204_CO * (64'h1 << 28)) + (comp_207_CO * (64'h1 << 29)) + (comp_209_CO * (64'h1 << 30));

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
