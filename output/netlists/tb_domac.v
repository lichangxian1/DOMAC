`timescale 1ns/1ps

// ================= TSMC Mock Behavioral Models =================
module FA1D0BWP12T40P140 (input A, B, CI, output S, CO);
    assign {CO, S} = A + B + CI;
endmodule
module FA1D1BWP12T40P140 (input A, B, CI, output S, CO);
    assign {CO, S} = A + B + CI;
endmodule
module FA1D2BWP12T40P140 (input A, B, CI, output S, CO);
    assign {CO, S} = A + B + CI;
endmodule
module FA1D4BWP12T40P140 (input A, B, CI, output S, CO);
    assign {CO, S} = A + B + CI;
endmodule
module HA1D1BWP12T40P140 (input A, B, output S, CO);
    assign {CO, S} = A + B;
endmodule

module HA1D2BWP12T40P140 (input A, B, output S, CO);
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
    wire out_pp_0, out_pp_1, out_pp_2, out_pp_236, out_pp_244, out_pp_248, out_pp_250, out_pp_253, out_pp_255, comp_0_S, comp_2_S, comp_5_S, comp_9_S, comp_14_S, comp_20_S, comp_27_S, comp_35_S, comp_44_S, comp_54_S, comp_65_S, comp_77_S, comp_90_S, comp_104_S, comp_118_S, comp_131_S, comp_143_S, comp_154_S, comp_164_S, comp_173_S, comp_181_S, comp_188_S, comp_194_S, comp_199_S, comp_203_S, comp_206_S, comp_208_S, comp_209_S, comp_107_CO, comp_121_CO, comp_134_CO, comp_144_CO, comp_157_CO, comp_167_CO, comp_175_CO, comp_182_CO, comp_209_CO;

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
        .out_pp_236(out_pp_236),
        .out_pp_244(out_pp_244),
        .out_pp_248(out_pp_248),
        .out_pp_250(out_pp_250),
        .out_pp_253(out_pp_253),
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
        .comp_107_CO(comp_107_CO),
        .comp_121_CO(comp_121_CO),
        .comp_134_CO(comp_134_CO),
        .comp_144_CO(comp_144_CO),
        .comp_157_CO(comp_157_CO),
        .comp_167_CO(comp_167_CO),
        .comp_175_CO(comp_175_CO),
        .comp_182_CO(comp_182_CO),
        .comp_209_CO(comp_209_CO)
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
            #5; // 等待组合逻辑稳定

            expected_weight = 0 + (pp_in_0 * (1 << 0)) + (pp_in_1 * (1 << 1)) + (pp_in_2 * (1 << 1)) + (pp_in_3 * (1 << 2)) + (pp_in_4 * (1 << 2)) + (pp_in_5 * (1 << 2)) + (pp_in_6 * (1 << 3)) + (pp_in_7 * (1 << 3)) + (pp_in_8 * (1 << 3)) + (pp_in_9 * (1 << 3)) + (pp_in_10 * (1 << 4)) + (pp_in_11 * (1 << 4)) + (pp_in_12 * (1 << 4)) + (pp_in_13 * (1 << 4)) + (pp_in_14 * (1 << 4)) + (pp_in_15 * (1 << 5)) + (pp_in_16 * (1 << 5)) + (pp_in_17 * (1 << 5)) + (pp_in_18 * (1 << 5)) + (pp_in_19 * (1 << 5)) + (pp_in_20 * (1 << 5)) + (pp_in_21 * (1 << 6)) + (pp_in_22 * (1 << 6)) + (pp_in_23 * (1 << 6)) + (pp_in_24 * (1 << 6)) + (pp_in_25 * (1 << 6)) + (pp_in_26 * (1 << 6)) + (pp_in_27 * (1 << 6)) + (pp_in_28 * (1 << 7)) + (pp_in_29 * (1 << 7)) + (pp_in_30 * (1 << 7)) + (pp_in_31 * (1 << 7)) + (pp_in_32 * (1 << 7)) + (pp_in_33 * (1 << 7)) + (pp_in_34 * (1 << 7)) + (pp_in_35 * (1 << 7)) + (pp_in_36 * (1 << 8)) + (pp_in_37 * (1 << 8)) + (pp_in_38 * (1 << 8)) + (pp_in_39 * (1 << 8)) + (pp_in_40 * (1 << 8)) + (pp_in_41 * (1 << 8)) + (pp_in_42 * (1 << 8)) + (pp_in_43 * (1 << 8)) + (pp_in_44 * (1 << 8)) + (pp_in_45 * (1 << 9)) + (pp_in_46 * (1 << 9)) + (pp_in_47 * (1 << 9)) + (pp_in_48 * (1 << 9)) + (pp_in_49 * (1 << 9)) + (pp_in_50 * (1 << 9)) + (pp_in_51 * (1 << 9)) + (pp_in_52 * (1 << 9)) + (pp_in_53 * (1 << 9)) + (pp_in_54 * (1 << 9)) + (pp_in_55 * (1 << 10)) + (pp_in_56 * (1 << 10)) + (pp_in_57 * (1 << 10)) + (pp_in_58 * (1 << 10)) + (pp_in_59 * (1 << 10)) + (pp_in_60 * (1 << 10)) + (pp_in_61 * (1 << 10)) + (pp_in_62 * (1 << 10)) + (pp_in_63 * (1 << 10)) + (pp_in_64 * (1 << 10)) + (pp_in_65 * (1 << 10)) + (pp_in_66 * (1 << 11)) + (pp_in_67 * (1 << 11)) + (pp_in_68 * (1 << 11)) + (pp_in_69 * (1 << 11)) + (pp_in_70 * (1 << 11)) + (pp_in_71 * (1 << 11)) + (pp_in_72 * (1 << 11)) + (pp_in_73 * (1 << 11)) + (pp_in_74 * (1 << 11)) + (pp_in_75 * (1 << 11)) + (pp_in_76 * (1 << 11)) + (pp_in_77 * (1 << 11)) + (pp_in_78 * (1 << 12)) + (pp_in_79 * (1 << 12)) + (pp_in_80 * (1 << 12)) + (pp_in_81 * (1 << 12)) + (pp_in_82 * (1 << 12)) + (pp_in_83 * (1 << 12)) + (pp_in_84 * (1 << 12)) + (pp_in_85 * (1 << 12)) + (pp_in_86 * (1 << 12)) + (pp_in_87 * (1 << 12)) + (pp_in_88 * (1 << 12)) + (pp_in_89 * (1 << 12)) + (pp_in_90 * (1 << 12)) + (pp_in_91 * (1 << 13)) + (pp_in_92 * (1 << 13)) + (pp_in_93 * (1 << 13)) + (pp_in_94 * (1 << 13)) + (pp_in_95 * (1 << 13)) + (pp_in_96 * (1 << 13)) + (pp_in_97 * (1 << 13)) + (pp_in_98 * (1 << 13)) + (pp_in_99 * (1 << 13)) + (pp_in_100 * (1 << 13)) + (pp_in_101 * (1 << 13)) + (pp_in_102 * (1 << 13)) + (pp_in_103 * (1 << 13)) + (pp_in_104 * (1 << 13)) + (pp_in_105 * (1 << 14)) + (pp_in_106 * (1 << 14)) + (pp_in_107 * (1 << 14)) + (pp_in_108 * (1 << 14)) + (pp_in_109 * (1 << 14)) + (pp_in_110 * (1 << 14)) + (pp_in_111 * (1 << 14)) + (pp_in_112 * (1 << 14)) + (pp_in_113 * (1 << 14)) + (pp_in_114 * (1 << 14)) + (pp_in_115 * (1 << 14)) + (pp_in_116 * (1 << 14)) + (pp_in_117 * (1 << 14)) + (pp_in_118 * (1 << 14)) + (pp_in_119 * (1 << 14)) + (pp_in_120 * (1 << 15)) + (pp_in_121 * (1 << 15)) + (pp_in_122 * (1 << 15)) + (pp_in_123 * (1 << 15)) + (pp_in_124 * (1 << 15)) + (pp_in_125 * (1 << 15)) + (pp_in_126 * (1 << 15)) + (pp_in_127 * (1 << 15)) + (pp_in_128 * (1 << 15)) + (pp_in_129 * (1 << 15)) + (pp_in_130 * (1 << 15)) + (pp_in_131 * (1 << 15)) + (pp_in_132 * (1 << 15)) + (pp_in_133 * (1 << 15)) + (pp_in_134 * (1 << 15)) + (pp_in_135 * (1 << 15)) + (pp_in_136 * (1 << 16)) + (pp_in_137 * (1 << 16)) + (pp_in_138 * (1 << 16)) + (pp_in_139 * (1 << 16)) + (pp_in_140 * (1 << 16)) + (pp_in_141 * (1 << 16)) + (pp_in_142 * (1 << 16)) + (pp_in_143 * (1 << 16)) + (pp_in_144 * (1 << 16)) + (pp_in_145 * (1 << 16)) + (pp_in_146 * (1 << 16)) + (pp_in_147 * (1 << 16)) + (pp_in_148 * (1 << 16)) + (pp_in_149 * (1 << 16)) + (pp_in_150 * (1 << 16)) + (pp_in_151 * (1 << 17)) + (pp_in_152 * (1 << 17)) + (pp_in_153 * (1 << 17)) + (pp_in_154 * (1 << 17)) + (pp_in_155 * (1 << 17)) + (pp_in_156 * (1 << 17)) + (pp_in_157 * (1 << 17)) + (pp_in_158 * (1 << 17)) + (pp_in_159 * (1 << 17)) + (pp_in_160 * (1 << 17)) + (pp_in_161 * (1 << 17)) + (pp_in_162 * (1 << 17)) + (pp_in_163 * (1 << 17)) + (pp_in_164 * (1 << 17)) + (pp_in_165 * (1 << 18)) + (pp_in_166 * (1 << 18)) + (pp_in_167 * (1 << 18)) + (pp_in_168 * (1 << 18)) + (pp_in_169 * (1 << 18)) + (pp_in_170 * (1 << 18)) + (pp_in_171 * (1 << 18)) + (pp_in_172 * (1 << 18)) + (pp_in_173 * (1 << 18)) + (pp_in_174 * (1 << 18)) + (pp_in_175 * (1 << 18)) + (pp_in_176 * (1 << 18)) + (pp_in_177 * (1 << 18)) + (pp_in_178 * (1 << 19)) + (pp_in_179 * (1 << 19)) + (pp_in_180 * (1 << 19)) + (pp_in_181 * (1 << 19)) + (pp_in_182 * (1 << 19)) + (pp_in_183 * (1 << 19)) + (pp_in_184 * (1 << 19)) + (pp_in_185 * (1 << 19)) + (pp_in_186 * (1 << 19)) + (pp_in_187 * (1 << 19)) + (pp_in_188 * (1 << 19)) + (pp_in_189 * (1 << 19)) + (pp_in_190 * (1 << 20)) + (pp_in_191 * (1 << 20)) + (pp_in_192 * (1 << 20)) + (pp_in_193 * (1 << 20)) + (pp_in_194 * (1 << 20)) + (pp_in_195 * (1 << 20)) + (pp_in_196 * (1 << 20)) + (pp_in_197 * (1 << 20)) + (pp_in_198 * (1 << 20)) + (pp_in_199 * (1 << 20)) + (pp_in_200 * (1 << 20)) + (pp_in_201 * (1 << 21)) + (pp_in_202 * (1 << 21)) + (pp_in_203 * (1 << 21)) + (pp_in_204 * (1 << 21)) + (pp_in_205 * (1 << 21)) + (pp_in_206 * (1 << 21)) + (pp_in_207 * (1 << 21)) + (pp_in_208 * (1 << 21)) + (pp_in_209 * (1 << 21)) + (pp_in_210 * (1 << 21)) + (pp_in_211 * (1 << 22)) + (pp_in_212 * (1 << 22)) + (pp_in_213 * (1 << 22)) + (pp_in_214 * (1 << 22)) + (pp_in_215 * (1 << 22)) + (pp_in_216 * (1 << 22)) + (pp_in_217 * (1 << 22)) + (pp_in_218 * (1 << 22)) + (pp_in_219 * (1 << 22)) + (pp_in_220 * (1 << 23)) + (pp_in_221 * (1 << 23)) + (pp_in_222 * (1 << 23)) + (pp_in_223 * (1 << 23)) + (pp_in_224 * (1 << 23)) + (pp_in_225 * (1 << 23)) + (pp_in_226 * (1 << 23)) + (pp_in_227 * (1 << 23)) + (pp_in_228 * (1 << 24)) + (pp_in_229 * (1 << 24)) + (pp_in_230 * (1 << 24)) + (pp_in_231 * (1 << 24)) + (pp_in_232 * (1 << 24)) + (pp_in_233 * (1 << 24)) + (pp_in_234 * (1 << 24)) + (pp_in_235 * (1 << 25)) + (pp_in_236 * (1 << 25)) + (pp_in_237 * (1 << 25)) + (pp_in_238 * (1 << 25)) + (pp_in_239 * (1 << 25)) + (pp_in_240 * (1 << 25)) + (pp_in_241 * (1 << 26)) + (pp_in_242 * (1 << 26)) + (pp_in_243 * (1 << 26)) + (pp_in_244 * (1 << 26)) + (pp_in_245 * (1 << 26)) + (pp_in_246 * (1 << 27)) + (pp_in_247 * (1 << 27)) + (pp_in_248 * (1 << 27)) + (pp_in_249 * (1 << 27)) + (pp_in_250 * (1 << 28)) + (pp_in_251 * (1 << 28)) + (pp_in_252 * (1 << 28)) + (pp_in_253 * (1 << 29)) + (pp_in_254 * (1 << 29)) + (pp_in_255 * (1 << 30));
            actual_weight = 0 + (out_pp_0 * (1 << 0)) + (out_pp_1 * (1 << 1)) + (out_pp_2 * (1 << 1)) + (out_pp_236 * (1 << 25)) + (out_pp_244 * (1 << 26)) + (out_pp_248 * (1 << 27)) + (out_pp_250 * (1 << 28)) + (out_pp_253 * (1 << 29)) + (out_pp_255 * (1 << 30)) + (comp_0_S * (1 << 2)) + (comp_2_S * (1 << 3)) + (comp_5_S * (1 << 4)) + (comp_9_S * (1 << 5)) + (comp_14_S * (1 << 6)) + (comp_20_S * (1 << 7)) + (comp_27_S * (1 << 8)) + (comp_35_S * (1 << 9)) + (comp_44_S * (1 << 10)) + (comp_54_S * (1 << 11)) + (comp_65_S * (1 << 12)) + (comp_77_S * (1 << 13)) + (comp_90_S * (1 << 14)) + (comp_104_S * (1 << 15)) + (comp_118_S * (1 << 16)) + (comp_131_S * (1 << 17)) + (comp_143_S * (1 << 18)) + (comp_154_S * (1 << 19)) + (comp_164_S * (1 << 20)) + (comp_173_S * (1 << 21)) + (comp_181_S * (1 << 22)) + (comp_188_S * (1 << 23)) + (comp_194_S * (1 << 24)) + (comp_199_S * (1 << 25)) + (comp_203_S * (1 << 26)) + (comp_206_S * (1 << 27)) + (comp_208_S * (1 << 28)) + (comp_209_S * (1 << 29)) + (comp_107_CO * (1 << 17)) + (comp_121_CO * (1 << 18)) + (comp_134_CO * (1 << 19)) + (comp_144_CO * (1 << 20)) + (comp_157_CO * (1 << 21)) + (comp_167_CO * (1 << 22)) + (comp_175_CO * (1 << 23)) + (comp_182_CO * (1 << 24)) + (comp_209_CO * (1 << 30));

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
