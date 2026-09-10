# synth_ooc.tcl -- out-of-context, LUT-only build of every design in the
# comparison, under identical constraints.
#
#   vivado -mode batch -source synth/synth_ooc.tcl
#   vivado -mode batch -source synth/synth_ooc.tcl -tclargs dlzs_signed
#   vivado -mode batch -source synth/synth_ooc.tcl -tclargs -synth-only
#   vivado -mode batch -source synth/synth_ooc.tcl -tclargs -period 15 -force
#   vivado -mode batch -source synth/synth_ooc.tcl -tclargs -list
#
# ALWAYS RUN FROM THE REPO ROOT. Every path below is relative to it.
#
# OPTIONS
#   <name> ...      build only these designs (default: all). -list prints them.
#   -period <ns>    clock period. Default 10.0.
#   -synth-only     stop after synth_design; skip place and route.
#   -force          rebuild designs that already have results.
#   -list           print the design names and exit.
#
# WHY IMPLEMENTATION AND NOT JUST SYNTHESIS
# -----------------------------------------
# Post-synthesis, Vivado has no placement, so every net delay is estimated from
# fanout alone and the reports say `unplaced`. That is tolerable when routing is
# a small share of the path. It is not tolerable here: routing is 62% of the
# DLZS path and 48% of the exact path, and the ENTIRE measured gap between those
# two designs is routing -- their logic delays match to 0.03ns. The number the
# comparison rests on is the one number synthesis has not actually computed.
#
# The bias also runs one way. Vivado's unplaced model is pessimistic on high
# fanout, and DLZS is the design carrying the fo=7/12/22 nets out of its
# barrel-shifter control, while exact's path is mostly dedicated carry cascade
# whose CO->CI hops cost 0.000ns and have nothing to recover. So placement
# should close some of the gap, and how much is exactly the open question.
#
# Post-synthesis LUT counts are broadly trustworthy; post-synthesis timing
# across designs is not. Both are reported, separately labelled, so nobody has
# to remember which is which six months from now.
#
# WHY Fmax AND NOT SLACK
# ----------------------
# At a 10ns target three of the four designs fail, and a failing WNS is a real
# measurement but a strained one -- the router keeps working a path it cannot
# close, so the number partly reflects how hard it tried. Fmax = 1000 /
# (period - WNS) does not depend on the choice of target, so it is the figure
# that belongs in the comparison table. Slack is kept beside it because it is
# what tells you whether the target was met.
#
# For a clean run with no failing paths, pass -period 15 and compare the Fmax
# column. The ranking should not move. If it does, say so in the writeup --
# that is a finding about constraint sensitivity, not a nuisance.
#
# LUT-ONLY
# --------
# -max_dsp 0 on every design, no exceptions. DRUM's core contains a real k x k
# multiply (`assign tmp = mm*nn;`), and exact_wrapper is the textbook DSP48E1
# inference template -- two input regs, a multiply, one output reg, which is
# precisely the A/B input regs, multiplier and P output reg inside one DSP48E1.
# Either one mapping to a DSP against a LUT-only DLZS would make the comparison
# meaningless. The constraint is verified from the utilization report rather
# than trusted, because a silent DSP inference is the one failure that
# invalidates every LUT number without any other visible symptom.
#
# exact_wrapper carries no (* use_dsp = "no" *) attribute on purpose: attribute
# inheritance across module boundaries is not something to rely on for a
# headline number, so the policy lives here where it can be checked.
#
# ADDING A DESIGN
# ---------------
# Add one entry to DESIGNS below. Nothing else needs touching -- the flow, the
# checks, the summary and the table are all driven off that dict. Then build
# only it:
#
#   vivado -mode batch -source synth/synth_ooc.tcl -tclargs my_new_design
#
# Finished designs are skipped unless -force, so a fifth design does not re-run
# the four that are already done, and the results table still prints all five.

# ---------------------------------------------------------------------------
# Design database. One entry per row of the comparison table.
# ---------------------------------------------------------------------------

