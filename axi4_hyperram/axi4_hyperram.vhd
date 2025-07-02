----------------------------------------------------------------------------------
-- Company: 
-- Engineer: 
-- 
-- Create Date: 06/29/2025 08:49:17 PM
-- Design Name: 
-- Module Name: axi4_hyperram - Behavioral
-- Project Name: 
-- Target Devices: 
-- Tool Versions: 
-- Description: 
-- 
-- Dependencies: 
-- 
-- Revision:
-- Revision 0.01 - File Created
-- Additional Comments:
-- 
----------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

-- Uncomment the following library declaration if using
-- arithmetic functions with Signed or Unsigned values
use IEEE.NUMERIC_STD.ALL;

-- Uncomment the following library declaration if instantiating
-- any Xilinx leaf cells in this code.
--library UNISIM;
--use UNISIM.VComponents.all;

entity axi4_hyperram is
	generic (
		C_S00_AXI_DATA_WIDTH	: integer	:= 32;
		C_S00_AXI_ADDR_WIDTH	: integer	:= 23
	);
    Port ( 		
		s00_axi_aclk	: in std_logic;
		s00_axi_aresetn	: in std_logic;
		s00_axi_awaddr	: in std_logic_vector(C_S00_AXI_ADDR_WIDTH-1 downto 0);
		s00_axi_awlen	: in std_logic_vector(7 downto 0);
		s00_axi_awsize	: in std_logic_vector(2 downto 0);
		s00_axi_awburst	: in std_logic_vector(1 downto 0);
		s00_axi_awprot	: in std_logic_vector(2 downto 0);
		s00_axi_awvalid	: in std_logic;
		s00_axi_awready	: out std_logic;
		s00_axi_wdata	: in std_logic_vector(C_S00_AXI_DATA_WIDTH-1 downto 0);
		s00_axi_wstrb	: in std_logic_vector((C_S00_AXI_DATA_WIDTH/8)-1 downto 0);
		s00_axi_wlast	: in std_logic;
		s00_axi_wvalid	: in std_logic;
		s00_axi_wready	: out std_logic;
		s00_axi_bresp	: out std_logic_vector(1 downto 0);
		s00_axi_bvalid	: out std_logic;
		s00_axi_bready	: in std_logic;
		s00_axi_araddr	: in std_logic_vector(C_S00_AXI_ADDR_WIDTH-1 downto 0);
		s00_axi_arlen	: in std_logic_vector(7 downto 0);
		s00_axi_arsize	: in std_logic_vector(2 downto 0);
		s00_axi_arburst	: in std_logic_vector(1 downto 0);
		s00_axi_arprot	: in std_logic_vector(2 downto 0);
		s00_axi_arvalid	: in std_logic;
		s00_axi_arready	: out std_logic;
		s00_axi_rdata	: out std_logic_vector(C_S00_AXI_DATA_WIDTH-1 downto 0);
		s00_axi_rresp	: out std_logic_vector(1 downto 0);
		s00_axi_rlast	: out std_logic;
		s00_axi_rvalid	: out std_logic;
		s00_axi_rready	: in std_logic;
		
        hpc_tri     : out std_logic_vector (11 downto 0);
        hpc_dout_r  : out std_logic_vector (11 downto 0);
        hpc_dout_f  : out std_logic_vector (11 downto 0);
        hpc_din_r   : in  std_logic_vector (11 downto 0);
        hpc_din_f   : in  std_logic_vector (11 downto 0));
end axi4_hyperram;

architecture Behavioral of axi4_hyperram is

		
        signal write_en    : std_logic;
        signal read_en     : std_logic;
        signal busy        : std_logic;
        signal cmd_out     : std_logic_vector (47 downto 0);
        signal addr_out    : std_logic_vector(22 downto 0);
        
        signal writ_valid : std_logic;
        signal writ_done : std_logic;
        signal read_valid : std_logic;
        signal read_done : std_logic;
        
        signal writ_addr: std_logic_vector(22 downto 0);        
        signal writ_data_out : std_logic_vector (127 downto 0);        
        signal writ_wbyte : std_logic_vector (15 downto 0);
        
        signal read_addr: std_logic_vector(22 downto 0);       
        signal phy_data_out : std_logic_vector (127 downto 0);     
        signal byte_out     : std_logic_vector (31 downto 0);        




