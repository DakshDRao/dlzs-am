# Compatibility alias; use make synth-one DESIGN=dlzs_comp_three.
set argv [linsert $argv 0 dlzs_comp_three]
source [file join [file dirname [info script]] synth_ooc.tcl]
