# cocotb makefile for our FPGA-optimised DRUM(K), K = 3..8.
#
#   make                         run everything with Icarus
#   make lint                    Verilator lint only
#   make DRUM_OPT_N_RANDOM={n}   short smoke run (random counts only; the
#                                exhaustive and directed tests run in full)
#   make WAVES=1                 dump waves (handled natively by cocotb)
#   make clean

THIS := $(dir $(realpath $(firstword $(MAKEFILE_LIST))))
include $(THIS)../dirs.mk

DRUMOPTDIR := $(ROOT)/baselines/drum_opt

TOPLEVEL            := drum_opt_tb_top
COCOTB_TEST_MODULES := test_drum_opt

N_RANDOM_VAR := DRUM_OPT_N_RANDOM
N_RANDOM     := 200000

# Our design, plus the vendored published cores behind drum_signed_top as the
# second reference for K = 4 and 6.
VERILOG_SOURCES := $(RTLDIR)/lzc_8.sv $(RTLDIR)/lzc_16.sv \
                   $(DRUMOPTDIR)/drum_opt_operand.sv \
                   $(DRUMOPTDIR)/drum_opt_shift.sv \
                   $(DRUMOPTDIR)/drum_opt_top.sv \
                   $(DRUMDIR)/DRUM6_16_u.v $(DRUMDIR)/DRUM4_16_u.v \
                   $(DRUMDIR)/drum_signed_top.sv \
                   $(TBDIR)/drum_opt_tb_top.sv

# Same waivers as tb/drum, and for the same reason: they cover the vendored
# upstream cores, which must not be edited. Our own files lint clean without
# them (checked per-K with -GK in isolation).
LINT_ARGS := -Wno-WIDTHEXPAND -Wno-UNUSEDSIGNAL

include $(THIS)../common.mk
