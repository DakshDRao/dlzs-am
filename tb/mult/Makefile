# cocotb makefile for the DLZS multiplier testbench.
#
#   make                    run everything with Icarus
#   make lint               Verilator lint only
#   make MULT_N_RANDOM={n}   short smoke run
#   make WAVES=1            dump waves (handled natively by cocotb)
#   make clean

THIS := $(dir $(realpath $(firstword $(MAKEFILE_LIST))))
include $(THIS)../dirs.mk

TOPLEVEL            := mult_tb_top
COCOTB_TEST_MODULES := test_mult

N_RANDOM_VAR := MULT_N_RANDOM
N_RANDOM     := 200000

# One module per file, matching module names, so Verilator's -y search and
# svlangserver both resolve the leaf modules from the tb top.
VERILOG_SOURCES := $(RTLDIR)/lzc_8.sv $(RTLDIR)/lzc_16.sv \
                   $(RTLDIR)/dlzc_mult.sv $(RTLDIR)/dlzc_mult_top.sv \
                   $(TBDIR)/mult_tb_top.sv

# Must come last: the WAVES=1 branch appends to VERILOG_SOURCES.
include $(THIS)../common.mk
