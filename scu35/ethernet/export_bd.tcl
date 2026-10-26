# Documentation export only. No synthesis, programming, or saved BD edits.
# vivado -mode batch -source export_bd.tcl -tclargs <project.xpr> <output-prefix>
if {[llength $argv] != 2} {error "Expected project.xpr and output prefix"}
lassign $argv project prefix
set prefix [file normalize $prefix]
file mkdir [file dirname $prefix]
puts "EXPORT_VERSION [version -short]"
start_gui
open_project -read_only [file normalize $project]
set designs [get_files -quiet */sys.bd]
if {[llength $designs] != 1} {error "Expected exactly one sys block design"}
open_bd_design [lindex $designs 0]
write_bd_layout -force -format svg ${prefix}.svg
write_bd_layout -force -format pdf ${prefix}.pdf
foreach extension {svg pdf} {
 set path ${prefix}.${extension}
 if {![file exists $path] || [file size $path] == 0} {error "Missing export $path"}
}
puts EXPORT_COMPLETED
close_project
exit
