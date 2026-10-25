module reference_writer #(
    parameter integer EVENT_PERIOD = 1000000
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk100 CLK", X_INTERFACE_PARAMETER = "XIL_INTERFACENAME clk100, ASSOCIATED_BUSIF M_AXI, ASSOCIATED_RESET resetn, FREQ_HZ 100000000" *) input wire clk100,
    input wire cfgclk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 resetn RST", X_INTERFACE_PARAMETER = "XIL_INTERFACENAME resetn, POLARITY ACTIVE_LOW" *) input wire resetn,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI AWADDR", X_INTERFACE_PARAMETER = "XIL_INTERFACENAME M_AXI, PROTOCOL AXI4, DATA_WIDTH 32, ADDR_WIDTH 32, ID_WIDTH 1, HAS_BURST 1, HAS_LOCK 1, HAS_CACHE 1, HAS_QOS 1, HAS_REGION 1, HAS_WSTRB 1, HAS_BRESP 1, HAS_RRESP 1" *)    output reg [31:0] m_axi_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI AWID" *)    output wire [0:0] m_axi_awid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI AWVALID" *)    output reg m_axi_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI AWREADY" *)    input wire m_axi_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI AWLEN" *)    output wire [7:0] m_axi_awlen,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI AWSIZE" *)    output wire [2:0] m_axi_awsize,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI AWBURST" *)    output wire [1:0] m_axi_awburst,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI AWLOCK" *)    output wire m_axi_awlock,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI AWCACHE" *)    output wire [3:0] m_axi_awcache,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI AWPROT" *)    output wire [2:0] m_axi_awprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI AWQOS" *)    output wire [3:0] m_axi_awqos,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI AWREGION" *)    output wire [3:0] m_axi_awregion,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI WDATA" *)    output reg [31:0] m_axi_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI WSTRB" *)    output wire [3:0] m_axi_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI WVALID" *)    output reg m_axi_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI WREADY" *)    input wire m_axi_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI WLAST" *)    output wire m_axi_wlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI BID" *)    input wire [0:0] m_axi_bid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI BRESP" *)    input wire [1:0] m_axi_bresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI BVALID" *)    input wire m_axi_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI BREADY" *)    output reg m_axi_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI ARADDR" *)    output reg [31:0] m_axi_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI ARID" *)    output wire [0:0] m_axi_arid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI ARVALID" *)    output reg m_axi_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI ARREADY" *)    input wire m_axi_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI ARLEN" *)    output wire [7:0] m_axi_arlen,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI ARSIZE" *)    output wire [2:0] m_axi_arsize,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI ARBURST" *)    output wire [1:0] m_axi_arburst,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI ARLOCK" *)    output wire m_axi_arlock,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI ARCACHE" *)    output wire [3:0] m_axi_arcache,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI ARPROT" *)    output wire [2:0] m_axi_arprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI ARQOS" *)    output wire [3:0] m_axi_arqos,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI ARREGION" *)    output wire [3:0] m_axi_arregion,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI RID" *)    input wire [0:0] m_axi_rid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI RDATA" *)    input wire [31:0] m_axi_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI RRESP" *)    input wire [1:0] m_axi_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI RLAST" *)    input wire m_axi_rlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI RVALID" *)    input wire m_axi_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI RREADY" *)    output reg m_axi_rready
);
    localparam [31:0] MAGIC_ADDR = 32'h04029100;
    localparam [31:0] PHASE_ADDR = 32'h04029104;
    localparam [31:0] MAILBOX = 32'h04029500;
    localparam [31:0] MAGIC = 32'h504d434d;

    (* ASYNC_REG = "TRUE" *) reg [1:0] cfg_reset_pipe;
    reg [31:0] cfg_binary_count;
    reg [31:0] cfg_gray_count;
    (* ASYNC_REG = "TRUE" *) reg [31:0] cfg_gray_meta;
    (* ASYNC_REG = "TRUE" *) reg [31:0] cfg_gray_sync;
    reg [31:0] snapshot_cfg;

    always @(posedge cfgclk or negedge resetn) begin
        if (!resetn) cfg_reset_pipe <= 2'b00;
        else cfg_reset_pipe <= {cfg_reset_pipe[0], 1'b1};
    end
    always @(posedge cfgclk or negedge resetn) begin
        if (!resetn) begin
            cfg_binary_count <= 32'd0;
            cfg_gray_count <= 32'd0;
        end else if (cfg_reset_pipe[1]) begin
            cfg_binary_count <= cfg_binary_count + 1'b1;
            cfg_gray_count <= ((cfg_binary_count + 1'b1) >> 1) ^ (cfg_binary_count + 1'b1);
        end
    end

    always @(posedge clk100) begin
        if (!resetn) begin
            cfg_gray_meta <= 32'd0;
            cfg_gray_sync <= 32'd0;
        end else begin
            cfg_gray_meta <= cfg_gray_count;
            cfg_gray_sync <= cfg_gray_meta;
        end
    end

    function [31:0] gray_to_binary;
        input [31:0] gray;
        integer i;
        begin
            gray_to_binary[31] = gray[31];
            for (i = 30; i >= 0; i = i - 1)
                gray_to_binary[i] = gray_to_binary[i+1] ^ gray[i];
        end
    endfunction

    assign m_axi_awid = 1'b0;
    assign m_axi_awlen = 8'd0;
    assign m_axi_awsize = 3'd2;
    assign m_axi_awburst = 2'b01;
    assign m_axi_awlock = 1'b0;
    assign m_axi_awcache = 4'b0011;
    assign m_axi_awprot = 3'b000;
    assign m_axi_awqos = 4'b0000;
    assign m_axi_awregion = 4'b0000;
    assign m_axi_wstrb = 4'b1111;
    assign m_axi_wlast = 1'b1;
    assign m_axi_arid = 1'b0;
    assign m_axi_arlen = 8'd0;
    assign m_axi_arsize = 3'd2;
    assign m_axi_arburst = 2'b01;
    assign m_axi_arlock = 1'b0;
    assign m_axi_arcache = 4'b0011;
    assign m_axi_arprot = 3'b000;
    assign m_axi_arqos = 4'b0000;
    assign m_axi_arregion = 4'b0000;

    localparam [3:0] ST_MAGIC_AR=0, ST_MAGIC_R=1, ST_PHASE_AR=2, ST_PHASE_R=3,
                     ST_WAIT=4, ST_W_LOW=5, ST_W_HIGH=6, ST_W_CFG=7,
                     ST_W_SEQ=8, ST_W_B=9;
    reg [3:0] state;
    reg [31:0] ref_counter_low, ref_counter_high;
    reg [31:0] snapshot_low, snapshot_high;
    reg [31:0] event_sequence;
    reg [31:0] divider;
    reg write_addr_done, write_data_done;

    always @(posedge clk100) begin
        if (!resetn) begin
            state <= ST_MAGIC_AR;
            m_axi_araddr <= MAGIC_ADDR;
            m_axi_arvalid <= 1'b0;
            m_axi_rready <= 1'b0;
            m_axi_awaddr <= MAILBOX;
            m_axi_awvalid <= 1'b0;
            m_axi_wdata <= 32'd0;
            m_axi_wvalid <= 1'b0;
            m_axi_bready <= 1'b0;
            ref_counter_low <= 32'd0;
            ref_counter_high <= 32'd0;
            snapshot_low <= 32'd0;
            snapshot_high <= 32'd0;
            snapshot_cfg <= 32'd0;
            event_sequence <= 32'd0;
            divider <= 32'd0;
            write_addr_done <= 1'b0;
            write_data_done <= 1'b0;
        end else begin
            ref_counter_low <= ref_counter_low + 1'b1;
            if (ref_counter_low == 32'hffffffff) ref_counter_high <= ref_counter_high + 1'b1;
            case (state)
                ST_MAGIC_AR: begin
                    if (!m_axi_arvalid) begin m_axi_araddr <= MAGIC_ADDR; m_axi_arvalid <= 1'b1; end
                    else if (m_axi_arready) begin m_axi_arvalid <= 1'b0; m_axi_rready <= 1'b1; state <= ST_MAGIC_R; end
                end
                ST_MAGIC_R: if (m_axi_rvalid && m_axi_rready) begin
                    m_axi_rready <= 1'b0;
                    if (m_axi_rresp == 0 && m_axi_rdata == MAGIC) state <= ST_PHASE_AR;
                    else state <= ST_MAGIC_AR;
                end
                ST_PHASE_AR: begin
                    if (!m_axi_arvalid) begin m_axi_araddr <= PHASE_ADDR; m_axi_arvalid <= 1'b1; end
                    else if (m_axi_arready) begin m_axi_arvalid <= 1'b0; m_axi_rready <= 1'b1; state <= ST_PHASE_R; end
                end
                ST_PHASE_R: if (m_axi_rvalid && m_axi_rready) begin
                    m_axi_rready <= 1'b0;
                    if (m_axi_rresp == 0 && m_axi_rdata == 2) begin divider <= 0; state <= ST_WAIT; end
                    else state <= ST_MAGIC_AR;
                end
                ST_WAIT: begin
                    if (divider == EVENT_PERIOD-1) begin
                        divider <= 0; event_sequence <= event_sequence + 1'b1;
                        snapshot_low <= ref_counter_low;
                        snapshot_high <= ref_counter_high;
                        snapshot_cfg <= gray_to_binary(cfg_gray_sync);
                        write_addr_done <= 1'b0; write_data_done <= 1'b0;
                        state <= ST_W_LOW;
                    end else divider <= divider + 1'b1;
                end
                ST_W_LOW: begin
                    if (!m_axi_awvalid && !m_axi_wvalid) begin
                        m_axi_awaddr <= MAILBOX + 4; m_axi_awvalid <= 1'b1;
                        m_axi_wdata <= snapshot_low; m_axi_wvalid <= 1'b1;
                    end
                    if (m_axi_awvalid && m_axi_awready) begin m_axi_awvalid <= 1'b0; write_addr_done <= 1'b1; end
                    if (m_axi_wvalid && m_axi_wready) begin m_axi_wvalid <= 1'b0; write_data_done <= 1'b1; end
                    if ((write_addr_done || (m_axi_awvalid && m_axi_awready)) &&
                        (write_data_done || (m_axi_wvalid && m_axi_wready))) state <= ST_W_B;
                end
                ST_W_HIGH: begin
                    if (!m_axi_awvalid && !m_axi_wvalid) begin
                        m_axi_awaddr <= MAILBOX + 8; m_axi_awvalid <= 1'b1;
                        m_axi_wdata <= snapshot_high; m_axi_wvalid <= 1'b1;
                    end
                    if (m_axi_awvalid && m_axi_awready) begin m_axi_awvalid <= 1'b0; write_addr_done <= 1'b1; end
                    if (m_axi_wvalid && m_axi_wready) begin m_axi_wvalid <= 1'b0; write_data_done <= 1'b1; end
                    if ((write_addr_done || (m_axi_awvalid && m_axi_awready)) &&
                        (write_data_done || (m_axi_wvalid && m_axi_wready))) state <= ST_W_B;
                end
                ST_W_SEQ: begin
                    if (!m_axi_awvalid && !m_axi_wvalid) begin
                        m_axi_awaddr <= MAILBOX; m_axi_awvalid <= 1'b1;
                        m_axi_wdata <= event_sequence; m_axi_wvalid <= 1'b1;
                    end
                    if (m_axi_awvalid && m_axi_awready) begin m_axi_awvalid <= 1'b0; write_addr_done <= 1'b1; end
                    if (m_axi_wvalid && m_axi_wready) begin m_axi_wvalid <= 1'b0; write_data_done <= 1'b1; end
                    if ((write_addr_done || (m_axi_awvalid && m_axi_awready)) &&
                        (write_data_done || (m_axi_wvalid && m_axi_wready))) state <= ST_W_B;
                end
                ST_W_CFG: begin
                    if (!m_axi_awvalid && !m_axi_wvalid) begin
                        m_axi_awaddr <= MAILBOX + 16; m_axi_awvalid <= 1'b1;
                        m_axi_wdata <= snapshot_cfg; m_axi_wvalid <= 1'b1;
                    end
                    if (m_axi_awvalid && m_axi_awready) begin m_axi_awvalid <= 1'b0; write_addr_done <= 1'b1; end
                    if (m_axi_wvalid && m_axi_wready) begin m_axi_wvalid <= 1'b0; write_data_done <= 1'b1; end
                    if ((write_addr_done || (m_axi_awvalid && m_axi_awready)) &&
                        (write_data_done || (m_axi_wvalid && m_axi_wready))) state <= ST_W_B;
                end
                ST_W_B: begin
                    m_axi_bready <= 1'b1;
                    if (m_axi_bvalid && m_axi_bready) begin
                        m_axi_bready <= 1'b0;
                        if (m_axi_bresp != 0) state <= ST_MAGIC_AR;
                        else if (m_axi_awaddr == MAILBOX+4) begin
                            write_addr_done <= 1'b0; write_data_done <= 1'b0; state <= ST_W_HIGH;
                        end else if (m_axi_awaddr == MAILBOX+8) begin
                            write_addr_done <= 1'b0; write_data_done <= 1'b0; state <= ST_W_CFG;
                        end else if (m_axi_awaddr == MAILBOX+16) begin
                            write_addr_done <= 1'b0; write_data_done <= 1'b0; state <= ST_W_SEQ;
                        end
                        else state <= ST_WAIT;
                    end
                end
                default: state <= ST_MAGIC_AR;
            endcase
        end
    end
endmodule
