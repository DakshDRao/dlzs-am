# synth_ooc.tcl -- out-of-context, LUT-only synthesis of every design in the
# comparison, under identical constraints.
#
#   vivado -mode batch -source synth/synth_ooc.tcl        (run from the REPO ROOT;
#                                                         all paths below are relative to it)
#
# Replaces the single-design version. Three things changed and each is
# load-bearing for the Week 6-7 gate:
#
#   1. -max_dsp 0 on every run. DRUM's core contains a real k x k multiply
#      (`assign tmp = mm*nn;`), which Vivado will map to a DSP48 given the
#      chance. DLZS has no multiply at all, so a DSP-mapped DRUM against a
#      LUT-only DLZS would understate DRUM's LUT cost and the comparison would
#      be meaningless. The (* use_dsp = "no" *) attributes stay in the RTL as
#      belt-and-braces, but attribute inheritance across module boundaries is
#      not something to rely on for a headline number.
#
#   2. Each design gets its own report directory, and the DSP row is checked
#      programmatically rather than eyeballed. The gate asks for PROOF the runs
#      were LUT-only -- a script that fails loudly is proof; a claim is not.
#
#   3. Every design runs through a structurally identical pipelined harness
#      (two 16-bit input registers, one 32-bit output register, one clock), so
#      the 64 flip-flops are common to all rows and drop out of the delta.
#
# Reports land in synth_result/<design>/.

set part xc7z020clg400-1
set_part $part

set rtl_dir     ./rtl
set drum_dir    ./baselines/drum
set wrap_dir    ./synth/wrappers
set constraints ./synth/constraints/ooc_clock.xdc

# design name -> list of source files.
#
# NOTE on signedness, corrected: dlzc_wrapper_test instantiates dlzc_mult_top,
# which IS the sign-magnitude shell (XOR sign, conditional negate) around the
# unsigned dlzc_mult core -- not the bare core. The dlzs_signed row is
# therefore signed-vs-signed comparable to the DRUM rows as it stands. An
# earlier comment here and in drum_wrapper_test.sv claimed otherwise and
# blocked the comparison table for no reason.
set designs [dict create \
    dlzs_signed   [list $rtl_dir/lzc_8.sv $rtl_dir/lzc_16.sv $rtl_dir/dlzc_mult.sv $rtl_dir/dlzc_mult_top.sv $wrap_dir/dlzc_wrapper_test.sv] \
    drum6_signed  [list $drum_dir/DRUM6_16_u.v $drum_dir/DRUM4_16_u.v $drum_dir/drum_signed_top.sv $wrap_dir/drum_wrapper_test.sv] \
    drum4_signed  [list $drum_dir/DRUM6_16_u.v $drum_dir/DRUM4_16_u.v $drum_dir/drum_signed_top.sv $wrap_dir/drum_wrapper_test.sv] \
]

set tops [dict create \
    dlzs_signed   {dlzc_wrapper_test {}} \
    drum6_signed  {drum_wrapper_test {K=6}} \
    drum4_signed  {drum_wrapper_test {K=4}} \
]

proc check_no_dsp {name util_file} {
    # Parse the DSP row rather than trusting the constraint. A silent DSP
    # inference is the one failure mode that would invalidate every LUT number
    # in the comparison table without producing any other visible symptom.
    set fh [open $util_file r]
    set text [read $fh]
    close $fh
    if {[regexp {\|\s*DSPs\s*\|\s*(\d+)\s*\|} $text -> n]} {
        if {$n != 0} {
            error "FAIL: $name inferred $n DSP(s); the LUT-only claim is void"
        }
        puts "  DSP check: $name uses 0 DSPs (LUT-only confirmed)"
    } else {
        puts "  WARNING: no DSP row found in $util_file -- check the report manually"
    }
}

file mkdir synth_result

dict for {name sources} $designs {
    puts "=========================================================="
    puts "Synthesizing $name"
    puts "=========================================================="

    lassign [dict get $tops $name] top generics

    # Fresh in-memory project per design. Without this, leaf modules from a
    # previous read_verilog stay resident and a design can silently pick up
    # the wrong LOD or P_Encoder.
    close_project -quiet
    create_project -in_memory -part $part

    foreach f $sources { read_verilog -sv $f }
    read_xdc $constraints

    set args [list -top $top -mode out_of_context -max_dsp 0]
    if {[llength $generics]} { lappend args -generic $generics }
    synth_design {*}$args

    set outdir synth_result/$name
    file mkdir $outdir

    report_utilization -file $outdir/utilization.txt
    report_timing      -file $outdir/timing.txt
    report_power       -file $outdir/power.txt

    # Machine-readable one-liner for the comparison table, so the numbers are
    # transcribed by the tool rather than by hand.
    set n_lut  [llength [get_cells -hier -filter {PRIMITIVE_GROUP == LUT}]]
    set n_ff   [llength [get_cells -hier -filter {PRIMITIVE_GROUP == FLOP_LATCH}]]
    set n_dsp  [llength [get_cells -hier -filter {PRIMITIVE_GROUP == ARITHMETIC}]]
    set slack  [get_property SLACK [get_timing_paths -delay_type max]]

    set fh [open $outdir/summary.txt w]
    puts $fh "design    $name"
    puts $fh "top       $top"
    puts $fh "generics  $generics"
    puts $fh "part      $part"
    puts $fh "luts      $n_lut"
    puts $fh "ffs       $n_ff"
    puts $fh "dsps      $n_dsp"
    puts $fh "slack_ns  $slack"
    close $fh
    puts "  luts=$n_lut ffs=$n_ff dsps=$n_dsp slack=$slack ns"

    check_no_dsp $name $outdir/utilization.txt
}

puts "=========================================================="
puts "All designs synthesized. Summaries in synth_result/*/summary.txt"
puts "=========================================================="
