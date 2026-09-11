# Top-level entry point. Every target is runnable from the repo root, so no
# target depends on the caller having cd'd into a subdirectory first.
#
#   make test     golden-model regression suite
#   make sweep    error sweeps -> results/
#   make sim      all cocotb testbenches
#   make lint     Verilator lint on all benches
#   make smoke    fast versions of test + sim, for pre-commit
#   make synth    Vivado OOC synth + implementation -> synth_result/
#   make synth-only   stop after synthesis (fast, timing NOT comparable)
#   make synth-one DESIGN=dlzs_signed    build a single design
#   make designs  list the buildable design names
#   make power    activity-driven power of every routed design (needs routed.dcp)
#   make clean

PYTHON ?= python3
BENCHES := lzc mult mitchell drum exact opt drum_opt

test:
	$(PYTHON) tests/test_golden_model.py

sweep:
	$(PYTHON) src/sweep.py

sim:
	@for b in $(BENCHES); do \
	  echo "=== tb/$$b ==="; $(MAKE) -C tb/$$b || exit 1; \
	done

lint:
	@for b in $(BENCHES); do \
	  echo "=== lint tb/$$b ==="; $(MAKE) -C tb/$$b lint || exit 1; \
	done

# Short run for the pre-commit loop. The random counts are the only thing
# reduced; every directed and corner test still runs in full.
smoke:
	$(PYTHON) tests/test_golden_model.py
	$(MAKE) -C tb/lzc  LZC_N_RANDOM=1000
	$(MAKE) -C tb/mult MULT_N_RANDOM=1000
	$(MAKE) -C tb/mitchell MITCHELL_N_RANDOM=1000
	$(MAKE) -C tb/drum  DRUM_N_RANDOM=1000
	$(MAKE) -C tb/exact EXACT_N_RANDOM=1000
	$(MAKE) -C tb/opt   OPT_N_RANDOM=1000
	$(MAKE) -C tb/drum_opt DRUM_OPT_N_RANDOM=1000

# Full flow: synth, place, route, post-route timing. Finished designs are
# skipped, so adding a new algorithm rebuilds only that one. Pass EXTRA for
# anything else, e.g. `make synth EXTRA="-period 15 -force"`.
VIVADO ?= vivado
EXTRA  ?=

synth:
	$(VIVADO) -mode batch -source synth/synth_ooc.tcl -tclargs $(EXTRA)

# Estimated timing only -- nets are unplaced, so the WNS is NOT comparable
# across designs. Useful for a quick LUT count, not for any number you quote.
synth-only:
	$(VIVADO) -mode batch -source synth/synth_ooc.tcl -tclargs -synth-only $(EXTRA)

synth-one:
	@test -n "$(DESIGN)" || { echo "usage: make synth-one DESIGN=<name>"; \
	  echo "run 'make designs' for the list"; exit 1; }
	$(VIVADO) -mode batch -source synth/synth_ooc.tcl -tclargs $(DESIGN) $(EXTRA)

# Power from the routed checkpoints, at identical data-input activity for every
# design. Pass EXTRA for options, e.g. `make power EXTRA="-toggle 25"`.
power:
	$(VIVADO) -mode batch -source synth/power.tcl -tclargs $(EXTRA)

designs:
	@$(VIVADO) -mode batch -source synth/synth_ooc.tcl -tclargs -list

clean:
	@for b in $(BENCHES); do $(MAKE) -C tb/$$b clean; done
	rm -rf __pycache__ */__pycache__ */*/__pycache__ .pytest_cache
	rm -f vivado*.jou vivado*.log

.PHONY: test sweep sim lint smoke synth synth-only synth-one power designs clean