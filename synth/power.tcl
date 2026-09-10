# power.tcl -- activity-driven power of every routed design in the comparison.
#
#   vivado -mode batch -source synth/power.tcl
#   vivado -mode batch -source synth/power.tcl -tclargs dlzs_opt exact_lut
#   vivado -mode batch -source synth/power.tcl -tclargs -toggle 50 -sp 0.5
#
# ALWAYS RUN FROM THE REPO ROOT. Needs synth_result/<design>/post_route/
# routed.dcp, which synth_ooc.tcl writes after route_design. Designs routed
# before that change have no checkpoint: rebuild them with
# `synth_ooc.tcl -tclargs -force` first.
#
# OPTIONS
#   <n> ...        only these designs (default: every design with a checkpoint)
#   -toggle <pct>  data-input toggle rate, % of the clock. Default 50.
#   -sp <p>        data-input static probability. Default 0.5.
#
# WHY NOT THE DEFAULT report_power IN synth_ooc.tcl
# -------------------------------------------------
# Two problems, both of which make the default numbers unrankable:
#
#   1. Activity. Without user activity, Vivado assumes a default 12.5% toggle
#      rate on the inputs. That is a guess, and it is not the stimulus the error
#      tables were measured on. Here every data input of every design gets the
#      SAME activity -- by default 50% toggle / 0.5 static probability, which
#      is what uniform random operands produce (each bit changes with
#      probability 1/2 per cycle) -- and Vivado propagates it through the
#      routed netlist. Identical input activity is what makes rows comparable.
#
#   2. Resolution. report_power prints watts to 3 decimals, i.e. 1 mW steps,
#      and these designs burn a few mW. `set_units -power mW` moves the same
#      three decimals to microwatts. If a Vivado version rejects it, the
#      summary records the unit actually used, so a coarse row is visible as
#      coarse rather than silently rounded.
#
# WHAT TO COMPARE
# ---------------
# The DSP block's power is its own row in the report ("DSPs") and is included
# in dynamic power, so the exact_dsp row is compared on the same footing.
#
# Device static power (~0.1 W) is the whole chip's leakage and is the same for
# every row; it tells you nothing about the multiplier. Compare DYNAMIC power,
# and better, ENERGY PER MULTIPLY:
#
#     E (pJ) = P_dynamic (mW) x clock period (ns)
#
# Energy per operation does not depend on the clock the estimate was run at, so
# it is the fair column even though some designs cannot close timing at 10 ns.
# All rows are estimated at the constraint clock in the checkpoint (10 ns).
#
# CONFIDENCE
# ----------
# Vectorless propagation from set input activity is typically reported as
# "Medium" confidence. For "High", replace set_switching_activity with a SAIF
# from a netlist simulation of the same vectors (read_saif); the rest of this
# script is unchanged. The confidence level is recorded per row.

set opt_toggle 50.0
set opt_sp     0.5
set want       {}

for {set i 0} {$i < [llength $argv]} {incr i} {
    set a [lindex $argv $i]
    switch -glob -- $a {
        -toggle { incr i; set opt_toggle [lindex $argv $i] }
        -sp     { incr i; set opt_sp     [lindex $argv $i] }
        -*      { error "unknown option '$a' -- see the header of this file" }
        default { lappend want $a }
    }
}

# A toggle rate above 2*min(sp, 1-sp)*100 is physically impossible for a
# signal with that static probability; Vivado rejects it, so reject it first
# with a message that says why.
set tr_max [expr {200.0 * min($opt_sp, 1.0 - $opt_sp)}]
if {$opt_toggle > $tr_max} {
    error "toggle rate $opt_toggle% impossible at static probability $opt_sp\
           (max $tr_max%)"
}

