module top(input sysclk_p, input sysclk_n);
    wire clk_in, clk100, cfgclk_raw, cfgclk;
    IBUFDS clock_input (.I(sysclk_p), .IB(sysclk_n), .O(clk_in));
    BUFG clock_global (.I(clk_in), .O(clk100));
    STARTUPE3 #(
        .PROG_USR("FALSE"),
        .SIM_CCLK_FREQ(0.0)
    ) startupe3_cfg (
        .CFGCLK(cfgclk_raw), .CFGMCLK(), .DI(), .DO(4'b0000), .DTS(4'b1111),
        .EOS(), .PREQ(), .FCSBO(1'b1), .FCSBTS(1'b1),
        .GSR(1'b0), .GTS(1'b0), .KEYCLEARB(1'b1), .PACK(1'b0),
        .USRCCLKO(1'b0), .USRCCLKTS(1'b1),
        .USRDONEO(1'b1), .USRDONETS(1'b1)
    );
    BUFG cfg_clock_global (.I(cfgclk_raw), .O(cfgclk));
    clock_fixture_bd clock_fixture_design (.clk100(clk100), .cfgclk(cfgclk));
endmodule
