# Same anchors/source-order/shared plumbing as tb/opt.
THIS := $(dir $(realpath $(firstword $(MAKEFILE_LIST))))
include $(THIS)../dirs.mk

TOPLEVEL := comp_tb_top
COCOTB_TEST_MODULES := test_comp
N_RANDOM_VAR := COMP_N_RANDOM
N_RANDOM := 200000

VERILOG_SOURCES := $(RTLDIR)/lzc_8.sv $(RTLDIR)/lzc_16.sv \
                   $(RTLDIR)/lzc_8_meta.sv $(RTLDIR)/lzc_16_meta.sv \
                   $(RTLDIR)/dlzs_snap_exp.sv $(RTLDIR)/dlzs_b_prep.sv \
                   $(RTLDIR)/dlzc_shift.sv $(RTLDIR)/dlzc_opt_top.sv \
                   $(RTLDIR)/dlzs_comp_decode.sv $(RTLDIR)/dlzs_b_multiple.sv \
                   $(RTLDIR)/dlzc_comp_top.sv $(WRAPDIR)/dlzc_comp_wrapper.sv \
                   $(TBDIR)/comp_tb_top.sv

include $(THIS)../common.mk
