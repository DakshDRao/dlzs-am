# cocotb makefile for the Mitchell approximate multiplier.
#
#   make
#   make lint
#   make MITCHELL_N_RANDOM={n}
#   make WAVES=1
#   make clean

THIS := $(dir $(realpath $(firstword $(MAKEFILE_LIST))))
include $(THIS)../dirs.mk

TOPLEVEL            := mitchell_tb_top
COCOTB_TEST_MODULES := test_mitchell

N_RANDOM_VAR := MITCHELL_N_RANDOM
N_RANDOM     := 200000

VERILOG_SOURCES := $(RTLDIR)/lzc_8.sv \
                   $(RTLDIR)/lzc_16.sv \
                   $(MITCHELLDIR)/mitchell_mult.sv \
                   $(MITCHELLDIR)/mitchell_mult_top.sv \
                   $(TBDIR)/mitchell_tb_top.sv

include $(THIS)../common.mk
