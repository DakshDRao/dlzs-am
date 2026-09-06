# cocotb makefile for the DRUM baseline testbench.
#
#   make                    run everything with Icarus
#   make lint               Verilator lint only
#   make DRUM_N_RANDOM={n}   short smoke run
#   make WAVES=1            dump waves (handled natively by cocotb)
#   make clean

THIS := $(dir $(realpath $(firstword $(MAKEFILE_LIST))))
include $(THIS)../dirs.mk

TOPLEVEL            := drum_tb_top
COCOTB_TEST_MODULES := test_drum

N_RANDOM_VAR := DRUM_N_RANDOM
N_RANDOM     := 200000

# One module per file, matching module names, so Verilator's -y search and
# svlangserver both resolve the leaf modules from the tb top.
VERILOG_SOURCES := $(DRUMDIR)/DRUM6_16_u.v $(DRUMDIR)/DRUM4_16_u.v \
                   $(DRUMDIR)/drum_signed_top.sv \
                   $(TBDIR)/drum_tb_top.sv

# The DRUM cores are vendored upstream Verilog-2001 (see
# baselines/drum/LICENSE.upstream) and are not ours to reformat. Their only
# lint findings are implicit-width shifts and unused decode bits, both benign
# and both confined to those files. Waived here rather than repo-wide, so our
# own RTL stays under full -Wall.
LINT_ARGS := -Wno-WIDTHEXPAND -Wno-UNUSEDSIGNAL

# Must come last.
include $(THIS)../common.mk