# NOTE on signedness: dlzc_wrapper_test instantiates dlzc_mult_top, which IS
# the sign-magnitude shell (XOR sign, conditional negate) around the unsigned
# dlzc_mult core -- not the bare core. dlzs_signed is therefore signed-vs-signed
# comparable to the DRUM rows.
#
# exact_lut is NOT shell-comparable to either: $signed(a)*$signed(b) folds sign
# handling into the partial-product array instead of paying a 16-bit input
# negate and a 32-bit output negate. Measured on the post-synth path, that
# shell is ~4.35ns of DLZS's 11.82ns. Read the exact row as "what you would
# actually deploy", not as a matched-shell control.
set DESIGNS [dict create]

dict set DESIGNS dlzs_signed {
    top     dlzc_wrapper_test
    generic {}
    sources {
        ./rtl/lzc_8.sv
        ./rtl/lzc_16.sv
        ./rtl/dlzc_mult.sv
        ./rtl/dlzc_mult_top.sv
        ./synth/wrappers/dlzc_wrapper_test.sv
    }
}

dict set DESIGNS drum6_signed {
    top     drum_wrapper_test
    generic {K=6}
    sources {
        ./baselines/drum/DRUM6_16_u.v
        ./baselines/drum/DRUM4_16_u.v
        ./baselines/drum/drum_signed_top.sv
        ./synth/wrappers/drum_wrapper_test.sv
    }
}

dict set DESIGNS drum4_signed {
    top     drum_wrapper_test
    generic {K=4}
    sources {
        ./baselines/drum/DRUM6_16_u.v
        ./baselines/drum/DRUM4_16_u.v
        ./baselines/drum/drum_signed_top.sv
        ./synth/wrappers/drum_wrapper_test.sv
    }
}

dict set DESIGNS exact_lut {
    top     exact_wrapper
    generic {}
    sources {
        ./baselines/exact/exact.sv
        ./synth/wrappers/exact_wrapper.sv
    }
}

set part        xc7z020clg400-1
set constraints ./synth/constraints/ooc_clock.xdc

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

set opt_period [get_property PERIOD [get_clocks clk]]set opt_stage  impl
set opt_force  0
set opt_list   0
set want       {}

for {set i 0} {$i < [llength $argv]} {incr i} {
    set a [lindex $argv $i]
    switch -glob -- $a {
        -period     { incr i; set opt_period [lindex $argv $i] }
        -synth-only { set opt_stage synth }
        -force      { set opt_force 1 }
        -list       { set opt_list 1 }
        -*          { error "unknown option '$a' -- see the header of this file" }
        default     { lappend want $a }
    }
}

if {$opt_list} {
    puts "designs: [dict keys $DESIGNS]"
    return
}

if {[llength $want] == 0} {
    set want [dict keys $DESIGNS]
}

# Fail on an unknown name rather than silently building nothing. A typo'd
# design name that quietly does nothing looks exactly like a successful
# incremental run, and you find out when the comparison table is a row short.
foreach name $want {
    if {![dict exists $DESIGNS $name]} {
        error "unknown design '$name' -- known: [dict keys $DESIGNS]"
    }
}

# The clock period lives in the xdc, so overriding it means writing a new
# constraint. Generated into the results tree rather than over the checked-in
# file, so a -period experiment cannot leave the repo in a state where the
# committed constraint no longer matches the committed numbers.
proc period_xdc {period} {
    file mkdir synth_result/.constraints
    set f synth_result/.constraints/ooc_clock_${period}.xdc
    set fh [open $f w]
    puts $fh "create_clock -name clk -period $period \[get_ports clk\]"
    close $fh
    return $f
}

