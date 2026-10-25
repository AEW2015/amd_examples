set_property PACKAGE_PIN F23 [get_ports sysclk_p]
set_property PACKAGE_PIN E23 [get_ports sysclk_n]
set_property IOSTANDARD LVDS [get_ports {sysclk_p sysclk_n}]
create_clock -name sysclk -period 10.000 [get_ports sysclk_p]

# STARTUPE3 CFGCLK is asynchronous to the board SYSCLK. Constrain it
# conservatively; the source is configuration logic, not a user-set divider.
create_clock -name cfgclk -period 5.000 [get_pins -hierarchical -filter {NAME =~ *startupe3_cfg/CFGCLK}]
