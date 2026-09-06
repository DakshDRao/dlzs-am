# common.mk -- shared cocotb plumbing for every testbench under tb/.
#
# Included LAST by tb/<name>/Makefile, which must first include tb/dirs.mk and
# then set:
#
#   TOPLEVEL             the HDL toplevel module name
#   COCOTB_TEST_MODULES  the python test module name
#   VERILOG_SOURCES      full source list, including the tb top
#
# VERILOG_SOURCES must still be assigned BEFORE this file is included, so that
# lint and the cocotb rules both see the final list.
#
# and MAY set:
#
#   N_RANDOM_VAR   name of the env var carrying the random-vector count
#   N_RANDOM       its default value
#
# The bench-specific Makefiles stay separate rather than merging behind a
# variable: cocotb drives one TOPLEVEL per invocation, and a shared choice of
# DUT in an environment variable is easy to get wrong and believe the pass.
# This file holds only the parts that are genuinely identical.

SIM           ?= icarus
TOPLEVEL_LANG ?= verilog

# Per-bench build directory. This is load-bearing, not tidiness: cocotb's
# Makefile.sim only relinks when sources are NEWER than sim_build/sim.vvp, so a
# single shared sim_build lets one bench silently execute the previously built
# binary of another and report a full pass against the wrong DUT.
SIM_BUILD := $(TBDIR)/sim_build

# The testbenches import the golden model and the sweep stimulus from src/, so
# the published error tables and the verified vectors are provably the same
# set. Exported here rather than re-derived with sys.path surgery in each file.
export PYTHONPATH := $(SRCDIR)$(if $(PYTHONPATH),:$(PYTHONPATH))

# Icarus needs -g2012 for the SystemVerilog syntax in the tb tops and in
# drum_signed_top. The vendored DRUM cores are Verilog-2001 and compile
# unchanged under it.
COMPILE_ARGS += -g2012

# Must have a value before export: `export FOO` on an unset variable passes an
# empty string to the environment, not an absent key, so the testbench's
# os.environ.get() default would never fire.
ifneq ($(N_RANDOM_VAR),)
    $(N_RANDOM_VAR) ?= $(N_RANDOM)
    export $(N_RANDOM_VAR)
endif

# NOTE on waves: there is deliberately no WAVES block here. cocotb >= 2.0
# implements WAVES=1 natively for Icarus -- it generates its own dump module
# against the real TOPLEVEL and adds the vvp flags. The old hand-rolled
# tb/dump_waves.v both hardcoded the wrong hierarchy (lzc_tb_top while
# TOPLEVEL was mult_tb_top) and, once fixed, double-passed -fst to vvp and
# failed to launch. `make WAVES=1` works with nothing extra.

# Fail with a readable message rather than collapsing to /Makefile.sim when
# cocotb-config is off PATH, which is what an unactivated venv looks like.
COCOTB_MAKEFILES := $(shell cocotb-config --makefiles 2>/dev/null)
ifeq ($(COCOTB_MAKEFILES),)
    $(error cocotb not found -- activate the venv, or pip install cocotb)
endif

include $(COCOTB_MAKEFILES)/Makefile.sim

# LINT_ARGS lets a bench waive warning classes that come from vendored
# third-party sources it does not own. Verilator exits non-zero on warnings, so
# without this the DRUM bench fails lint on upstream code we must not edit --
# which trains everyone to ignore the lint target.
LINT_ARGS ?=

lint:
	verilator --lint-only -Wall -Wno-DECLFILENAME $(LINT_ARGS) -y $(RTLDIR) $(VERILOG_SOURCES)

clean::
	rm -rf $(SIM_BUILD) $(TBDIR)/__pycache__ $(TBDIR)/results.xml \
	       $(TBDIR)/*.fst $(TBDIR)/*.vcd

.PHONY: lint clean
