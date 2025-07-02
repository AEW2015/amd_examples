--Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
--Copyright 2022-2025 Advanced Micro Devices, Inc. All Rights Reserved.
----------------------------------------------------------------------------------
--Tool Version: Vivado v.2025.1 (win64) Build 6140274 Thu May 22 00:12:29 MDT 2025
--Date        : Tue Jul  1 22:38:55 2025
--Host        : DESKTOP-I75K8PP running 64-bit major release  (build 9200)
--Command     : generate_target top_wrapper.bd
--Design      : top_wrapper
--Purpose     : IP block netlist
----------------------------------------------------------------------------------
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
library UNISIM;
use UNISIM.VCOMPONENTS.ALL;
entity top_wrapper is
  port (
    hpc_io : inout STD_LOGIC_VECTOR ( 11 downto 0 );
    reset : in STD_LOGIC;
    scu35_uartb_rxd : in STD_LOGIC;
    scu35_uartb_txd : out STD_LOGIC;
    sys_diff_clock_clk_n : in STD_LOGIC;
    sys_diff_clock_clk_p : in STD_LOGIC
  );
end top_wrapper;

architecture STRUCTURE of top_wrapper is
  component top is
  port (
    sys_diff_clock_clk_n : in STD_LOGIC;
    sys_diff_clock_clk_p : in STD_LOGIC;
    scu35_uartb_rxd : in STD_LOGIC;
    scu35_uartb_txd : out STD_LOGIC;
    reset : in STD_LOGIC;
    main_clk : out STD_LOGIC;
    hpc_tri_0 : out STD_LOGIC_VECTOR ( 11 downto 0 );
    hpc_dout_r_0 : out STD_LOGIC_VECTOR ( 11 downto 0 );
    hpc_dout_f_0 : out STD_LOGIC_VECTOR ( 11 downto 0 );
    hpc_din_r_0 : in STD_LOGIC_VECTOR ( 11 downto 0 );
    hpc_din_f_0 : in STD_LOGIC_VECTOR ( 11 downto 0 )
  );
  end component top;
  
    signal hpc_tri    : STD_LOGIC_VECTOR ( 11 downto 0 );
    signal hpc_dout_r : STD_LOGIC_VECTOR ( 11 downto 0 );
    signal hpc_dout_f : STD_LOGIC_VECTOR ( 11 downto 0 );
    signal hpc_din_r  : STD_LOGIC_VECTOR ( 11 downto 0 );
    signal hpc_din_f  : STD_LOGIC_VECTOR ( 11 downto 0 );
    signal main_clk : std_logic;
    signal main_clk_180 : std_logic;
    
begin


    io_block : block
        -- Intermediate signals scoped inside this block
        signal din_rise  : std_logic_vector(11 downto 0);
        signal din_fall  : std_logic_vector(11 downto 0);
        signal dout_q1   : std_logic_vector(11 downto 0);
        signal dout_q2   : std_logic_vector(11 downto 0);
        signal dq_ibuf   : std_logic_vector(11 downto 0);
        signal dq_drive  : std_logic_vector(11 downto 0);
        signal dq_t      : std_logic_vector(11 downto 0);
    begin

        main_clk_180 <= not main_clk;

        gen_loop : for i in 0 to 11 generate

               ODDRE1_inst : ODDRE1
               generic map (
                  SIM_DEVICE => "ULTRASCALE_PLUS", -- Set the device version for simulation functionality (ULTRASCALE, ULTRASCALE_PLUS, ULTRASCALE_PLUS_ES1,
                    
                  SRVAL => '1'                     -- Initializes the ODDRE1 Flip-Flops to the specified value ('0', '1')                               -- ULTRASCALE_PLUS_ES2)
               )
               port map (
                  Q => dq_drive(i),
                  C => main_clk,
                  D1 => hpc_dout_r(i),
                  D2 => hpc_dout_f(i),
                  SR => '0'
               );
               
              ODDRE1t_inst : ODDRE1
               generic map (
                  SIM_DEVICE => "ULTRASCALE_PLUS", -- Set the device version for simulation functionality (ULTRASCALE, ULTRASCALE_PLUS, ULTRASCALE_PLUS_ES1,
                    
                  SRVAL => '1'                     -- Initializes the ODDRE1 Flip-Flops to the specified value ('0', '1')                               -- ULTRASCALE_PLUS_ES2)
               )
               port map (
                  Q => dq_t(i),
                  C => main_clk,
                  D1 => hpc_tri(i),
                  D2 => hpc_tri(i),
                  SR => '0'
               );
  
                
               IDDRE1_inst : IDDRE1
               generic map (
                  DDR_CLK_EDGE => "SAME_EDGE_PIPELINED", -- IDDRE1 mode (OPPOSITE_EDGE, SAME_EDGE, SAME_EDGE_PIPELINED)
                  IS_CB_INVERTED => '0',           -- Optional inversion for CB
                  IS_C_INVERTED => '0'             -- Optional inversion for C
               )
               port map (
                  Q1 => hpc_din_r(i), -- 1-bit output: Registered parallel output 1
                  Q2 => hpc_din_f(i), -- 1-bit output: Registered parallel output 2
                  C => main_clk,   -- 1-bit input: High-speed clock
                  CB => main_clk_180, -- 1-bit input: Inversion of High-speed clock C
                  D => dq_ibuf(i),
                  R => '0'
               );

            IOBUF_inst : IOBUF
                port map (
                    IO => hpc_io(i),
                    I  => dq_drive(i),
                    O  => dq_ibuf(i),
                    T  => dq_t(i)
                );

        end generate;

    end block io_block;
    
top_i: component top
     port map (
      hpc_din_f_0(11 downto 0) => hpc_din_f(11 downto 0),
      hpc_din_r_0(11 downto 0) => hpc_din_r(11 downto 0),
      hpc_dout_f_0(11 downto 0) => hpc_dout_f(11 downto 0),
      hpc_dout_r_0(11 downto 0) => hpc_dout_r(11 downto 0),
      hpc_tri_0(11 downto 0) => hpc_tri(11 downto 0),
      main_clk => main_clk,
      reset => reset,
      scu35_uartb_rxd => scu35_uartb_rxd,
      scu35_uartb_txd => scu35_uartb_txd,
      sys_diff_clock_clk_n => sys_diff_clock_clk_n,
      sys_diff_clock_clk_p => sys_diff_clock_clk_p
    );
end STRUCTURE;
