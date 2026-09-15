# DLZS three-level compensation: repository-integrated package

This archive replaces the earlier standalone package. Extract over your
dlzs-am repository root, preserving paths. Review the replacement files first if
you have local edits. Baseline: GitHub master fetched on 15 September 2026.
No GitHub changes or physical-board changes were made.

## Integration

* Makefile: comp added to BENCHES (sim/lint/clean); new model tests included
  in test and smoke; smoke invokes tb/comp with COMP_N_RANDOM=1000.
* tb/comp/Makefile: dirs.mk first, sources next, common.mk last, matching opt.
  Uses isolated SIM_BUILD, common PYTHONPATH, WAVES, lint and clean rules.
* tb/comp/test_comp.py: seven cocotb tests: exhaustive decoder, exhaustive
  metadata detector, B/3B generator, shift extremes, all signed A with
  extreme B, shared sweep.sampled_pairs, and the actual registered synthesis
  wrapper. Disabled mode is compared against both the golden model and
  original RTL.
* synth/synth_ooc.tcl: dlzs_comp_three added to DESIGNS. Uses the SAME target,
  XDC, DSP check, synthesis/place/phys-opt/route flow, summary format,
  incremental skip, period/force controls, and report directory conventions.
* synth/wrappers/dlzc_comp_wrapper.sv: clk/a/b/p ports and 64-register harness.
* src/combine_attention_costs.py: both compensated attention directions map to
  dlzs_comp_three. Old seven-design runs still work; partial compensation
  pairs fail explicitly.
* src/golden_model.py: dlzs_three_level registered for unsigned/signed sweeps.
  src/sweep.py needs no edit because it already iterates DESIGNS.
* src/attention_corpus_eval.py: adds dlzs_comp_q/k and scalar self-check entries.
* synth/power.tcl needs no edit: it discovers post_route/routed.dcp automatically.
* tb/dirs.mk and common.mk are included unchanged for reference.

## Commands, from repository root with your existing environment activated

    make test
    make -C tb/comp
    make -C tb/comp COMP_N_RANDOM=1000
    make -C tb/comp WAVES=1
    make sim
    make lint
    make smoke
    make designs
    make synth-one DESIGN=dlzs_comp_three
    make synth-one DESIGN=dlzs_comp_three EXTRA="-period 10 -force"
    make power EXTRA="dlzs_comp_three"
    make sweep
    make clean

Standard reports/checkpoint:
    synth_result/dlzs_comp_three/summary.txt
    synth_result/dlzs_comp_three/post_route/utilization.txt
    synth_result/dlzs_comp_three/post_route/timing_summary.txt
    synth_result/dlzs_comp_three/post_route/routed.dcp

Run the existing attention command followed by the existing audit and cost
join command. New design rows will be included automatically. The existing
passage-minimum reporting caveat still applies; use audited/corrected tables.

## Arithmetic and deployment

The decoder rounds |A| to {1,1.5,2}*2^k (nearest, upward magnitude ties).
Small magnitudes and zero have explicit handling. A prepared signed B/3B is
selected before one shared 18-bit-input shifter. Output remains signed 32-bit.
The original shifter's INPUT_WIDTH defaults to 17, preserving old callers.
COMPENSATE=0 instantiates the original top exactly at elaboration time.

The optimized decoder uses two fixed-position casez leading-one detectors and
exports the two bits below the leading one as metadata. This removes the
runtime variable shift from the first compensation implementation. The
selected B/3B value then uses one shared 18-bit-input shifter. The metadata
detector is exhaustively checked for all 0..32768 input magnitudes.

The first compensation implementation is retained in the validation notes for
an apples-to-apples comparison. The optimized implementation is the RTL in
this archive and is the one registered as `dlzs_comp_three` in the shared flow.

The AXI packaged IP and existing bitstream are NOT updated. To deploy later,
select the new core inside that IP and regenerate the overlay.

## Validation

See validation/ for actual logs and VALIDATION.md for the final status. The
new attention kernel/full corpus study has not been run in this task.
