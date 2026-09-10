# cocotb makefile for the exact reference testbench.
#
#   make                     run everything with Icarus
#   make lint                Verilator lint only
#   make EXACT_N_RANDOM={n}  short smoke run
#   make WAVES=1             dump waves (handled natively by cocotb)
#   make clean

THIS := $(dir $(realpath $(firstword $(MAKEFILE_LIST))))
include $(THIS)../dirs.mk

TOPLEVEL            := exact_tb_top
COCOTB_TEST_MODULES := test_exact

N_RANDOM_VAR := EXACT_N_RANDOM
N_RANDOM     := 200000

# exact_wrapper lives under synth/wrappers/ with the other synthesis harnesses,
# not under baselines/. It is not moved here just to make this list tidier: the
# synthesis script reads it from that path, and a copy under baselines/ would
# be a second file that can drift from the one Vivado actually compiles. The
# bench reaches across instead, so what is simulated is byte-for-byte what is
# synthesized.
VERILOG_SOURCES := $(EXACTDIR)/exact.sv \
                   $(WRAPDIR)/exact_wrapper.sv \
                   $(TBDIR)/exact_tb_top.sv

# No LINT_ARGS waivers. Everything in this bench is ours, so it stays under
# full -Wall -- the DRUM bench's waivers exist only for vendored upstream code.
#
# Verilator's -y search points at rtl/ by default (see common.mk), which does
# not contain either source here. Both are named explicitly above, so the
# search path is unused rather than wrong.

# Must come last.
include $(THIS)../common.mk
