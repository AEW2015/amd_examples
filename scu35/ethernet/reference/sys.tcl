
################################################################
# This is a generated script based on design: sys
#
# Though there are limitations about the generated script,
# the main purpose of this utility is to make learning
# IP Integrator Tcl commands easier.
################################################################

namespace eval _tcl {
proc get_script_folder {} {
   set script_path [file normalize [info script]]
   set script_folder [file dirname $script_path]
   return $script_folder
}
}
variable script_folder
set script_folder [_tcl::get_script_folder]

################################################################
# Check if script is running in correct Vivado version.
################################################################
set scripts_vivado_version 2026.1
set current_vivado_version [version -short]

if { [string first $scripts_vivado_version $current_vivado_version] == -1 } {
   puts ""
   if { [string compare $scripts_vivado_version $current_vivado_version] > 0 } {
      catch {common::send_gid_msg -ssname BD::TCL -id 2042 -severity "ERROR" " This script was generated using Vivado <$scripts_vivado_version> and is being run in <$current_vivado_version> of Vivado. Sourcing the script failed since it was created with a future version of Vivado."}

   } else {
     catch {common::send_gid_msg -ssname BD::TCL -id 2041 -severity "ERROR" "This script was generated using Vivado <$scripts_vivado_version> and is being run in <$current_vivado_version> of Vivado. Please run the script in Vivado <$scripts_vivado_version> then open the design in Vivado <$current_vivado_version>. Upgrade the design by running \"Tools => Report => Report IP Status...\", then run write_bd_tcl to create an updated script."}

   }

   return 1
}

################################################################
# START
################################################################

# To test this script, run the following commands from Vivado Tcl console:
# source sys_script.tcl

# If there is no project opened, this script will create a
# project, but make sure you do not have an existing project
# <./myproj/project_1.xpr> in the current working folder.

set list_projs [get_projects -quiet]
if { $list_projs eq "" } {
   create_project project_1 myproj -part xcsu35p-sbvb625-2-e
}


# CHANGE DESIGN NAME HERE
variable design_name
set design_name sys

# If you do not already have an existing IP Integrator design open,
# you can create a design using the following command:
#    create_bd_design $design_name

# Creating design if needed
set errMsg ""
set nRet 0

set cur_design [current_bd_design -quiet]
set list_cells [get_bd_cells -quiet]

if { ${design_name} eq "" } {
   # USE CASES:
   #    1) Design_name not set

   set errMsg "Please set the variable <design_name> to a non-empty value."
   set nRet 1

} elseif { ${cur_design} ne "" && ${list_cells} eq "" } {
   # USE CASES:
   #    2): Current design opened AND is empty AND names same.
   #    3): Current design opened AND is empty AND names diff; design_name NOT in project.
   #    4): Current design opened AND is empty AND names diff; design_name exists in project.

   if { $cur_design ne $design_name } {
      common::send_gid_msg -ssname BD::TCL -id 2001 -severity "INFO" "Changing value of <design_name> from <$design_name> to <$cur_design> since current design is empty."
      set design_name [get_property NAME $cur_design]
   }
   common::send_gid_msg -ssname BD::TCL -id 2002 -severity "INFO" "Constructing design in IPI design <$cur_design>..."

} elseif { ${cur_design} ne "" && $list_cells ne "" && $cur_design eq $design_name } {
   # USE CASES:
   #    5) Current design opened AND has components AND same names.

   set errMsg "Design <$design_name> already exists in your project, please set the variable <design_name> to another value."
   set nRet 1
} elseif { [get_files -quiet ${design_name}.bd] ne "" } {
   # USE CASES: 
   #    6) Current opened design, has components, but diff names, design_name exists in project.
   #    7) No opened design, design_name exists in project.

   set errMsg "Design <$design_name> already exists in your project, please set the variable <design_name> to another value."
   set nRet 2

} else {
   # USE CASES:
   #    8) No opened design, design_name not in project.
   #    9) Current opened design, has components, but diff names, design_name not in project.

   common::send_gid_msg -ssname BD::TCL -id 2003 -severity "INFO" "Currently there is no design <$design_name> in project, so creating one..."

   create_bd_design $design_name

   common::send_gid_msg -ssname BD::TCL -id 2004 -severity "INFO" "Making design <$design_name> as current_bd_design."
   current_bd_design $design_name

}

