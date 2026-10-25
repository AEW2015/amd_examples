# Only the explicitly synchronized Gray crossing receives this asynchronous
# timing bound. Register cells provide valid startpoints without segmentation.
set cfg_gray_src [get_cells -hierarchical -filter {NAME =~ *cfg_gray_count_reg*}]
set cfg_gray_meta [get_cells -hierarchical -filter {NAME =~ *cfg_gray_meta_reg*}]
set_max_delay -datapath_only 5.000 -from $cfg_gray_src -to $cfg_gray_meta
set_bus_skew 5.000 -from $cfg_gray_src -to $cfg_gray_meta
set_false_path -to [get_pins -hierarchical -filter {NAME =~ *cfg_reset_pipe_reg*/D}]
set_false_path -to [get_pins -hierarchical -filter {REF_PIN_NAME == CLR && NAME =~ *reference_writer_0*}]
