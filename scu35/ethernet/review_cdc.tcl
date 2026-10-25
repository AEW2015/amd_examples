# Explicit post-route inspection. This does not program hardware or waive CDC.
lassign $argv out
open_checkpoint [file join $out routed.dcp]
report_cdc -details -file [file join $out cdc_details.txt]
report_exceptions -coverage -file [file join $out exceptions.txt]
exit
