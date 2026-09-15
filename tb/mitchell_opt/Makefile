# cocotb makefile for the optimized Mitchell multiplier.

THIS := $(dir $(realpath $(firstword $(MAKEFILE_LIST))))
include $(THIS)../dirs.mk

TOPLEVEL            := mitchell_opt_tb_top
COCOTB_TEST_MODULES := test_mitchell_opt

N_RANDOM_VAR := MITCHELL_OPT_N_RANDOM
N_RANDOM     := 200000

VERILOG_SOURCES := $(THIS)../../baselines/mitchell_opt/mitchell_lzc_meta.sv \
                   $(THIS)../../baselines/mitchell_opt/mitchell_mult_opt.sv \
                   $(THIS)../../baselines/mitchell_opt/mitchell_mult_opt_top.sv \
                   $(TBDIR)/mitchell_opt_tb_top.sv

include $(THIS)../common.mk
