# cocotb makefile for the LZC testbench.
#
#   make                        run everything with Icarus
#   make lint                   Verilator lint only
#   make LZC16_N_RANDOM=1000    short smoke run (16-bit coverage drops; the
#                               testbench warns rather than silently shrinking)
#   make WAVES=1                dump lzc.fst
#   make clean

TOPDIR := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
RTLDIR := $(TOPDIR)/../rtl

SIM            ?= icarus
TOPLEVEL_LANG  ?= verilog
TOPLEVEL       := lzc_tb_top
COCOTB_TEST_MODULES := test_lzc

# One module per file, matching module names, so Verilator's -y search and
# svlangserver both resolve lzc_8 from lzc_tb_top.
VERILOG_SOURCES := $(RTLDIR)/lzc_8.sv $(RTLDIR)/lzc_16.sv $(TOPDIR)/lzc_tb_top.sv

# Must have a value before export: `export FOO` on an unset variable passes an
# empty string through to the environment, not an absent key, so the
# testbench's os.environ.get() default would never fire.
LZC16_N_RANDOM ?= 1000000
export LZC16_N_RANDOM

ifeq ($(WAVES),1)
    ifeq ($(SIM),icarus)
        SIM_ARGS += -fst
        COMPILE_ARGS += -s cocotb_waves
        VERILOG_SOURCES += $(TOPDIR)/dump_waves.v
    endif
endif

# Fail with a readable message rather than collapsing to /Makefile.sim when
# cocotb-config is off PATH, which is what an unactivated venv looks like.
COCOTB_MAKEFILES := $(shell cocotb-config --makefiles 2>/dev/null)
ifeq ($(COCOTB_MAKEFILES),)
    $(error cocotb not found — activate the venv, or pip install cocotb)
endif

include $(COCOTB_MAKEFILES)/Makefile.sim

lint:
	verilator --lint-only -Wall -y $(RTLDIR) \
	    $(RTLDIR)/lzc_8.sv $(RTLDIR)/lzc_16.sv $(TOPDIR)/lzc_tb_top.sv

clean::
	rm -rf $(TOPDIR)/sim_build $(TOPDIR)/__pycache__ \
	       $(TOPDIR)/results.xml $(TOPDIR)/lzc.fst

.PHONY: lint clean