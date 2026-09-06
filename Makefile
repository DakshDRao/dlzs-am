# Top-level entry point. Every target is runnable from the repo root, so no
# target depends on the caller having cd'd into a subdirectory first.
#
#   make test     golden-model regression suite
#   make sweep    error sweeps -> results/
#   make sim      all three cocotb testbenches
#   make lint     Verilator lint on all three
#   make smoke    fast versions of test + sim, for pre-commit
#   make synth    Vivado OOC synthesis of every design -> synth_result/
#   make clean

PYTHON ?= python3
BENCHES := lzc mult drum

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
	$(MAKE) -C tb/drum DRUM_N_RANDOM=1000

synth:
	vivado -mode batch -source synth/synth_ooc.tcl

clean:
	@for b in $(BENCHES); do $(MAKE) -C tb/$$b clean; done
	rm -rf __pycache__ */__pycache__ */*/__pycache__ .pytest_cache
	rm -f vivado*.jou vivado*.log

.PHONY: test sweep sim lint smoke synth clean
