# Documentation export only: no synthesis, hardware, or saved BD changes.
puts "EXPORT_VERSION [version -short]"
start_gui
open_project -read_only C:/aiup/s35cmp/cmp.xpr
open_bd_design C:/aiup/s35cmp/cmp.srcs/sources_1/bd/sys/sys.bd
write_bd_layout -force -format svg C:/aiup/docs/pmc/presenter/assets/sys_vivado.svg
write_bd_layout -force -format pdf C:/aiup/docs/pmc/presenter/assets/sys_vivado.pdf
foreach output {sys_vivado.svg sys_vivado.pdf} {
    set output_path C:/aiup/docs/pmc/presenter/assets/$output
    if {![file exists $output_path] || [file size $output_path] == 0} {error "Missing export: $output_path"}
}
puts "EXPORT_COMPLETED"
close_project
exit
