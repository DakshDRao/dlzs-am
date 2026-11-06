# Program the EDGE ZYNQ, initialise the PS (clocks, DDR, UART) and run the
# regression ELF -- no GUI needed.
#
#   C:\AMDDesignTools\2025.2\Vitis\bin\xsdb.bat <path>\run_on_board.tcl
#
# Board: mode jumper on JTAG, USB JTAG/UART connected, serial terminal open
# at 115200 on the board's COM port BEFORE you run this.
#
# Order matters: a system reset also clears the PL, so reset FIRST, then load
# the bitstream, then initialise the PS (this matches Vitis's own launch flow).

set WS  "C:/projects/major_project/vitis_wrk/dlzs_edge/ws"
set APP "dlzs_test"
set PLATFORM "edge_platform"

proc find_rec {dir name} {
    foreach f [glob -nocomplain -directory $dir -types f $name] { return $f }
    foreach d [glob -nocomplain -directory $dir -types d *] {
        set r [find_rec $d $name]
        if {$r ne ""} { return $r }
    }
    return ""
}

set bit  [find_rec "$WS/$PLATFORM" *.bit]
set init [find_rec "$WS/$PLATFORM" ps7_init.tcl]
set elf  [find_rec "$WS/$APP" $APP.elf]
foreach {v n} [list $bit bitstream $init ps7_init.tcl $elf $APP.elf] {
    if {$v eq ""} { error "could not find $n under $WS" }
    puts "$n: $v"
}

connect
puts [targets]

# 1. Reset the whole system (this also clears any old PL configuration).
targets -set -nocase -filter {name =~ "APU*"}
rst -system
after 1000

# 2. Load the bitstream into the PL.
targets -set -nocase -filter {name =~ "*xc7z*"}
fpga -file $bit
puts "FPGA programmed (DONE LED should be on)"

# 3. Initialise clocks, DDR, MIO/UART, then enable the PS-PL level shifters.
targets -set -nocase -filter {name =~ "APU*"}
source $init
ps7_init
ps7_post_config

# 4. Load and run the application on core 0.
targets -set -nocase -filter {name =~ "*Cortex-A9*#0"}
dow $elf
con
puts "Running -- watch the serial terminal for RESULT: PASS/FAIL."
after 15000
disconnect
