# cocotb makefile for the optimised ("sign-extend B") DLZS multiplier.
#
#   make                    run everything with Icarus
#   make lint               Verilator lint only
#   make OPT_N_RANDOM={n}   short smoke run (random counts only; every
#                           exhaustive and directed test still runs in full)
#   make WAVES=1            dump waves (handled natively by cocotb)
#   make clean

THIS := $(dir $(realpath $(firstword $(MAKEFILE_LIST))))
include $(THIS)../dirs.mk

TOPLEVEL            := opt_tb_top
COCOTB_TEST_MODULES := test_opt

N_RANDOM_VAR := OPT_N_RANDOM
N_RANDOM     := 200000

# The new datapath, plus the old verified top (dlzc_mult + dlzc_mult_top) as
# an independent second reference for the equivalence tests.
VERILOG_SOURCES := $(RTLDIR)/lzc_8.sv $(RTLDIR)/lzc_16.sv \
                   $(RTLDIR)/dlzs_snap_exp.sv $(RTLDIR)/dlzs_b_prep.sv \
                   $(RTLDIR)/dlzc_shift.sv $(RTLDIR)/dlzc_opt_top.sv \
                   $(RTLDIR)/dlzc_mult.sv $(RTLDIR)/dlzc_mult_top.sv \
                   $(TBDIR)/opt_tb_top.sv

# Must come last: the WAVES=1 branch appends to VERILOG_SOURCES.
include $(THIS)../common.mk