begin


 -------------------------------------------------------------------
    -- AXI4 Write Channel Block
    -------------------------------------------------------------------
    axi4_channel_blk: block
        signal aw_ready : std_logic := '1';
        signal w_ready  : std_logic;
        signal b_valid  : std_logic;
        
        signal wr_cnt : unsigned(1 downto 0);
        
        
        signal ar_ready  : std_logic := '1';
        signal r_valid  : std_logic;
        signal r_last  : std_logic;
        signal r_dout  : std_logic_vector (31 downto 0);
        
        signal rd_cnt : unsigned(1 downto 0);
        signal burst_len : unsigned(1 downto 0);
        
    begin
        -- assign outputs
        s00_axi_awready <= aw_ready;
        s00_axi_wready  <= w_ready;
        s00_axi_bresp	<= "00";
        s00_axi_bvalid  <= b_valid;
        s00_axi_arready <= ar_ready;
        s00_axi_rdata	<= r_dout;
        s00_axi_rresp	<= "00";
        s00_axi_rlast   <= r_last;
        s00_axi_rvalid	<= r_valid;
        
        
        -- Write Address Handling
        process(s00_axi_aclk)
        begin
            if rising_edge(s00_axi_aclk) then
                if s00_axi_aresetn = '0' then
                    aw_ready <= '1'; -- always ready to go!
                    w_ready <= '0';
                    b_valid <= '0';
                    writ_valid <= '0';
                    writ_wbyte <= (others=>'0');
                    wr_cnt <= (others=>'0');
                else
                    -- capture valid data when ready
                    if  s00_axi_awvalid = '1' and aw_ready='1' then
                        writ_addr <= s00_axi_awaddr;
                        aw_ready <= '0';
                        writ_wbyte <= (others=>'0');
                        wr_cnt <= (others=>'0');
                        w_ready <= '1';
                    end if;
                    
                    if s00_axi_wvalid = '1' and w_ready = '1' then
                        case wr_cnt is
                        when "00" =>
                            writ_data_out(127 downto 96) <= s00_axi_wdata;
                            writ_wbyte(15 downto 12) <= s00_axi_wstrb;
                        when "01" =>
                            writ_data_out(95 downto 64) <= s00_axi_wdata;
                            writ_wbyte(11 downto 8) <= s00_axi_wstrb;
                        when "10" =>
                            writ_data_out(63 downto 32) <= s00_axi_wdata;
                            writ_wbyte(7 downto 4) <= s00_axi_wstrb;
                        when others =>
                            writ_data_out(31 downto 0) <= s00_axi_wdata;
                            writ_wbyte(3 downto 0) <= s00_axi_wstrb;
                        end case;
                        wr_cnt <= wr_cnt + 1;
                        if s00_axi_wlast = '1' then
                          w_ready <= '0';                          
                          writ_valid <= '1';
                        end if;
                    
                    end if;
                    
                    if writ_done = '1' then                     
                        writ_valid <= '0';
                        b_valid <= '1';
                    end if;
                    
                    
                    if s00_axi_bready = '1' and b_valid = '1' then
                         b_valid <= '0';
                         writ_valid <= '0';   
                         aw_ready <= '1';
                    end if;
                    
                    -- AXI transaction has to complete or it needs a reset :)
                end if;
            end if;
        end process;

        -- Read Handling
        process(s00_axi_aclk)
        begin
            if rising_edge(s00_axi_aclk) then
                if s00_axi_aresetn = '0' then
                    ar_ready <= '1';
                    r_valid <= '0';
                    rd_cnt <= (others => '0');
                    burst_len <= "00";
                else
                    if  s00_axi_arvalid = '1' and ar_ready='1' then
                        ar_ready <= '0';
                        read_addr <= s00_axi_araddr;
                        burst_len <= unsigned(s00_axi_arlen(1 downto 0));
                        rd_cnt <= (others => '0');
                        read_valid <= '1';
                    end if;
                    
                    if read_done = '1' then
                        read_valid <= '0';
                        r_valid <= '1';
                    end if;
                    
                    if s00_axi_rready = '1' and r_valid = '1' then
                         burst_len <= burst_len -1 ;
                         rd_cnt <= rd_cnt + 1;
                         if burst_len = 0 then
                            r_valid <= '0';
                            ar_ready <= '1';
                         end if;
                    end if;

                end if;
            end if;
        end process;

    with rd_cnt select
        r_dout <=
                  phy_data_out ( 31 downto  0) when "11",
                  phy_data_out ( 63 downto 32) when "10",
                  phy_data_out ( 95 downto 64) when "01",
                  byte_out                     when "00",
                  x"CAFE7AC0"                   when others;
                  
    r_last <= '1' when r_valid = '1' and burst_len = 0 else '0';

    end block axi4_channel_blk;