common::send_gid_msg -ssname BD::TCL -id 2005 -severity "INFO" "Currently the variable <design_name> is equal to \"$design_name\"."

if { $nRet != 0 } {
   catch {common::send_gid_msg -ssname BD::TCL -id 2006 -severity "ERROR" $errMsg}
   return $nRet
}

set bCheckIPsPassed 1
##################################################################
# CHECK IPs
##################################################################
set bCheckIPs 1
if { $bCheckIPs == 1 } {
   set list_check_ips "\ 
xilinx.com:ip:microblaze_riscv:1.0\
xilinx.com:ip:mdm_riscv:1.0\
xilinx.com:ip:proc_sys_reset:5.0\
xilinx.com:ip:xlconstant:1.1\
xilinx.com:ip:smartconnect:1.0\
xilinx.com:ip:axi_uartlite:2.0\
xilinx.com:ip:pmcbridge:1.0\
xilinx.com:ip:axi_timer:2.0\
xilinx.com:ip:clk_wiz:6.0\
xilinx.com:ip:axi_ethernetlite:3.0\
xilinx.com:ip:lmb_v10:3.0\
xilinx.com:ip:lmb_bram_if_cntlr:4.0\
xilinx.com:ip:blk_mem_gen:8.4\
"

   set list_ips_missing ""
   common::send_gid_msg -ssname BD::TCL -id 2011 -severity "INFO" "Checking if the following IPs exist in the project's IP catalog: $list_check_ips ."

   foreach ip_vlnv $list_check_ips {
      set ip_obj [get_ipdefs -all $ip_vlnv]
      if { $ip_obj eq "" } {
         lappend list_ips_missing $ip_vlnv
      }
   }

   if { $list_ips_missing ne "" } {
      catch {common::send_gid_msg -ssname BD::TCL -id 2012 -severity "ERROR" "The following IPs are not found in the IP Catalog:\n  $list_ips_missing\n\nResolution: Please add the repository containing the IP(s) to the project." }
      set bCheckIPsPassed 0
   }

}

if { $bCheckIPsPassed != 1 } {
  common::send_gid_msg -ssname BD::TCL -id 2023 -severity "WARNING" "Will not continue with creation of design due to the error(s) above."
  return 3
}

##################################################################
# DESIGN PROCs
##################################################################


