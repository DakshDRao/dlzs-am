# cocotb makefile for the multiplier testbench.
#
#   make -f Makefile.mult                    run everything with Icarus
#   make -f Makefile.mult lint               Verilator lint only
#   make -f Makefile.mult MULT_N_RANDOM=1000 short smoke run
#   make -f Makefile.mult WAVES=1            dump mult.fst
#   make -f Makefile.mult clean
#
# Kept separate from the LZC Makefile rather than merged behind a variable:
# cocotb drives one TOPLEVEL per invocation, and a shared makefile would put
# the choice of DUT in an environment variable where it is easy to run the
# wrong one and believe the pass.

TOPDIR := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
RTLDIR := $(TOPDIR)/../rtl

SIM            ?= icarus
TOPLEVEL_LANG  ?= verilog
TOPLEVEL       := mult_tb_top
COCOTB_TEST_MODULES := test_mult

# One module per file, matching module names, so Verilator's -y search and
# svlangserver both resolve the leaf modules from mult_tb_top.
VERILOG_SOURCES := $(RTLDIR)/lzc_8.sv $(RTLDIR)/lzc_16.sv \
                   $(RTLDIR)/dlzc_mult.sv $(RTLDIR)/dlzc_mult_top.sv \
                   $(TOPDIR)/mult_tb_top.sv

# Must have a value before export: `export FOO` on an unset variable passes an
# empty string through to the environment, not an absent key, so the
# testbench's os.environ.get() default would never fire.
MULT_N_RANDOM ?= 200000
export MULT_N_RANDOM

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
	verilator --lint-only -Wall -y $(RTLDIR) $(VERILOG_SOURCES)

clean::
	rm -rf $(TOPDIR)/sim_build $(TOPDIR)/__pycache__ \
	       $(TOPDIR)/results.xml $(TOPDIR)/mult.fst

.PHONY: lint clean