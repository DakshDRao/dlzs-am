# Run in a fresh Vivado GUI session:
# vivado -mode gui -source export_vivado.tcl -tclargs <repository-root>
# Exports DLZS RTL blocks only. Does not run implementation or modify reports.
if {$argc != 1} {
    error "Usage: vivado -mode gui -source export_vivado.tcl -tclargs <repository-root>"
}
set repo [file normalize [lindex $argv 0]]
set out [file join $repo docs images vivado elaborated]
file mkdir $out

set sources [glob -nocomplain [file join $repo rtl *.sv]]
set wrapper [file join $repo synth wrappers dlzc_opt_wrapper.sv]
if {[llength $sources] == 0 || ![file exists $wrapper]} {
    error "Repository sources not found under $repo"
}
lappend sources $wrapper

set tops {
    lzc_8 lzc_16 dlzs_snap_exp dlzs_b_prep dlzc_shift
    dlzc_mult dlzc_mult_top dlzc_opt_top dlzc_opt_wrapper
}
set failures {}
foreach top $tops {
    puts "Exporting $top ..."
    set opened 0
    if {[catch {
        create_project -in_memory -part xc7z020clg400-1
        set opened 1
        read_verilog -sv $sources
        synth_design -rtl -top $top -part xc7z020clg400-1
        set view "export_$top"
        show_schematic -name $view [get_nets]
        set pdf [file join $out "$top.pdf"]
        write_schematic -force -format pdf -orientation landscape \
            -scope all -name $view $pdf
        if {![file exists $pdf] || [file size $pdf] == 0} {
            error "No non-empty PDF was exported for $top"
        }
    } reason]} {
        lappend failures $top
        puts stderr "FAILED $top: $reason"
    }
    if {$opened} { close_project }
}
puts "Output folder: $out"
if {[llength $failures]} {
    error "Export failed for: [join $failures {, }]. See the preceding errors."
}
puts "All nine DLZS schematic PDFs exported."
# Leave the GUI open so the user can inspect messages.