# Hierarchical cell: mb_local_memory
proc create_hier_cell_mb_local_memory { parentCell nameHier } {

  variable script_folder

  if { $parentCell eq "" || $nameHier eq "" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2092 -severity "ERROR" "create_hier_cell_mb_local_memory() - Empty argument(s)!"}
     return
  }

  # Get object for parentCell
  set parentObj [get_bd_cells $parentCell]
  if { $parentObj == "" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2090 -severity "ERROR" "Unable to find parent cell <$parentCell>!"}
     return
  }

  # Make sure parentObj is hier blk
  set parentType [get_property TYPE $parentObj]
  if { $parentType ne "hier" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2091 -severity "ERROR" "Parent <$parentObj> has TYPE = <$parentType>. Expected to be <hier>."}
     return
  }

  # Save current instance; Restore later
  set oldCurInst [current_bd_instance .]

  # Set parent object as current
  current_bd_instance $parentObj

  # Create cell and set as current instance
  set hier_obj [create_bd_cell -type hier $nameHier]
  current_bd_instance $hier_obj

  # Create interface pins
  create_bd_intf_pin -mode MirroredMaster -vlnv xilinx.com:interface:lmb_rtl:1.0 DLMB

  create_bd_intf_pin -mode MirroredMaster -vlnv xilinx.com:interface:lmb_rtl:1.0 ILMB


  # Create pins
  create_bd_pin -dir I -type clk sysclk
  create_bd_pin -dir I -type rst SYS_Rst

  # Create instance: dlmb_v10, and set properties
  set dlmb_v10 [ create_bd_cell -type ip -vlnv xilinx.com:ip:lmb_v10:3.0 dlmb_v10 ]

  # Create instance: ilmb_v10, and set properties
  set ilmb_v10 [ create_bd_cell -type ip -vlnv xilinx.com:ip:lmb_v10:3.0 ilmb_v10 ]

  # Create instance: dlmb_bram_if_cntlr, and set properties
  set dlmb_bram_if_cntlr [ create_bd_cell -type ip -vlnv xilinx.com:ip:lmb_bram_if_cntlr:4.0 dlmb_bram_if_cntlr ]
  set_property CONFIG.C_ECC {0} $dlmb_bram_if_cntlr


  # Create instance: ilmb_bram_if_cntlr, and set properties
  set ilmb_bram_if_cntlr [ create_bd_cell -type ip -vlnv xilinx.com:ip:lmb_bram_if_cntlr:4.0 ilmb_bram_if_cntlr ]
  set_property CONFIG.C_ECC {0} $ilmb_bram_if_cntlr


  # Create instance: lmb_bram, and set properties
  set lmb_bram [ create_bd_cell -type ip -vlnv xilinx.com:ip:blk_mem_gen:8.4 lmb_bram ]
  set_property -dict [list \
    CONFIG.Memory_Type {True_Dual_Port_RAM} \
    CONFIG.use_bram_block {BRAM_Controller} \
  ] $lmb_bram


  # Create interface connections
  connect_bd_intf_net -intf_net mb_dlmb [get_bd_intf_pins dlmb_v10/LMB_M] [get_bd_intf_pins DLMB]
  connect_bd_intf_net -intf_net mb_dlmb_bus [get_bd_intf_pins dlmb_v10/LMB_Sl_0] [get_bd_intf_pins dlmb_bram_if_cntlr/SLMB]
  connect_bd_intf_net -intf_net mb_dlmb_cntlr [get_bd_intf_pins dlmb_bram_if_cntlr/BRAM_PORT] [get_bd_intf_pins lmb_bram/BRAM_PORTA]
  connect_bd_intf_net -intf_net mb_ilmb [get_bd_intf_pins ilmb_v10/LMB_M] [get_bd_intf_pins ILMB]
  connect_bd_intf_net -intf_net mb_ilmb_bus [get_bd_intf_pins ilmb_v10/LMB_Sl_0] [get_bd_intf_pins ilmb_bram_if_cntlr/SLMB]
  connect_bd_intf_net -intf_net mb_ilmb_cntlr [get_bd_intf_pins ilmb_bram_if_cntlr/BRAM_PORT] [get_bd_intf_pins lmb_bram/BRAM_PORTB]

  # Create port connections
  connect_bd_net -net SYS_Rst_1  [get_bd_pins SYS_Rst] \
  [get_bd_pins dlmb_v10/SYS_Rst] \
  [get_bd_pins dlmb_bram_if_cntlr/LMB_Rst] \
  [get_bd_pins ilmb_v10/SYS_Rst] \
  [get_bd_pins ilmb_bram_if_cntlr/LMB_Rst]
  connect_bd_net -net mb_Clk  [get_bd_pins sysclk] \
  [get_bd_pins dlmb_v10/LMB_Clk] \
  [get_bd_pins dlmb_bram_if_cntlr/LMB_Clk] \
  [get_bd_pins ilmb_v10/LMB_Clk] \
  [get_bd_pins ilmb_bram_if_cntlr/LMB_Clk]

  # Restore current instance
  current_bd_instance $oldCurInst
}


