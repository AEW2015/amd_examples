# Explicit SCU35 pin mapping; no board-store dependency.
# MII/MDIO pins checked against the SCU35 v1.2 part0_pins.xml.
set_property PACKAGE_PIN F23 [get_ports sysclk_p]
set_property PACKAGE_PIN E23 [get_ports sysclk_n]
set_property IOSTANDARD LVDS [get_ports {sysclk_p sysclk_n}]
create_clock -name sysclk -period 10.000 [get_ports sysclk_p]
set_property PACKAGE_PIN F3 [get_ports reset_n]
set_property IOSTANDARD LVCMOS33 [get_ports reset_n]
set_property PULLUP TRUE [get_ports reset_n]
set_property PACKAGE_PIN AC6 [get_ports uartb_rxd]
set_property PACKAGE_PIN AB6 [get_ports uartb_txd]
set_property IOSTANDARD LVCMOS33 [get_ports {uartb_rxd uartb_txd}]
foreach {port pin} {
 mii_rxd[0] AD7 mii_rxd[1] AE5 mii_rxd[2] AE6 mii_rxd[3] AE7
 mii_txd[0] AB7 mii_txd[1] AC7 mii_txd[2] W9 mii_txd[3] Y9
 mii_tx_clk AC9 mii_tx_en AD9 mii_rx_dv AE11 mii_rx_er AE8
 mii_rx_clk AE12 mii_col AE10 mii_crs AD6 mdio_mdc AB9
 mdio_mdio_io AA9 phy_reset_n AE9
} {
 set_property PACKAGE_PIN $pin [get_ports $port]
 set_property IOSTANDARD LVCMOS33 [get_ports $port]
}
set_property SLEW SLOW [get_ports {mii_txd[*] mii_tx_en mdio_mdc phy_reset_n}]
set_property DRIVE 8 [get_ports {mii_txd[*] mii_tx_en mdio_mdc phy_reset_n}]
create_clock -name mii_rx -period 40.000 [get_ports mii_rx_clk]
create_clock -name mii_tx -period 40.000 [get_ports mii_tx_clk]
# DP83867IR datasheet SNLS484J, sections 6.12/6.13, 100 Mbps MII.
# Add 1 ns conservative relative PCB skew to PHY RX delay / TX setup/hold.
# Board trace skew is not independently characterized by this project.
set_input_delay -clock mii_rx -min 9.0 [get_ports {mii_rxd[*] mii_rx_dv mii_rx_er}]
set_input_delay -clock mii_rx -max 31.0 [get_ports {mii_rxd[*] mii_rx_dv mii_rx_er}]
set_output_delay -clock mii_tx -max 11.0 [get_ports {mii_txd[*] mii_tx_en}]
set_output_delay -clock mii_tx -min -1.0 [get_ports {mii_txd[*] mii_tx_en}]
# Carrier/collision are asynchronous link status inputs, not packet data.
set_false_path -from [get_ports {mii_col mii_crs reset_n uartb_rxd}]
# UART TX, PHY reset and management are slow control paths.
set_false_path -to [get_ports {uartb_txd phy_reset_n mdio_mdc mdio_mdio_io}]
set_false_path -from [get_ports mdio_mdio_io]
