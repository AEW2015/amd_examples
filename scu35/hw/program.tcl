# Volatile SCU35 configuration only; never invokes flash or eFUSE programming.
lassign $argv server cable pdi expected
if {![regexp {^[A-Za-z0-9]+$} $cable]} {error "Invalid exact cable serial"}
try {
 open_hw_manager
 connect_hw_server -url $server
 set targets [get_hw_targets -quiet */Xilinx/$cable]
 if {[llength $targets]!=1} {error "Exact SCU35 cable unavailable"}
 current_hw_target [lindex $targets 0]
 open_hw_target
 set devices [get_hw_devices -quiet]
 if {[llength $devices]!=1} {error "Expected one device on the selected cable"}
 set dev [lindex $devices 0]
 if {[get_property PART $dev] ne "xcsu35p" || [string tolower [get_property IDCODE_HEX $dev]] ne "04e80093"} {error "SCU35 target mismatch"}
 set_property PROGRAM.FILE [file normalize $pdi] $dev
 set programmed [catch {program_hw_devices $dev} message]
 refresh_hw_device $dev
 set done [get_property {REGISTER.JTAG_STATUS.BIT[34]_DONE} $dev]
 set errors [get_property REGISTER.ERROR_STATUS $dev]
 puts "DEVICE_STATUS DONE=$done ERROR=$errors"
 if {$expected eq "reject"} {
  if {$done!=0 || [scan $errors %x]==0} {error "Expected a rejected configuration"}
 } else {
  if {$programmed || $done!=1 || [scan $errors %x]!=0} {error "Configuration failed: $message"}
 }
 puts "PROGRAM_CHECK_PASS"
} finally {
 catch {close_hw_target};catch {disconnect_hw_server};catch {close_hw_manager}
}
