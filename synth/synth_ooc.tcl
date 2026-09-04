# 1. Set part (PYNQ-Z2 is xc7z020clg400-1)
set_part xc7z020clg400-1

# 2. Read RTL and Constraints
read_verilog -sv [glob ./rtl/*.sv]
read_xdc ./constraint/ooc_clock.xdc

# 3. Synthesize OUT OF CONTEXT
synth_design -top dlzc_mult_top -mode out_of_context

file mkdir synth_result

# 4. Generate Reports
report_utilization -file synth_result/dlzs_utilization.txt
report_timing -file synth_result/dlzs_timing.txt
report_power -file synth_result/dlzs_power.txt