if {[llength $want] == 0} {
    foreach d [lsort [glob -nocomplain -type d synth_result/*]] {
        if {[file exists $d/post_route/routed.dcp]} {
            lappend want [file tail $d]
        }
    }
}
if {[llength $want] == 0} {
    error "no routed checkpoints found -- run synth_ooc.tcl -tclargs -force first"
}

# ---------------------------------------------------------------------------
# Report parsing
# ---------------------------------------------------------------------------

proc pw_summary {text label} {
    # "| Dynamic (mW) | 1.234 |" -> {mW 1.234}. Returns {n/a n/a} if absent.
    set re "\\|\\s*${label}\\s*\\((\\w+)\\)\\s*\\|\\s*(\[<0-9.\]+)"
    if {[regexp $re $text -> unit val]} { return [list $unit $val] }
    return [list n/a n/a]
}

proc pw_component {text label} {
    # "| Slice Logic | 0.123 | ..." -> 0.123 (or <0.001, or n/a)
    set re "\\|\\s*${label}\\s*\\|\\s*(\[<0-9.\]+)\\s*\\|"
    if {[regexp $re $text -> val]} { return $val }
    return n/a
}

proc to_mw {val unit} {
    # Numeric value in mW, or n/a when the report gave "<x" or no number.
    if {![string is double -strict $val]} { return n/a }
    switch -- $unit {
        uW { return [expr {$val / 1000.0}] }
        mW { return [expr {double($val)}] }
        W  { return [expr {$val * 1000.0}] }
    }
    return n/a
}

proc fmt {x {spec %.3f}} {
    if {$x eq "n/a"} { return n/a }
    return [format $spec $x]
}

# ---------------------------------------------------------------------------
# Per design
# ---------------------------------------------------------------------------

set done {}

foreach name $want {
    set dcp synth_result/$name/post_route/routed.dcp
    if {![file exists $dcp]} {
        puts "SKIP $name -- no $dcp (rebuild it with synth_ooc.tcl -force)"
        continue
    }

    puts "=========================================================="
    puts "Power: $name  (data toggle=${opt_toggle}% sp=$opt_sp)"
    puts "=========================================================="

    close_project -quiet
    open_checkpoint $dcp

    if {[catch {set_units -power mW} err]} {
        puts "  NOTE: set_units -power mW rejected ($err); reporting in W"
    }

    # Data inputs only: the clock's activity comes from its constraint. Every
    # harness has two 16-bit operand ports, so anything but 32 means the
    # filter picked up the wrong ports and the rows would not be comparable.
    set din [get_ports -filter {DIRECTION == IN && NAME != clk}]
    if {[llength $din] != 32} {
        error "FAIL: $name has [llength $din] data inputs, expected 32 --\
               the activity would not be applied identically across rows"
    }
    set_switching_activity -toggle_rate $opt_toggle \
                           -static_probability $opt_sp $din

    set period [get_property PERIOD [get_clocks clk]]

    set rpt synth_result/$name/post_route/power_activity.txt
    report_power -file $rpt

    set fh [open $rpt r]; set text [read $fh]; close $fh

    lassign [pw_summary $text {Total On-Chip Power}] u_tot v_tot
    lassign [pw_summary $text {Dynamic}]             u_dyn v_dyn
    lassign [pw_summary $text {Device Static}]       u_sta v_sta
    set conf n/a
    regexp {\|\s*Confidence Level\s*\|\s*(\w+)} $text -> conf

    set unit $u_dyn
    set clk_v [pw_component $text {Clocks}]
    set log_v [pw_component $text {Slice Logic}]
    set sig_v [pw_component $text {Signals}]
    # Only the exact_dsp row has this; for LUT-only rows it is absent (n/a).
    set dsp_v [pw_component $text {DSPs}]

    set dyn_mw [to_mw $v_dyn $unit]
    set energy [expr {$dyn_mw eq "n/a" ? "n/a" : $dyn_mw * $period}]

    set fh [open synth_result/$name/power_summary.txt w]
    puts $fh "design            $name"
    puts $fh "activity_toggle   $opt_toggle"
    puts $fh "activity_sp       $opt_sp"
    puts $fh "period_ns         $period"
    puts $fh "unit              $unit"
    puts $fh "total             $v_tot"
    puts $fh "dynamic           $v_dyn"
    puts $fh "static            $v_sta"
    puts $fh "clocks            $clk_v"
    puts $fh "slice_logic       $log_v"
    puts $fh "signals           $sig_v"
    puts $fh "dsps              $dsp_v"
    puts $fh "dynamic_mw        [fmt $dyn_mw]"
    puts $fh "energy_pj_per_op  [fmt $energy]"
    puts $fh "confidence        $conf"
    close $fh

    puts "  dynamic=$v_dyn $unit  energy=[fmt $energy] pJ/op  confidence=$conf"
    if {$unit eq "W"} {
        puts "  WARNING: 1 mW resolution -- this row cannot be ranked finely"
    }

    close_design
    lappend done $name
}

# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------

puts "=========================================================="
puts "Power at data toggle ${opt_toggle}%, sp $opt_sp"
puts "=========================================================="
puts [format "%-14s %5s %9s %9s %9s %9s %9s %9s %11s %8s" \
      design unit dynamic logic signals clocks dsps static "pJ/op" conf]
foreach name $done {
    set fh [open synth_result/$name/power_summary.txt r]
    set t [read $fh]; close $fh
    set g {}
    foreach k {unit dynamic slice_logic signals clocks dsps static energy_pj_per_op confidence} {
        if {[regexp "(?m)^$k\\s+(\\S+)" $t -> v]} { lappend g $v } else { lappend g - }
    }
    puts [format "%-14s %5s %9s %9s %9s %9s %9s %9s %11s %8s" $name {*}$g]
}
puts "----------------------------------------------------------"
puts "Compare DYNAMIC power or pJ/op. Static is whole-chip leakage, the same"
puts "for every row. Reports: synth_result/*/post_route/power_activity.txt"
puts "=========================================================="