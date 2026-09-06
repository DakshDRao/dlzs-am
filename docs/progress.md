# DLZS-AM — Progress

FPGA-optimized differential log-domain approximate multiplier with error
compensation — design, characterization, and application to attention-sparsity
prediction.

B.Tech ECE major project, NIT Andhra Pradesh.

Last audited against repo commit `62de93e` ("test cases passed").

---

## Signoff ledger

| Week | Scope | Status |
|------|-------|--------|
| 1–2 | Literature lock + golden model | **SIGNED OFF** |
| 3–5 | DLZS RTL + verification | **SIGNED OFF (conditional — see carry-over)** |
| 6–7 | Baselines + OOC synthesis | Open — current week |
| 8–9 | PYNQ integration | Not started |
| 10–11 | Attention top-k application study | Not started |
| 12–13 | Error compensation (novelty tier) | Not started |
| 14 | Buffer + writeup | Not started |

---

## Week 1–2 — Literature lock + golden model — SIGNED OFF

**Delivered**

- `src/golden_model.py` — bit-exact integer reference models. No float appears
  in any datapath, so results are reproducible and comparable bit-for-bit with
  SystemVerilog simulation output.
  - `exact`, `mitchell`, `drum(k)`
  - DLZS in **four** snap interpretations, not the three the plan asked for:
    `dlzs_floor`, `dlzs_ceil`, `dlzs_nearest_linear`, `dlzs_nearest_log`.
    Splitting "nearest" into linear and log metrics was the right call — they
    genuinely disagree (A=23 snaps to 16 under linear, 32 under log) and the
    log variant has no tie case at all.
- `src/metrics.py` — MRED, max RED, signed bias, NMED, max AED, error rate,
  with the zero-product singularity handled explicitly (RED metrics over the
  65,025 non-zero pairs; absolute metrics and error rate over all 65,536).
- `src/sweep.py` — 8-bit exhaustive and 16-bit sampled+corner sweeps, fixed
  seed 20260828 recorded in every output header.
- `tests/test_golden_model.py` — 16 regression tests, all passing.

**Error table — 8-bit exhaustive, all 65,536 ordered pairs**

```
design                   MRED   maxRED      bias      NMED      maxAED err_rate
-------------------------------------------------------------------------------
dlzs_floor            0.29855  0.49804  -0.29855  0.082682       32385  0.96107
dlzs_ceil             0.37153  0.98450  +0.37153  0.082682       32385  0.96107
dlzs_nearest_linear   0.16918  0.33333  -0.00964  0.041828       16320  0.96107
dlzs_nearest_log      0.17364  0.40659  +0.03890  0.042961       18870  0.96107
mitchell              0.03788  0.11111  -0.03788  0.009326        4096  0.93092
drum4                 0.05887  0.26562  +0.01596  0.014238        7425  0.97717
drum6                 0.01301  0.06348  +0.00571  0.003581        2000  0.85431
```

**Chosen spec:** DLZS nearest-linear, ties round **up**, unsigned 16×16 → 32
core, sign-magnitude signed wrapper.

Justification, in the order it actually mattered:

1. Lowest MRED and NMED of the four DLZS modes, and a near-zero signed bias
   (−0.0096) — which matters specifically for the Week 10 ranking task, where
   a uniform bias largely cancels but variance does not.
2. Cheapest snap decision in hardware: the round-up condition is a single wire
   tapped off the bit below the leading one. `nearest_log` needs a comparison
   against ⌈√2·2^k⌉ thresholds for a *worse* MRED and a larger max RED
   (0.4066 vs 0.3333). It loses on both axes; there is no trade to argue about.
3. `floor` and `ceil` are strongly one-sided (bias ±0.30/±0.37) and are kept
   in the model as characterization baselines only, not as candidate specs.

**Carry-over from this gate**

- The related-work note (4+ prior designs + claimed delta) exists as prose in
  the module docstrings and the framing section below, but is **not yet a
  standalone document in the repo**. It must be written up before the Week 14
  gate; it is not a blocker for Week 6–7.
- `results/` is git-ignored, so the tables above are reproducible but not
  archived. Fine for now; the report will need them committed or attached.

---

## Week 3–5 — DLZS RTL + verification — SIGNED OFF (conditional)

**Delivered**

| File | Contents |
|------|----------|
| `rtl/lzc_8.sv` | 8-bit leading-one detector, `casez` priority encoder, `all_zero` flag |
| `rtl/lzc_16.sv` | 16-bit LZE built by cascading two `lzc_8` blocks |
| `rtl/dlzc_mult.sv` | Unsigned 16×16 → 32 DLZS core, nearest-linear, ties up |
| `rtl/dlzc_mult_top.sv` | Sign-magnitude wrapper (XOR sign, conditional negate) |
| `tb/lzc_tb_top.sv` | Verification wrapper, both LZC widths, pure pass-through |
| `tb/mult_tb_top.sv` | Verification wrapper, unsigned core + signed wrapper |
| `tb/test_lzc.py` | cocotb LZC tests vs `golden_model.lead_one` |
| `tb/test_mult.py` | cocotb multiplier tests vs the golden model |
| `tb/Makefile` | cocotb/Icarus flow, Verilator lint target, waveform hook |

**Design decisions worth defending at the viva**

