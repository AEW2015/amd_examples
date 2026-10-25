module sec_top (
    input wire sysclk_p,
    input wire sysclk_n,
    input wire reset_n,
    input wire uartb_rxd,
    output wire uartb_txd
);
    wire clk_ibuf;
    wire clk;
    IBUFDS #(.DIFF_TERM("FALSE")) clock_in (
        .I(sysclk_p), .IB(sysclk_n), .O(clk_ibuf)
    );
    BUFG clock_global (.I(clk_ibuf), .O(clk));
    sys_wrapper system_i (
        .sysclk(clk), .reset_n(reset_n),
        .uartb_rxd(uartb_rxd), .uartb_txd(uartb_txd)
    );
endmodule
