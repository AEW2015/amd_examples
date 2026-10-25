# SCU35 only. Run through lab.py; paths are arguments, not workstation constants.
if {[llength $argv] != 4} {error "Expected source-root build-root phase jobs"}
lassign $argv src out phase jobs
if {[version -short] ne "2026.1"} {error "Vivado 2026.1 required"}
set project [file join $out ipi sec.xpr]
if {$phase eq "hardware"} {
 if {[file exists $project]} {error "Project exists; choose a fresh build directory"}
 create_project sec [file join $out ipi] -part xcsu35p-sbvb625-2-e
 set_property target_language Verilog [current_project]
 add_files -norecurse [list [file join $src hw sec_top.v]]
 add_files -fileset constrs_1 -norecurse [list [file join $src hw sec_top.xdc]]
 import_files -norecurse [list [file join $src hw sys.bd]]
 set bd [get_files */sys.bd]
 open_bd_design $bd
 validate_bd_design
 save_bd_design
 generate_target all $bd
 set wrapper [make_wrapper -files $bd -top]
 add_files -norecurse $wrapper
 set_property top sec_top [current_fileset]
 update_compile_order -fileset sources_1
 write_hw_platform -fixed -force -file [file join $out hw.xsa]
 write_bd_tcl -force [file join $out sys.tcl]
 puts "HARDWARE_HANDOFF_PASS"
} elseif {$phase eq "image"} {
 open_project $project
 set old [get_files -quiet -filter {FILE_TYPE == ELF}]
 if {[llength $old]} {remove_files $old}
 set elf [file normalize [file join $out bench.elf]]
 add_files -norecurse $elf
 set_property SCOPED_TO_REF sys [get_files $elf]
 set_property SCOPED_TO_CELLS {mb} [get_files $elf]
 update_compile_order -fileset sources_1
 reset_run synth_1
 launch_runs synth_1 -jobs $jobs
 wait_on_run synth_1
 if {[get_property STATUS [get_runs synth_1]] ne "synth_design Complete!"} {error "Synthesis failed"}
 launch_runs impl_1 -to_step write_bitstream -jobs $jobs
 wait_on_run impl_1
 if {[get_property STATUS [get_runs impl_1]] ne "write_bitstream Complete!"} {error "Implementation failed"}
 open_run impl_1
 report_timing_summary -file [file join $out timing.txt]
 report_drc -file [file join $out drc.txt]
 report_utilization -file [file join $out utilization.txt]
 write_checkpoint -force [file join $out routed.dcp]
 write_hw_platform -fixed -force -file [file join $out hw.xsa]
 set report [open [file join $out source_bindings.txt] w]
 foreach f [get_files -all] {puts $report "[get_property FILE_TYPE $f]\t[get_property NAME $f]"}
 close $report
 puts "IMAGE_BUILD_PASS"
} else {error "Unknown phase"}
close_project
exit