- `output_power` is *not* a leading-zero count despite the module name — it is
  ⌊log₂ x⌋, i.e. `(w−1) − LZC(x)`, which is exactly the shift amount the
  datapath consumes. The testbench checks it as such, so a future revision to
  a true zero-count fails loudly instead of silently shifting wrong.
- `shamt` is **5 bits**, not 4. A 4-bit sum wraps to 0 when `lead_a == 15` and
  `round_up` fires, silently dropping the shift entirely.
- The zero guard is explicit on operand A. `b == 0` falls out of the shift
  naturally; `a == 0` does not, because `lead_a` is meaningless there. This
  mirrors the model's guard and is the most common source of model/RTL
  divergence.
- Signed overflow bound: the product magnitude never reaches 2³¹, because
  `shamt == 16` requires `lead_one == 15` *and* a round-up, and the only
  magnitude with `lead_one == 15` is 32768 — an exact power of two, which
  never rounds up. Asserted directly in `test_signed_no_overflow`.
- `abs_value1/2` are deliberately **unsigned**. `abs(−32768) == 32768` fits
  16-bit storage but not the signed range; declaring those nets `signed` would
  break the DUT. `test_signed_corners` covers exactly that vector.

**Carry-over — must be cleared before the Week 6–7 gate closes**

1. **`tb/test_mult.py` cannot currently be imported.** It does
   `from golden_model import DESIGNS, signed_wrap, to_signed`, but
   `signed_wrap` and `to_signed` are **not defined** in `src/golden_model.py`
   and are absent from its `__all__`. Confirmed:
   `ImportError: cannot import name 'signed_wrap'`. The multiplier testbench
   therefore cannot execute as committed — only `test_lzc.py` imports cleanly.
   **Action:** add both functions to `src/golden_model.py`, export them, and
   commit the passing cocotb log.
2. **`tests/test_golden_model.py` only runs with the repo root on the path.**
   It inserts `src/` into `sys.path` and then imports `from src.golden_model`,
   which are mutually inconsistent. `python3 tests/test_golden_model.py` fails
   with `ModuleNotFoundError: No module named 'src'`;
   `PYTHONPATH=. python3 tests/test_golden_model.py` passes all 16.
   **Action:** pick one convention and fix the import.
3. **No testbench log is committed.** The Week 3–5 gate asks for a log proving
   zero mismatches. Nothing in the repo demonstrates a simulator was run.
   **Action:** commit `results/mult_tb.log` and `results/lzc_tb.log`.
4. **The RTL is fixed 16-bit, not parameterizable.** The plan called for a
   configurable 8/16-bit LZE. `dlzc_mult` hard-codes `[15:0]`/`[31:0]`, so the
   **exhaustive 8-bit RTL verification (all 65,536 pairs) has not been done and
   cannot be done** with the current source. This is the largest open gap: the
   16-bit runs are sampled, so nothing yet proves exhaustive model/RTL
   equivalence at any width. Week 6–7 needs 8-bit synthesis numbers anyway, so
   parameterizing pays for itself twice.
5. **`tb/Makefile` is inconsistent with its own header.** It documents
   `make -f Makefile.mult` and refers to a separate LZC makefile that does not
   exist, so `test_lzc.py` has no runnable target. Its `dump_waves.v` also
   dumps `lzc_tb_top` while `TOPLEVEL` is `mult_tb_top`, so `WAVES=1` dumps
   the wrong hierarchy.

---

## Week 6–7 — Baselines + OOC synthesis — CURRENT WEEK

Gate requires:

1. Verification evidence for **both** baselines — DRUM open-source Verilog
   checked against my own `drum()` model before it is trusted, and a clean
   Mitchell RTL checked against `mitchell()`.
2. The first full comparison table: designs × {LUTs, FFs, Fmax, power, MRED,
   NMED, bias} at 8 and 16 bit.
3. Proof the synthesis runs were out-of-context and LUT-only
   (`USE_DSP="no"`) — utilization report snippets, not claims.
4. Exact multiplier reported **twice**: LUT-only, and DSP-mapped as a separate
   reference row.

Immediate next actions, in order:

1. Clear carry-over items 1 and 2 above — they are ~20 lines of work and they
   unblock every later verification claim.
2. Parameterize the RTL on width (carry-over 4) and run the exhaustive 8-bit
   model/RTL equivalence check.
3. Only then start baseline bring-up.

The ordering is not negotiable: verified baselines before comparison tables,
and simulation match before any hardware claim.

---

## Framing rules (enforced)

Log-domain multiplication is Mitchell (1962) and is **not** claimed as novel.
The claimed contribution is the first standalone FPGA implementation and
characterization of the differential/asymmetric log scheme (DLZS, from SOFA,
Wang et al., MICRO 2024), plus error compensation for it. Position against
power-of-two weight quantization as related work.

Note the table honestly: **Mitchell beats DLZS on every error metric**
(MRED 0.038 vs 0.169). DLZS is not an accuracy play. Its case is hardware
cost — shift-only, no mantissa adder, no carry-resolution branch — and that
case is unproven until the Week 6–7 LUT numbers exist. Do not write a sentence
that implies DLZS is more accurate than Mitchell.

All comparisons must be fair: same bit-width, same LUT-only constraint, same
input distributions.