byte_out <= x"000000" & phy_data_out (127 downto 120) when read_addr( 1 downto 0) = "11" else
            x"0000"   & phy_data_out (127 downto 112) when read_addr( 1 downto 0) = "10" else
            x"00"     & phy_data_out (127 downto 104) when read_addr( 1 downto 0) = "01" else
                        phy_data_out (127 downto 96);

write_en <= '1' when read_valid = '0' and writ_valid = '1' else '0';
read_en <= '1' when read_valid = '1' else '0';

addr_out <= read_addr when read_en = '1' else writ_addr;

cmd_out <= read_en 
         & '0'  -- memory space
         & '0'  -- burst
         & "0000000000"
         & addr_out(22 downto 4)
         & "0000000000000"
         & addr_out(3 downto 2)
         & '0' --always on 32 allinged
         ;

hyper_phy_blk: block
    type state_type is (IDLE, CMD, LATE, DOUT, DIN);
    signal state, next_state : state_type;
    signal cmd_in, cmd_reg: std_logic_vector (47 downto 0);
    signal wdata, wdata_reg: std_logic_vector (127 downto 0);
    signal wbyte, wbyte_reg: std_logic_vector (15 downto 0);
    signal dout_old, dout_new, dout_next: std_logic_vector (7 downto 0);
    signal din_reg, din_next: std_logic_vector (127 downto 0);
    signal cs, cs_reg: std_logic; --tri control this?
    signal ck, ck_reg: std_logic;
    signal rwdr, rwdr_reg: std_logic;
    signal dbir, dbir_reg: std_logic;
    signal counter, count_reg : unsigned (7 downto 0);
    signal read_reg, read_edge : std_logic;
    signal read_op_reg, read_op : std_logic;
    signal writ_reg, writ_edge : std_logic;
    signal clk_in      : std_logic;
begin

clk_in <= s00_axi_aclk;

phy_data_out <= din_reg;

--Do a shift register
hpc_tri(11) <= '1';
hpc_dout_r (11) <= '0';
hpc_dout_f (11) <= '0';

hpc_tri(10) <= rwdr_reg;
hpc_dout_r (10) <= '0';
hpc_dout_f (10) <= '0';

hpc_tri(9) <= cs_reg;
hpc_dout_r (9) <= '0';
hpc_dout_f (9) <= '0';

hpc_tri(8) <= cs_reg;
hpc_dout_r (8) <= ck_reg;
hpc_dout_f (8) <= ck_reg;

hpc_tri(7 downto 0) <= (others=>dbir_reg);
hpc_dout_r( 7 downto 0) <= dout_old;
hpc_dout_f( 7 downto 0) <= dout_new;


-- When tri is low
-- Data out engine (enable, data_byte)
-- 00_11_00_11_00_11_00_11_00
-- X0_01_12_23_34_45_5X_XX_XX

-- When tri is high
-- Data in enginer
-- 00_11_00_11_00_00_00_00
-- XX_X0_01_12_23_3
-- XX_XX_X0_01_12_23_3

--Idle
    -- CS goes low
--Addr/ CMD
    -- Assign address for egnine
    -- wait ?
--Wait
    -- Data engine out with emptye data
--Data out
    -- use dout
--Data in
    --flip tri-state
    -- record values

