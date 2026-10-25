lassign $argv base run_dir
if {[file exists $run_dir]} {error "Fresh fixture output required"}
if {[version -short] ne "2026.1"} {error "2026.1 required"}
file mkdir $run_dir
file mkdir [file join $run_dir reports]
create_project cf $run_dir -part xcsu35p-sbvb625-2-e
set_property target_language Verilog [current_project]
add_files [list [file join $base rtl top.v]]
add_files [list [file join $base rtl reference_writer.v]]
add_files -fileset constrs_1 [list [file join $base constraints scu35.xdc]]
add_files -fileset constrs_1 [list [file join $base constraints cdc.xdc]]
set_property used_in_synthesis false [get_files cdc.xdc]
create_bd_design clock_fixture_bd
set clk [create_bd_port -dir I -type clk -freq_hz 100000000 clk100]
set_property CONFIG.FREQ_HZ 100000000 $clk
set cfgclk [create_bd_port -dir I -type clk -freq_hz 200000000 cfgclk]
set_property CONFIG.FREQ_HZ 200000000 $cfgclk
create_bd_cell -type ip -vlnv xilinx.com:ip:jtag_axi:1.2 jtag_axi_0
set_property -dict [list CONFIG.PROTOCOL 0 CONFIG.M_AXI_DATA_WIDTH 32 CONFIG.M_AXI_ADDR_WIDTH 32] [get_bd_cells jtag_axi_0]
create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 smartconnect_0
set_property -dict [list CONFIG.NUM_SI 2 CONFIG.NUM_MI 1] [get_bd_cells smartconnect_0]
create_bd_cell -type ip -vlnv xilinx.com:ip:pmcbridge:1.0 pmcbridge_0
create_bd_cell -type module -reference reference_writer reference_writer_0
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 reset_0
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 zero_0
set_property CONFIG.CONST_VAL 0 [get_bd_cells zero_0]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 one_0
set_property CONFIG.CONST_VAL 1 [get_bd_cells one_0]
connect_bd_net $clk [get_bd_pins jtag_axi_0/aclk] [get_bd_pins smartconnect_0/aclk] [get_bd_pins pmcbridge_0/S_AXI_clk] [get_bd_pins reset_0/slowest_sync_clk] [get_bd_pins reference_writer_0/clk100]
connect_bd_net $cfgclk [get_bd_pins reference_writer_0/cfgclk]
connect_bd_net [get_bd_pins zero_0/dout] [get_bd_pins reset_0/mb_debug_sys_rst]
connect_bd_net [get_bd_pins one_0/dout] [get_bd_pins reset_0/ext_reset_in] [get_bd_pins reset_0/aux_reset_in] [get_bd_pins reset_0/dcm_locked]
connect_bd_net [get_bd_pins reset_0/peripheral_aresetn] [get_bd_pins jtag_axi_0/aresetn] [get_bd_pins smartconnect_0/aresetn] [get_bd_pins reference_writer_0/resetn]
connect_bd_intf_net [get_bd_intf_pins jtag_axi_0/M_AXI] [get_bd_intf_pins smartconnect_0/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins reference_writer_0/M_AXI] [get_bd_intf_pins smartconnect_0/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M00_AXI] [get_bd_intf_pins pmcbridge_0/S_AXI]
assign_bd_address
validate_bd_design
save_bd_design
write_bd_tcl -force [file join $run_dir clock_fixture_bd.tcl]
generate_target all [get_files clock_fixture_bd.bd]
set_property top top [current_fileset]
update_compile_order -fileset sources_1
launch_runs synth_1 -jobs 2
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis failed"}
launch_runs impl_1 -to_step write_bitstream -jobs 2
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Implementation/PDI generation failed"}
open_run impl_1
if {[llength [get_cells -hierarchical -filter {NAME =~ *cfg_gray_count_reg* && REF_NAME =~ FD*}]] != 32 || [llength [get_cells -hierarchical -filter {NAME =~ *cfg_gray_meta_reg* && REF_NAME =~ FD*}]] != 32} {error "CFGCLK CDC counter/synchronizer missing"}
report_timing_summary -file [file join $run_dir reports timing_summary.rpt]
report_drc -file [file join $run_dir reports drc.rpt]
report_cdc -file [file join $run_dir reports cdc.rpt]
report_bus_skew -file [file join $run_dir reports bus_skew.rpt]
report_utilization -file [file join $run_dir reports utilization.rpt]
report_route_status -file [file join $run_dir reports route_status.rpt]
write_checkpoint -force [file join $run_dir top_routed.dcp]
write_hw_platform -fixed -include_bit -force -file [file join $run_dir fixture.xsa]
puts "PMC_CLOCK_FIXTURE_BUILD_COMPLETE"

close_design
file copy -force [file join $run_dir cf.runs impl_1 top.rcdo] [file join $run_dir design.rcdo]
file copy -force [file join $run_dir cf.runs impl_1 static_files plm.elf] [file join $run_dir plm.elf]
close_project
exit