# Procedure to create entire design; Provide argument to make
# procedure reusable. If parentCell is "", will use root.
proc create_root_design { parentCell } {

  variable script_folder
  variable design_name

  if { $parentCell eq "" } {
     set parentCell [get_bd_cells /]
  }

  # Get object for parentCell
  set parentObj [get_bd_cells $parentCell]
  if { $parentObj == "" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2090 -severity "ERROR" "Unable to find parent cell <$parentCell>!"}
     return
  }

  # Make sure parentObj is hier blk
  set parentType [get_property TYPE $parentObj]
  if { $parentType ne "hier" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2091 -severity "ERROR" "Parent <$parentObj> has TYPE = <$parentType>. Expected to be <hier>."}
     return
  }

  # Save current instance; Restore later
  set oldCurInst [current_bd_instance .]

  # Set parent object as current
  current_bd_instance $parentObj


  # Create interface ports
  set uartb [ create_bd_intf_port -mode Master -vlnv xilinx.com:interface:uart_rtl:1.0 uartb ]

  set mii [ create_bd_intf_port -mode Master -vlnv xilinx.com:interface:mii_rtl:1.0 mii ]

  set mdio [ create_bd_intf_port -mode Master -vlnv xilinx.com:interface:mdio_rtl:1.0 mdio ]


  # Create ports
  set reset_n [ create_bd_port -dir I -type rst reset_n ]
  set_property -dict [ list \
   CONFIG.POLARITY {ACTIVE_LOW} \
 ] $reset_n
  set sysclk_p [ create_bd_port -dir I -type clk -freq_hz 100000000 sysclk_p ]
  set sysclk_n [ create_bd_port -dir I sysclk_n ]
  set phy_reset_n [ create_bd_port -dir O -type rst phy_reset_n ]
  set_property -dict [ list \
   CONFIG.POLARITY {ACTIVE_LOW} \
 ] $phy_reset_n

  # Create instance: mb, and set properties
  set mb [ create_bd_cell -type ip -vlnv xilinx.com:ip:microblaze_riscv:1.0 mb ]
  set_property -dict [list \
    CONFIG.C_DEBUG_ENABLED {1} \
    CONFIG.C_D_AXI {1} \
    CONFIG.C_D_LMB {1} \
    CONFIG.C_I_LMB {1} \
  ] $mb


  # Create instance: mb_local_memory
  create_hier_cell_mb_local_memory [current_bd_instance .] mb_local_memory

  # Create instance: mdm_1, and set properties
  set mdm_1 [ create_bd_cell -type ip -vlnv xilinx.com:ip:mdm_riscv:1.0 mdm_1 ]

  # Create instance: rst_sysclk_100M, and set properties
  set rst_sysclk_100M [ create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_sysclk_100M ]

  # Create instance: low, and set properties
  set low [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 low ]
  set_property CONFIG.CONST_VAL {0} $low


  # Create instance: high, and set properties
  set high [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 high ]
  set_property CONFIG.CONST_VAL {1} $high


  # Create instance: axi, and set properties
  set axi [ create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 axi ]
  set_property -dict [list \
    CONFIG.NUM_MI {4} \
    CONFIG.NUM_SI {1} \
  ] $axi


  # Create instance: uart, and set properties
  set uart [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_uartlite:2.0 uart ]
  set_property -dict [list \
    CONFIG.C_BAUDRATE {115200} \
    CONFIG.C_S_AXI_ACLK_FREQ_HZ {100000000} \
  ] $uart


  # Create instance: pmc, and set properties
  set pmc [ create_bd_cell -type ip -vlnv xilinx.com:ip:pmcbridge:1.0 pmc ]

  # Create instance: timer, and set properties
  set timer [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_timer:2.0 timer ]

  # Create instance: clock, and set properties
  set clock [ create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 clock ]
  set_property -dict [list \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {100} \
    CONFIG.PRIM_IN_FREQ {100} \
    CONFIG.PRIM_SOURCE {Differential_clock_capable_pin} \
    CONFIG.USE_RESET {false} \
  ] $clock


  # Create instance: ethernet, and set properties
  set ethernet [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_ethernetlite:3.0 ethernet ]
  set_property -dict [list \
    CONFIG.C_INCLUDE_MDIO {1} \
    CONFIG.C_RX_PING_PONG {1} \
    CONFIG.C_TX_PING_PONG {1} \
  ] $ethernet


  # Create interface connections
  connect_bd_intf_net -intf_net axi_M00_AXI [get_bd_intf_pins axi/M00_AXI] [get_bd_intf_pins uart/S_AXI]
  connect_bd_intf_net -intf_net axi_M01_AXI [get_bd_intf_pins axi/M01_AXI] [get_bd_intf_pins pmc/S_AXI]
  connect_bd_intf_net -intf_net axi_M02_AXI [get_bd_intf_pins axi/M02_AXI] [get_bd_intf_pins timer/S_AXI]
  connect_bd_intf_net -intf_net axi_M03_AXI [get_bd_intf_pins axi/M03_AXI] [get_bd_intf_pins ethernet/S_AXI]
  connect_bd_intf_net -intf_net ethernet_MDIO [get_bd_intf_ports mdio] [get_bd_intf_pins ethernet/MDIO]
  connect_bd_intf_net -intf_net ethernet_MII [get_bd_intf_ports mii] [get_bd_intf_pins ethernet/MII]
  connect_bd_intf_net -intf_net mb_M_AXI_DP [get_bd_intf_pins mb/M_AXI_DP] [get_bd_intf_pins axi/S00_AXI]
  connect_bd_intf_net -intf_net mb_debug [get_bd_intf_pins mdm_1/MBDEBUG_0] [get_bd_intf_pins mb/DEBUG]
  connect_bd_intf_net -intf_net mb_dlmb_1 [get_bd_intf_pins mb/DLMB] [get_bd_intf_pins mb_local_memory/DLMB]
  connect_bd_intf_net -intf_net mb_ilmb_1 [get_bd_intf_pins mb/ILMB] [get_bd_intf_pins mb_local_memory/ILMB]
  connect_bd_intf_net -intf_net uart_UART [get_bd_intf_ports uartb] [get_bd_intf_pins uart/UART]

  # Create port connections
  connect_bd_net -net clock_locked  [get_bd_pins clock/locked] \
  [get_bd_pins rst_sysclk_100M/dcm_locked]
  connect_bd_net -net ethernet_phy_rst_n  [get_bd_pins ethernet/phy_rst_n] \
  [get_bd_ports phy_reset_n]
  connect_bd_net -net high_dout  [get_bd_pins high/dout] \
  [get_bd_pins rst_sysclk_100M/aux_reset_in]
  connect_bd_net -net low_dout  [get_bd_pins low/dout] \
  [get_bd_pins timer/capturetrig0] \
  [get_bd_pins timer/capturetrig1] \
  [get_bd_pins timer/freeze]
  connect_bd_net -net mb_Clk  [get_bd_pins clock/clk_out1] \
  [get_bd_pins mb/Clk] \
  [get_bd_pins mb_local_memory/sysclk] \
  [get_bd_pins rst_sysclk_100M/slowest_sync_clk] \
  [get_bd_pins axi/aclk] \
  [get_bd_pins uart/s_axi_aclk] \
  [get_bd_pins pmc/S_AXI_clk] \
  [get_bd_pins timer/s_axi_aclk] \
  [get_bd_pins ethernet/s_axi_aclk]
  connect_bd_net -net mdm_1_debug_sys_rst  [get_bd_pins mdm_1/Debug_SYS_Rst] \
  [get_bd_pins rst_sysclk_100M/mb_debug_sys_rst]
  connect_bd_net -net reset_n_1  [get_bd_ports reset_n] \
  [get_bd_pins rst_sysclk_100M/ext_reset_in]
  connect_bd_net -net rst_sysclk_100M_bus_struct_reset  [get_bd_pins rst_sysclk_100M/bus_struct_reset] \
  [get_bd_pins mb_local_memory/SYS_Rst]
  connect_bd_net -net rst_sysclk_100M_mb_reset  [get_bd_pins rst_sysclk_100M/mb_reset] \
  [get_bd_pins mb/Reset]
  connect_bd_net -net rst_sysclk_100M_peripheral_aresetn  [get_bd_pins rst_sysclk_100M/peripheral_aresetn] \
  [get_bd_pins axi/aresetn] \
  [get_bd_pins uart/s_axi_aresetn] \
  [get_bd_pins timer/s_axi_aresetn] \
  [get_bd_pins ethernet/s_axi_aresetn]
  connect_bd_net -net sysclk_n_1  [get_bd_ports sysclk_n] \
  [get_bd_pins clock/clk_in1_n]
  connect_bd_net -net sysclk_p_1  [get_bd_ports sysclk_p] \
  [get_bd_pins clock/clk_in1_p]

  # Create address segments
  assign_bd_address -offset 0x00000000 -range 0x00020000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs mb_local_memory/dlmb_bram_if_cntlr/SLMB/Mem] -force
  assign_bd_address -offset 0x40E00000 -range 0x00002000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs ethernet/S_AXI/Reg] -force
  assign_bd_address -offset 0x04130000 -range 0x00010000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/CCU_APB/ccu_apb_0] -force
  assign_bd_address -offset 0x04060000 -range 0x00010000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/CCU_RD_STREAM/ccu_rd_stream_0] -force
  assign_bd_address -offset 0x04070000 -range 0x00010000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/CCU_WR_STREAM/ccu_wr_stream_0] -force
  assign_bd_address -offset 0x04020000 -range 0x00010000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/PLM_CONFIG/plm_config_0] -force
  assign_bd_address -offset 0x040F0000 -range 0x00010000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/PMC_AES/pmcl_aes_0] -force
  assign_bd_address -offset 0x040E0000 -range 0x00010000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/PMCL_DMA/pmcl_dma_0] -force
  assign_bd_address -offset 0x04160000 -range 0x00010000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/PMCL_EFUSE/pmcl_efuse_0] -force
  assign_bd_address -offset 0x040A0000 -range 0x00020000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/PMCL_GLOBAL/pmcl_global_0] -force
  assign_bd_address -offset 0x04090000 -range 0x00010000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/PMCL_OSPI/pmcl_ospi_0] -force
  assign_bd_address -offset 0x04080000 -range 0x00010000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/PMCL_PUF/pmcl_puf_0] -force
  assign_bd_address -offset 0x04100000 -range 0x00010000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/PMCL_SHA3/pmcl_sha3_0] -force
  assign_bd_address -offset 0x04110000 -range 0x00010000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/PMCL_SLAVE_BOOT/pmcl_slave_boot_0] -force
  assign_bd_address -offset 0x040C0000 -range 0x00020000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/PMCL_TAP/pmcl_tap_0] -force
  assign_bd_address -offset 0x04120000 -range 0x00010000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/PMCL_TRNG/pmcl_trng_0] -force
  assign_bd_address -offset 0x04040000 -range 0x00001000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/RV_IOMODULE/rv_iomodule_0] -force
  assign_bd_address -offset 0x04042000 -range 0x00001000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/RV_RAM_DATA_ECC_CTRL/rv_ram_data_ecc_ctrl_0] -force
  assign_bd_address -offset 0x04041000 -range 0x00001000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/RV_RAM_INSTR_ECC_CTRL/rv_ram_instr_ecc_ctrl_0] -force
  assign_bd_address -offset 0x04050000 -range 0x00010000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs pmc/SLAVE_BOOT_STREAM/slave_boot_stream_0] -force
  assign_bd_address -offset 0x40000000 -range 0x00010000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs timer/S_AXI/Reg] -force
  assign_bd_address -offset 0x40600000 -range 0x00010000 -target_address_space [get_bd_addr_spaces mb/Data] [get_bd_addr_segs uart/S_AXI/Reg] -force
  assign_bd_address -offset 0x00000000 -range 0x00020000 -target_address_space [get_bd_addr_spaces mb/Instruction] [get_bd_addr_segs mb_local_memory/ilmb_bram_if_cntlr/SLMB/Mem] -force


  # Restore current instance
  current_bd_instance $oldCurInst

  validate_bd_design
  save_bd_design
}
# End of create_root_design()


##################################################################
# MAIN FLOW
##################################################################

create_root_design ""


