# Repair the dlzs_axi IP after "Edit in IP Packager" left its source paths
# pointing into the deleted temporary edit project.
#
# Run in the Tcl Console of your MAIN Vivado project:
#   source C:/path/to/fix_dlzs_ip.tcl
# Edit IP_DIR below if your ip_repo lives elsewhere.

set IP_DIR "C:/projects/major_project/axi_lite_wrapper/ip_repo/dlzs_axi_1_0"
set HDL    [list dlzs_axi.v dlzs_axi_slave_lite_v1_0_S00_AXI.v dlzc_opt_top.sv \
                 dlzs_snap_exp.sv dlzs_b_prep.sv dlzc_shift.sv lzc_16.sv lzc_8.sv]

# 1. Every source must physically exist in <IP_DIR>/hdl.
set missing {}
foreach f $HDL {
    if {![file exists "$IP_DIR/hdl/$f"]} { lappend missing $f }
}
if {[llength $missing]} {
    error "Missing in $IP_DIR/hdl: $missing -- copy them from the repo's rtl/ (or ip_repo hdl/) first, then re-run."
}

# 2. Point every file entry back at hdl/<name>; drop duplicates.
set core [ipx::open_core "$IP_DIR/component.xml"]
foreach fg [ipx::get_file_groups -of_objects $core] {
    set have {}
    foreach f [ipx::get_files -of_objects $fg] {
        set name [get_property NAME $f]
        if {![string match "*imports*" $name] && ![string match "*edit_dlzs_axi*" $name]} {
            lappend have $name
        }
    }
    foreach f [ipx::get_files -of_objects $fg] {
        set name [get_property NAME $f]
        if {[string match "*imports*" $name] || [string match "*edit_dlzs_axi*" $name]} {
            set fixed "hdl/[file tail $name]"
            if {[lsearch -exact $have $fixed] >= 0} {
                ipx::remove_file $name $fg
                puts "removed duplicate $name"
            } else {
                set_property NAME $fixed $f
                lappend have $fixed
                puts "repointed $name -> $fixed"
            }
        }
    }
}

# 3. Keep the clock frequency propagated from FCLK_CLK0 (no fixed FREQ_HZ).
set clk_if [ipx::get_bus_interfaces S00_AXI_CLK -of_objects $core]
if {[llength $clk_if] && [llength [ipx::get_bus_parameters FREQ_HZ -of_objects $clk_if]]} {
    ipx::remove_bus_parameter FREQ_HZ $clk_if
    puts "removed fixed FREQ_HZ"
}

set_property core_revision [expr {[get_property core_revision $core] + 1}] $core
ipx::update_checksums $core
ipx::check_integrity $core
ipx::save_core $core
ipx::unload_core $core

# 4. Refresh the catalog and regenerate the block-design IP.
update_ip_catalog -rebuild -repo_path [file dirname $IP_DIR]
upgrade_ip [get_ips *dlzs_axi*]
set bd [get_files -quiet *dlzs_system.bd]
if {[llength $bd]} {
    reset_target all $bd
    generate_target all $bd
}
puts "DONE -- now run Generate Bitstream."