-- Single-process FSM: state transitions and outputs
process(clk_in)
begin
    if  rising_edge(clk_in) then
        state <= next_state;
        cmd_reg <= cmd_in;
        wdata_reg <= wdata;
        wbyte_reg <= wbyte;
        dout_new <= dout_next;
        dout_old <= dout_new;
        din_reg <= din_next;
        rwdr_reg <= rwdr;
        cs_reg <= cs;
        ck_reg <= ck;
        dbir_reg <= dbir;
        count_reg <= counter;        
        read_reg <= read_en;
        read_op_reg <= read_op;
        writ_reg <= write_en;
    end if;
end process;

read_edge <= read_en and not read_reg;
writ_edge <= write_en and not writ_reg;


-- read_en or write_en

-- Combinational logic for next state and outputs
process(
cmd_reg, count_reg, wdata_reg, wbyte_reg, read_op_reg,  -- defaults
read_edge,writ_edge, cmd_out, writ_wbyte, writ_data_out,      --IDLE logic
ck_reg,                         -- CMD logic
din_reg, hpc_din_r,
state) 
begin
    -- Default outputs
    next_state <= state;
    cmd_in <= cmd_reg;
    counter <= count_reg;
    wdata <= wdata_reg;
    wbyte <= wbyte_reg;
    din_next <= din_reg;
    read_op <= read_op_reg;
    
    
    dout_next <= x"00";
    rwdr <= '1';    --tri high for input most of the time
    cs <= '1';      --tri high for input when idle
    ck <= '0';      -- idle this at zero, enbale with cs = 0;
    dbir <= '1';    -- idle as input
    busy <= '1';
    writ_done <= '0';
    read_done <= '0';

    


    case state is
        when IDLE =>
            busy <= '0';
            read_op <='0';
            -- CS goes low
            if (read_edge='1' or writ_edge='1') then --reg the edge
                read_op <= read_edge;
                cs <= '0';
                wdata <= writ_data_out;-- should lock data
                wbyte <= writ_wbyte;
                dbir <= '0'; --drive
                dout_next <= cmd_out(47 downto 40);
                cmd_in <= cmd_out(39 downto 0) & x"00";                
                -- should probably start first cmd byte here...
                next_state <= CMD;
                counter <= x"05";
            end if;
            
        when CMD =>
            cs <= '0';
            counter <= count_reg - 1;
            ck <= not ck_reg;
            dbir <= '0'; --drive
            dout_next <= cmd_reg(47 downto 40);
            cmd_in <= cmd_reg(39 downto 0) & x"00";
            --go through the 6 bytes for command
            if (count_reg = 0) then 
                next_state <= LATE;
                counter <= x"18"; -- (13*2)-1 for data setup?
            end if;
            
        when LATE =>        
            cs <= '0';
            dbir <= '0'; --drive?
            counter <= count_reg - 1;
            ck <= not ck_reg;
            -- 13 more clk peroids
            if (count_reg = 0) then 
                if (read_op_reg='0') then
                counter <= x"11"; 
                next_state <= DOUT;
                
                else 
                counter <= x"14"; 
                next_state <= DIN;                
                end if;
                
                
            end if;

        when DOUT =>
            cs <= '0';
            dbir <= '0'; --drive
            
            -- shift in wbyte
            rwdr <= not wbyte_reg(15); --drive 
            wbyte <= wbyte_reg(14 downto 0) & '0';
            
            ck <= not ck_reg;
            counter <= count_reg - 1;
            -- write 4 bytes
            dout_next <= wdata_reg(127 downto 120);
            wdata <= wdata_reg(119 downto 0) & x"00";
            if (count_reg = 0) then  
                cs <= '1';
                dbir <= '1';
                rwdr <= '1';
                writ_done <= '1';
                next_state <= IDLE;
                
            end if;

        when DIN =>
            cs <= '0';
            dbir <= '1'; --drive
            rwdr <= '1'; --drive
            ck <= not ck_reg;
                                    
            counter <= count_reg - 1;
            
            -- write 4 bytes
            din_next( 7 downto 0) <= hpc_din_f(7 downto 0);
            din_next(127 downto 8) <= din_reg(119 downto 0);
            if (count_reg = 0) then  
                --latch data for output                
                cs <= '1';
                dbir <= '1';
                rwdr <= '1';
                read_done <= '1';
                next_state <= IDLE;
                
            end if;

    end case;
end process;
end block hyper_phy_blk;

end Behavioral;
