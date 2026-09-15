# Integration validation, 15 September 2026

Validated in an isolated copy of the repository build/test sources with the overlay.

The final optimized-run transcript is in `optimized_comp_validation.log`.

- make lint: PASS, all eight benches, existing vendor waivers unchanged.
- make test: PASS, original 19 tests plus two compensation model tests.
- make smoke: PASS, all eight benches (47 cocotb tests); random counts reduced
  to 1000, exhaustive and directed tests retained.
- make -C tb/comp COMP_N_RANDOM=1000: PASS, seven tests including exhaustive
  metadata checking, plus 3600 shared corner pairs. The full default random
  run is available by omitting the override.
- make -n clean: build rules inspected without deletion.
- Vivado shared synth/synth_ooc.tcl -list: includes dlzs_comp_three.
- Shared synthesis/place/phys-opt/route flow: completed, zero DSPs.
- Existing synth/power.tcl dlzs_comp_three: completed using standard checkpoint.
- Cost join fixtures: PASS for old seven-design runs and new nine-design runs;
  incomplete compensation pairs rejected.

## Optimized implementation result

Vivado 2025.2, xc7z020clg400-1, matched OOC 10 ns constraint. These are the
post-route values produced by the same `synth/synth_ooc.tcl` flow used for the
other designs:

| Physical Slice LUTs | LUT cells | Registers | DSPs | WNS | Derived Fmax |
|---|---|---|---|---|---|
| 177 | 187 | 64 | 0 | +0.114 ns | 101.15 MHz |

The optimized build closes the 100 MHz target under this OOC constraint. The
post-synthesis WNS is -0.649 ns (estimated, before placement); quote the
post-route value above for the implementation comparison.

## First implementation result (historical, not optimized)

Vivado 2025.2, xc7z020clg400-1, matched OOC 10 ns constraint:

| Physical Slice LUTs | LUT cells | Registers | DSPs | WNS | Derived Fmax |
|---|---|---|---|---|---|
| 194 | 197 | 64 | 0 | -0.764 ns | 92.90 MHz |

This version misses the 100 MHz target. Do not describe it as timing-closed
at 100 MHz. The architecture still needs optimization if that target is required.
Power is activity-estimated, not measured; the reported 10 ns energy assumes
a clock period this design did not meet and is not a demonstrated operating point.

Attention-kernel execution, full top-k evaluation, and board testing remain pending.
No claims of top-k improvement or publication novelty are established by these tests.
