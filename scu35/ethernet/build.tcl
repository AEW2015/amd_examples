# All functional hardware is AMD catalog IP in the sys IP Integrator design.
lassign $argv src out phase jobs
set src [file normalize $src]
set out [file normalize $out]
if {[version -short] ne "2026.1"} {error "Vivado 2026.1 required"}
if {$phase eq "hardware"} {
 create_project eth $out/prj -part xcsu35p-sbvb625-2-e
 set_property target_language Verilog [current_project]
 import_files -norecurse [file join $src ../hw/sys.bd]
 set bd [get_files */sys.bd]
 open_bd_design $bd
 # Replace the previous external clock wrapper with a catalog Clocking Wizard.
 set oldclock [get_bd_nets -of_objects [get_bd_ports sysclk]]
 delete_bd_objs [get_bd_ports sysclk]
 create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 clock
 set_property -dict [list CONFIG.PRIM_SOURCE Differential_clock_capable_pin CONFIG.PRIM_IN_FREQ 100 CONFIG.CLKOUT1_REQUESTED_OUT_FREQ 100 CONFIG.USE_RESET false] [get_bd_cells clock]
 puts "CLOCK_PINS [get_bd_pins clock/*]"
 create_bd_port -dir I -type clk sysclk_p
 create_bd_port -dir I sysclk_n
 set_property CONFIG.FREQ_HZ 100000000 [get_bd_ports sysclk_p]
 connect_bd_net [get_bd_ports sysclk_p] [get_bd_pins clock/clk_in1_p]
 connect_bd_net [get_bd_ports sysclk_n] [get_bd_pins clock/clk_in1_n]
 connect_bd_net -net $oldclock [get_bd_pins clock/clk_out1]
 disconnect_bd_net [get_bd_nets -of_objects [get_bd_pins rst_sysclk_100M/dcm_locked]] [get_bd_pins rst_sysclk_100M/dcm_locked]
 connect_bd_net [get_bd_pins clock/locked] [get_bd_pins rst_sysclk_100M/dcm_locked]
 # Free, vendor-supported MII MAC with independent RX/TX ping-pong BRAM.
 create_bd_cell -type ip -vlnv xilinx.com:ip:axi_ethernetlite:3.0 ethernet
 set_property -dict [list CONFIG.C_INCLUDE_MDIO 1 CONFIG.C_TX_PING_PONG 1 CONFIG.C_RX_PING_PONG 1] [get_bd_cells ethernet]
 set_property CONFIG.NUM_MI 4 [get_bd_cells axi]
 connect_bd_intf_net [get_bd_intf_pins axi/M03_AXI] [get_bd_intf_pins ethernet/S_AXI]
 connect_bd_net [get_bd_pins clock/clk_out1] [get_bd_pins ethernet/s_axi_aclk]
 connect_bd_net [get_bd_pins rst_sysclk_100M/peripheral_aresetn] [get_bd_pins ethernet/s_axi_aresetn]
 create_bd_intf_port -mode Master -vlnv xilinx.com:interface:mii_rtl:1.0 mii
 connect_bd_intf_net [get_bd_intf_ports mii] [get_bd_intf_pins ethernet/MII]
 create_bd_intf_port -mode Master -vlnv xilinx.com:interface:mdio_rtl:1.0 mdio
 connect_bd_intf_net [get_bd_intf_ports mdio] [get_bd_intf_pins ethernet/MDIO]
 create_bd_port -dir O -type rst phy_reset_n
 set_property CONFIG.POLARITY ACTIVE_LOW [get_bd_ports phy_reset_n]
 connect_bd_net [get_bd_pins ethernet/phy_rst_n] [get_bd_ports phy_reset_n]
 assign_bd_address -offset 0x40e00000 -range 0x2000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs ethernet/S_AXI/Reg] -force
 validate_bd_design
 save_bd_design
 write_bd_tcl -force $out/sys.tcl
 generate_target all $bd
 set wrapper [make_wrapper -files $bd -top]
 add_files -norecurse $wrapper
 set_property top sys_wrapper [current_fileset]
 add_files -fileset constrs_1 -norecurse [file join $src board.xdc]
 update_compile_order -fileset sources_1
 write_hw_platform -fixed -force -file $out/hw.xsa
 set f [open $out/ports.txt w];foreach p [get_bd_ports] {puts $f $p};close $f
 puts "ETH_HARDWARE_PASS"
} elseif {$phase eq "image"} {
 open_project $out/prj/eth.xpr
 set elf [file normalize $out/eth.elf]
 if {![llength [get_files -quiet $elf]]} {add_files -norecurse $elf}
 set_property SCOPED_TO_REF sys [get_files $elf]
 set_property SCOPED_TO_CELLS mb [get_files $elf]
 update_compile_order -fileset sources_1
 if {[get_property STATUS [get_runs synth_1]] ne "Not started"} {reset_run synth_1}
 launch_runs synth_1 -jobs $jobs
 wait_on_run synth_1
 if {[get_property STATUS [get_runs synth_1]] ne "synth_design Complete!"} {error "Synthesis failed"}
 launch_runs impl_1 -to_step write_bitstream -jobs $jobs
 wait_on_run impl_1
 if {[get_property STATUS [get_runs impl_1]] ne "write_bitstream Complete!"} {error "Implementation failed"}
 open_run impl_1
 foreach kind {timing_summary utilization drc cdc clock_interaction route_status io} {
  report_$kind -file $out/$kind.txt
 }
 check_timing -verbose -file $out/check_timing.txt
 write_checkpoint -force $out/routed.dcp
 write_hw_platform -fixed -include_bit -force -file $out/hw.xsa
 set impl [get_property DIRECTORY [get_runs impl_1]]
 file copy -force $impl/sys_wrapper.pdi $out/ethernet.pdi
 file copy -force $impl/sys_wrapper.rcdo $out/design.rcdo
 file copy -force $impl/static_files/plm.elf $out/plm.elf
 puts "ETH_IMAGE_PASS"
} else {error "Unknown phase"}
close_project
exit
