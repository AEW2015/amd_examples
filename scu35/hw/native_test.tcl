# Native PMC monitor RPC; JTAG readout is outside all firmware timing intervals.
lassign $argv pdi attempt seedlo seedhi server cable restore_pdi
if {![regexp {^[A-Za-z0-9]+$} $cable]} {error "Exact cable serial required"}
set result [open $attempt/results.txt w]
proc note {s} {global result;puts $s;puts $result $s;flush $result}
proc burst_read {address count} {
 global axi
 create_hw_axi_txn rd $axi -type READ -address [format %08x $address] -len $count -force
 run_hw_axi [get_hw_axi_txns rd]
 return [get_property DATA [get_hw_axi_txns rd]]
}
proc rd {address {count 1}} {
 # The PMC bridge accepts at most 16 beats per AXI burst.
 set data ""
 for {set offset 0} {$offset<$count} {incr offset 16} {
  set n [expr {min(16,$count-$offset)}]
  set data "[burst_read [expr {$address+4*$offset}] $n]$data"
 }
 return $data
}
proc wr {address value} {
 global axi
 create_hw_axi_txn wr $axi -type WRITE -address [format %08x $address] -len 1 -data [format %08x $value] -force
 run_hw_axi [get_hw_axi_txns wr]
}
proc rpc {op address count reps {lo 0} {hi 0}} {
 global seq
 wr 0x04029110 $op;wr 0x04029114 $address;wr 0x04029118 $count
 wr 0x04029140 $reps;wr 0x04029144 $lo;wr 0x04029148 $hi
 incr seq;wr 0x04029108 $seq
 set done 0
 for {set i 0} {$i<1000} {incr i} {
  if {[scan [rd 0x0402910c] %x]==$seq} {set done 1;break}
  after 10
 }
 if {!$done} {error "RPC timeout op=$op"}
 set faults [scan [rd 0x0402911c] %x]
 set data [rd 0x04029140 32]
 if {$faults!=0} {note "FAILED_RPC op=$op kind=$address bytes=$count faults=$faults data=$data";error "Firmware rejected test"}
 return $data
}
set failed 0;set armed 0;set seq 0
open_hw_manager
connect_hw_server -url $server
try {
 set targets [get_hw_targets -quiet */Xilinx/$cable]
 if {[llength $targets]!=1} {error "Exact cable unavailable"}
 current_hw_target [lindex $targets 0];open_hw_target
 set devices [get_hw_devices -quiet]
 if {[llength $devices]!=1} {error "Expected exactly one device"}
 set dev [lindex $devices 0]
 if {[get_property PART $dev] ne "xcsu35p"||[string tolower [get_property IDCODE_HEX $dev]] ne "04e80093"} {error "Target mismatch"}
 set armed 1;set_property PROGRAM.FILE $pdi $dev;program_hw_devices $dev;refresh_hw_device $dev
 set done [get_property {REGISTER.JTAG_STATUS.BIT[34]_DONE} $dev]
 set errors [get_property REGISTER.ERROR_STATUS $dev]
 note "PROGRAM DONE=$done ERROR=$errors"
 if {$done!=1||[scan $errors %x]!=0} {error "Configuration status failed"}
 set axes [get_hw_axis -of_objects $dev]
 if {[llength $axes]!=1} {error "Expected one matching JTAG AXI fixture"}
 set axi [lindex $axes 0];reset_hw_axi $axi
 if {[scan [rd 0x04029100] %x]!=0x504d434d||[scan [rd 0x04029104] %x]!=2} {error "Monitor not ready"}
 note "TARGET cable=$cable idcode=04e80093"
 note "DIVIDERS PMC=[rd 0x040a0030] CCU=[rd 0x040a0034]"
 note "RAM_CONTROL data=[rpc 5 3 8192 10]"
 note "AES_KAT data=[rpc 9 0 0 0]"
 foreach bytes {0 1 3 4 55 86 110 136 137 4278} {
  note "SHAKE_KAT bytes=$bytes data=[rpc 32 0 $bytes 0]"
 }
 for {set s 0} {$s<5} {incr s} {note "CLOCK sample=$s data=[rpc 6 0 100 0]"}
 set nonce 0
 foreach kind {1 2 3 4 5} {
  set sizes {16 256 2048 8192}
  if {$kind<3} {lappend sizes 65536 1048576}
  if {$kind==5} {set sizes {65536 1048576}}
  foreach bytes $sizes {
   set reps 200
   if {$bytes<=8192} {set reps 1000}
   for {set sample 0} {$sample<3} {incr sample} {
    incr nonce
    set data [rpc 30 $kind $bytes $reps [expr {($seedlo+$nonce)&0xffffffff}] $seedhi]
    note "FAST kind=$kind bytes=$bytes repeats=$reps sample=$sample data=$data"
    if {$kind>=3} {
     set captured [expr {min(8192,$bytes)}]
     for {set offset 0} {$offset<$captured} {incr offset 512} {
      set remain [expr {$captured-$offset}]
      set count [expr {$remain>=512?128:$remain/4}]
      note "CIPHER kind=$kind bytes=$bytes sample=$sample offset=$offset data=[rd [expr {0x0402c000+$offset}] $count]"
     }
    }
   }
  }
 }
 source $attempt/pq_upload.tcl
 foreach kind {6 7} {
  foreach record [dict get $pq_upload $kind] {
   lassign $record address count data
   create_hw_axi_txn pq_upload_txn $axi -type WRITE -address $address -len $count -data $data -force
   run_hw_axi [get_hw_axi_txns pq_upload_txn]
   scan $address %x addr
   if {[string tolower [rd $addr $count]] ne [string tolower $data]} {error "Public vector upload mismatch"}
  }
  note "PQ_VECTOR kind=$kind UPLOAD_VERIFIED=YES"
  foreach case {0 1 2 3} {
   for {set sample 0} {$sample<3} {incr sample} {
    note "PQ kind=$kind case=$case sample=$sample data=[rpc 31 $kind $case 20]"
   }
  }
  foreach case {4 5 6} {note "PQ_GUARD kind=$kind case=$case data=[rpc 31 $kind $case 1]"}
 }
 note "SUITE_PASS=YES"
} on error {message options} {
 set failed 1;note "TEST_ERROR $message"
} finally {
 if {$armed} {
  set restore [catch {
   set_property PROGRAM.FILE $restore_pdi $dev
   program_hw_devices $dev;refresh_hw_device $dev
   set done [get_property {REGISTER.JTAG_STATUS.BIT[34]_DONE} $dev]
   set errors [get_property REGISTER.ERROR_STATUS $dev]
   note "RESTORED DONE=$done ERROR=$errors"
   if {$done!=1||[scan $errors %x]!=0} {error "Stock readback failed"}
  } message]
  if {$restore} {set failed 1;note "RECOVERY_ERROR $message"}
 }
 close $result
 catch {close_hw_target};catch {disconnect_hw_server};catch {close_hw_manager}
}
if {$failed} {exit 1}

puts "PROGRAM_CHECK_PASS"