set xdc $constraints
if {$opt_period != 10.0} {
    set xdc [period_xdc $opt_period]
    puts "NOTE: period overridden to ${opt_period}ns; using $xdc"
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

proc safe_prop {prop obj {default "n/a"}} {
    # Path properties are version-dependent. A missing one should cost a field
    # in the summary, not the whole run.
    if {[catch {get_property $prop $obj} v]} { return $default }
    if {$v eq ""} { return $default }
    return $v
}

proc check_no_dsp {name util_file} {
    # Parse the DSP row rather than trusting -max_dsp. A silent DSP inference
    # is the one failure mode that would invalidate every LUT number in the
    # comparison table without producing any other visible symptom.
    set fh [open $util_file r]
    set text [read $fh]
    close $fh
    if {[regexp {\|\s*DSPs\s*\|\s*(\d+)\s*\|} $text -> n]} {
        if {$n != 0} {
            error "FAIL: $name inferred $n DSP(s); the LUT-only claim is void"
        }
        puts "  DSP check: $name uses 0 DSPs (LUT-only confirmed)"
    } else {
        error "FAIL: no DSP row found in $util_file -- the LUT-only claim\
               cannot be verified, so it is not made. If the report format\
               changed, fix the regexp; do not downgrade this to a warning."
    }
}

proc count_cells {} {
    # REF_NAME rather than PRIMITIVE_GROUP for the DSP count. The group name is
    # version-dependent and, critically, a WRONG group name returns 0 -- which
    # is indistinguishable from a correct LUT-only result and would silently
    # confirm the claim this script exists to test. That already happened once:
    # a DSP-mapped run reported dsps=0 while Vivado's own log said
    # "Resources of type DSP have been overutilized. Used = 1".
    set n_lut [llength [get_cells -hier -filter {PRIMITIVE_GROUP == LUT}]]
    set n_ff  [llength [get_cells -hier -filter {PRIMITIVE_GROUP == FLOP_LATCH}]]
    set n_dsp [llength [get_cells -hier -filter {REF_NAME =~ "DSP*"}]]
    return [list $n_lut $n_ff $n_dsp]
}

proc worst_path {} {
    # Worst SETUP path and its endpoints. The endpoints go in the summary
    # because a slack figure alone cannot tell you WHICH path it measured, and
    # the failures that matter here -- a datapath collapsing into a DSP, or a
    # register-to-register path vanishing -- show up as a changed endpoint long
    # before anyone questions the nanoseconds.
    set paths [get_timing_paths -delay_type max -max_paths 1]
    if {[llength $paths] == 0} {
        return [list n/a n/a n/a n/a]
    }
    set p [lindex $paths 0]
    return [list [safe_prop SLACK $p] \
                 [safe_prop STARTPOINT_PIN $p] \
                 [safe_prop ENDPOINT_PIN $p] \
                 [safe_prop LOGIC_LEVELS $p]]
}

proc worst_hold {} {
    set paths [get_timing_paths -delay_type min -max_paths 1]
    if {[llength $paths] == 0} { return n/a }
    return [safe_prop SLACK [lindex $paths 0]]
}

proc summary_wns {file} {
    # Cross-check value, parsed out of report_timing_summary. get_timing_paths
    # returns the worst path it was asked for; report_timing_summary reports
    # WNS across every path group. They should agree, and a disagreement means
    # the single-path query missed a group -- worth knowing, not worth failing
    # the run over.
    if {![file exists $file]} { return n/a }
    set fh [open $file r]; set text [read $fh]; close $fh
    if {[regexp {WNS\(ns\)[^\n]*\n[^\n]*\n\s*(-?[0-9.]+)} $text -> w]} {
        return $w
    }
    return n/a
}

proc fmax_mhz {period wns} {
    if {$wns eq "n/a"} { return n/a }
    set achieved [expr {double($period) - double($wns)}]
    if {$achieved <= 0} { return n/a }
    return [format %.2f [expr {1000.0 / $achieved}]]
}

proc existing_stage {file} {
    if {![file exists $file]} { return "" }
    set fh [open $file r]; set text [read $fh]; close $fh
    if {[regexp {(?m)^stage\s+(\w+)} $text -> s]} { return $s }
    return ""
}

proc field {text key} {
    if {[regexp "(?m)^$key\\s+(\\S+)" $text -> v]} { return $v }
    return "-"
}

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

file mkdir synth_result

set built   {}
set skipped {}

foreach name $want {
    set outdir  synth_result/$name
    set sumfile $outdir/summary.txt

    # Skip work that is already done, so adding a fifth design does not re-run
    # the four that are finished. A synth-only result does NOT satisfy a
    # request for impl -- otherwise the skip would quietly hand back estimated
    # timing where routed timing was asked for, which is the exact confusion
    # this flow exists to remove.
    set have [existing_stage $sumfile]
    if {!$opt_force && $have ne ""} {
        if {$have eq $opt_stage || ($have eq "impl" && $opt_stage eq "synth")} {
            puts "SKIP $name (already built to stage '$have'; -force to rebuild)"
            lappend skipped $name
            continue
        }
        puts "REBUILD $name (have '$have', want '$opt_stage')"
    }

    puts "=========================================================="
    puts "Building $name  (stage=$opt_stage period=${opt_period}ns)"
    puts "=========================================================="

    set top     [dict get $DESIGNS $name top]
    set generic [dict get $DESIGNS $name generic]
    set sources [dict get $DESIGNS $name sources]

    # Fresh in-memory project per design. Without this, leaf modules from a
    # previous read_verilog stay resident and a design can silently pick up the
    # wrong LOD or P_Encoder.
    close_project -quiet
    create_project -in_memory -part $part

    foreach f $sources { read_verilog -sv $f }
    read_xdc $xdc

    set args [list -top $top -mode out_of_context -max_dsp 0]
    if {[llength $generic]} { lappend args -generic $generic }
    synth_design {*}$args

    file mkdir $outdir

    # Post-synthesis reports keep their historical paths, so previously
    # committed results stay comparable and nothing referencing them breaks.
    report_utilization -file $outdir/utilization.txt
    report_timing      -file $outdir/timing.txt
    report_power       -file $outdir/power.txt

    lassign [count_cells] s_lut s_ff s_dsp
    lassign [worst_path]  s_wns s_from s_to s_levels

    check_no_dsp $name $outdir/utilization.txt

    # A LUT-only 16x16 datapath cannot come out near-empty. If it does, the
    # logic went somewhere other than the fabric and every number in this row
    # is measuring something else.
    if {$s_lut < 10} {
        error "FAIL: $name reports only $s_lut LUTs under -max_dsp 0;\
               a fabric datapath cannot be that small -- check\
               $outdir/utilization.txt before trusting any row"
    }

    puts "  post-synth: luts=$s_lut ffs=$s_ff dsps=$s_dsp wns=$s_wns ns"

    set i_lut n/a; set i_ff n/a; set i_dsp n/a
    set i_wns n/a; set i_whs n/a
    set i_from n/a; set i_to n/a; set i_levels n/a; set i_wns_x n/a

    if {$opt_stage eq "impl"} {
        set impdir $outdir/post_route
        file mkdir $impdir

        opt_design
        place_design
        phys_opt_design
        route_design

        report_utilization    -file $impdir/utilization.txt
        report_timing         -file $impdir/timing.txt
        report_timing_summary -delay_type min_max -file $impdir/timing_summary.txt
        report_power          -file $impdir/power.txt

        lassign [count_cells] i_lut i_ff i_dsp
        lassign [worst_path]  i_wns i_from i_to i_levels
        set i_whs   [worst_hold]
        set i_wns_x [summary_wns $impdir/timing_summary.txt]

        check_no_dsp $name $impdir/utilization.txt

        puts "  post-route: luts=$i_lut ffs=$i_ff dsps=$i_dsp wns=$i_wns ns\
              whs=$i_whs fmax=[fmax_mhz $opt_period $i_wns] MHz"

        # A hold violation post-route on a single-clock OOC design means
        # something is wrong with the constraint, not with the datapath.
        if {$i_whs ne "n/a" && $i_whs < 0} {
            puts "  WARNING: $name has NEGATIVE hold slack ($i_whs ns) --\
                  investigate before using any number from this row"
        }
        if {$i_wns_x ne "n/a" && $i_wns ne "n/a"} {
            if {abs($i_wns_x - $i_wns) > 0.001} {
                puts "  WARNING: worst-path WNS ($i_wns) disagrees with\
                      timing-summary WNS ($i_wns_x); the single-path query may\
                      have missed a path group"
            }
        }
    }

    # Machine-readable one-liner for the comparison table, so the numbers are
    # transcribed by the tool rather than by hand. Post-synth and post-route
    # fields are prefixed rather than merged: they are not interchangeable, and
    # the whole point of this flow is that nobody quotes one for the other.
    set fh [open $sumfile w]
    puts $fh "design    $name"
    puts $fh "top       $top"
    puts $fh "generics  $generic"
    puts $fh "part      $part"
    puts $fh "period_ns $opt_period"
    puts $fh "stage     $opt_stage"
    puts $fh "synth_luts   $s_lut"
    puts $fh "synth_ffs    $s_ff"
    puts $fh "synth_dsps   $s_dsp"
    puts $fh "synth_wns_ns $s_wns"
    puts $fh "synth_fmax_mhz [fmax_mhz $opt_period $s_wns]"
    puts $fh "synth_logic_levels $s_levels"
    puts $fh "synth_worst_from $s_from"
    puts $fh "synth_worst_to   $s_to"
    puts $fh "impl_luts    $i_lut"
    puts $fh "impl_ffs     $i_ff"
    puts $fh "impl_dsps    $i_dsp"
    puts $fh "impl_wns_ns  $i_wns"
    puts $fh "impl_whs_ns  $i_whs"
    puts $fh "impl_fmax_mhz [fmax_mhz $opt_period $i_wns]"
    puts $fh "impl_logic_levels $i_levels"
    puts $fh "impl_worst_from $i_from"
    puts $fh "impl_worst_to   $i_to"
    close $fh

    lappend built $name
}

# ---------------------------------------------------------------------------
# Comparison table
# ---------------------------------------------------------------------------

# Printed over ALL designs that have results, not just the ones built this run.
# The point of per-design selection is that you rebuild one design and still see
# it in context; a table showing only what you just touched would defeat that.
puts "=========================================================="
puts "Results"
puts "=========================================================="
puts [format "%-14s %7s %7s %6s %9s %9s %9s %8s" \
      design synthLUT implLUT FF synthWNS implWNS Fmax period]

set seen_periods {}
dict for {name _} $DESIGNS {
    set f synth_result/$name/summary.txt
    if {![file exists $f]} { continue }
    set fh [open $f r]; set t [read $fh]; close $fh
    set per [field $t period_ns]
    if {[lsearch -exact $seen_periods $per] < 0} { lappend seen_periods $per }
    puts [format "%-14s %7s %7s %6s %9s %9s %9s %8s" \
          $name \
          [field $t synth_luts] [field $t impl_luts] [field $t synth_ffs] \
          [field $t synth_wns_ns] [field $t impl_wns_ns] [field $t impl_fmax_mhz] \
          $per]
}

# Rebuilding one design at a different -period leaves the table mixing targets.
# Fmax survives that (it is target-independent, which is why it is the column
# that belongs in the writeup) but WNS does not: slack against 10ns and slack
# against 15ns are not the same measurement and must never be ranked together.
# Silence here is how a mixed table ends up in a thesis.
if {[llength $seen_periods] > 1} {
    puts "----------------------------------------------------------"
    puts "WARNING: rows were built at DIFFERENT clock periods\
          ([join $seen_periods {, }] ns)."
    puts "         The Fmax column is still comparable; the WNS columns are"
    puts "         NOT. Rebuild all rows at one period (-force) before"
    puts "         quoting slack anywhere."
}

puts "----------------------------------------------------------"
puts "built:   [expr {[llength $built] ? $built : "none"}]"
puts "skipped: [expr {[llength $skipped] ? $skipped : "none"}]"
puts "Summaries in synth_result/*/summary.txt"
if {$opt_stage eq "synth"} {
    puts "NOTE: -synth-only. The WNS above is ESTIMATED (nets unplaced) and is"
    puts "      NOT comparable across designs. Re-run without -synth-only"
    puts "      before quoting any timing number."
}
puts "=========================================================="