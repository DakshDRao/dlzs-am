# DLZS-AM

**An FPGA-optimized differential log-domain approximate multiplier with error
compensation — design, characterization, and application to attention-sparsity
prediction.**

B.Tech ECE major project, NIT Andhra Pradesh.

---

## Headline result

On a LUT-only Zynq-7020 (xc7z020clg400-1), post-route, 16×16 → 32 signed:

| Design | Mean rel. error | Slice LUTs | Fmax (MHz) | Energy / multiply* |
|---|---|---|---|---|
| Exact multiplier (LUT-only) | 0 | 265 | 104.3 | ≈ 50 pJ |
| **DLZS, optimized (`dlzs_opt`)** | 16.8 % | **145** (−45 %) | **121.5** (+16.5 %) | **≈ 20 pJ** |

\* Preliminary: Vivado's default activity estimate, rounded to 1 mW; see §7.

`dlzs_opt` is the only approximate design in the comparison that beats the
exact multiplier on **both** area and speed, and it also has the lowest
estimated energy per multiply. It is bit-for-bit identical to
the original DLZS design, so it has exactly the same error; all of the gain
comes from the architecture (§5). It is also the **least accurate** design in
the comparison, and that trade is the whole story — see §7.

---

## 1. What this is

A multiplier is one of the most expensive things you can put on an FPGA fabric.
An *approximate* multiplier trades a bounded amount of numerical error for a
reduction in area and delay — a good trade whenever the consumer of the result
only needs a ranking or a threshold decision, not an exact product.

This project implements and characterizes **DLZS** (differential leading-zero
summation), a scheme from the SOFA accelerator paper (Wang et al., MICRO 2024).
DLZS is asymmetric: it snaps **one** operand to a power of two using its
leading-one position, and **shifts** the other operand by that amount. The
multiply collapses into a leading-one detector and a shifter.

    A × B  ≈  2^round(log₂ A) × B  =  B << round(log₂ A)

SOFA describes DLZS as a component inside a larger accelerator, and its notation
is ambiguous about which way the snap rounds. Nobody has published a standalone
characterization of the scheme. That gap is the project.

### What is and is not claimed

Log-domain multiplication is **Mitchell (1962)** and is **not** claimed as novel.
The claims are narrower:

- the first standalone FPGA implementation and error characterization of the
  asymmetric log scheme, against DRUM, Mitchell and an exact multiplier under
  identical LUT-only constraints;
- an FPGA architecture for signed DLZS that removes the sign-handling cost
  (§5), and an equally optimized DRUM so the comparison is effort-matched (§6);
- an MBM-style error compensation, evaluated on an accuracy-vs-LUTs Pareto
  front (planned, Week 12–13).

A negative result on the compensation tier is acceptable provided it is
characterized honestly.

---

## 2. The four snap interpretations

Because SOFA's notation is ambiguous, all four readings are implemented and
measured. Operand **A** is always snapped; operand **B** is shifted.

| Mode | A snaps to | Round-up test | Relative error of A |
|------|-----------|---------------|---------------------|
| `dlzs_floor` | 2^⌊log₂A⌋ | never | (−0.5, 0] — always under |
| `dlzs_ceil` | 2^⌈log₂A⌉ | whenever A is not a power of two | [0, +1.0) — always over |
| `dlzs_nearest_linear` | nearer power, **linear** midpoint 1.5·2^k | bit (k−1) of A is set | [−0.25, +0.333] |
| `dlzs_nearest_log` | nearer power, **log** midpoint √2·2^k | A² ≥ 2^(2k+1) | [−0.293, +0.414] |

**Chosen specification: `dlzs_nearest_linear`, ties round up.** It wins the
DLZS family on every error metric (§4) and is the cheapest snap in hardware:
the round-up decision is a single bit tap. The tie-break is a specification,
and the RTL matches it bit-for-bit.

---

## 3. Baselines

**Exact.** `$signed(a) * $signed(b)`, mapped to LUTs (`-max_dsp 0`). Vivado
folds the sign into the partial products, so it pays no separate sign cost.

**DRUM(k)** (Hashemi, Bahar, Reda, ICCAD 2015). Truncate both operands to their
k most significant bits from the leading one, force the lowest kept bit to 1
(unbiased rounding), multiply exactly in a k×k core, shift back up. Unbiased
by construction. Two versions are compared:

- **as published** — the authors' unsigned cores (vendored, unmodified logic)
  inside a sign-magnitude shell;
- **FPGA-optimized** — our own implementation, bit-exact with the published
  cores (§6).

**Mitchell (1962).** Both operands to the log domain, log₂(1+m) ≈ m. Always
underestimates; worst case −11.1 %, at mantissas of exactly 0.5 (e.g.
192 × 192 at 8 bits). Golden model only — RTL not yet built.

---

## 4. Accuracy

Golden model, 16-bit **unsigned** operands, the sweep set from `src/sweep.py`:
200,000 uniform random pairs (seed 20260828) plus 3,600 corner pairs. Signed
operands give the same figures to within 0.03 %. Metrics are defined in
`src/metrics.py`.

| Design | MRED | Bias | Max RED |
|---|---|---|---|
| exact | 0 | 0 | 0 |
| DRUM k=8 | 0.37 % | +0.02 % | 1.57 % |
| DRUM k=7 | 0.74 % | +0.03 % | 3.15 % |
| DRUM k=6 | 1.49 % | +0.08 % | 6.35 % |
| DRUM k=5 | 2.99 % | +0.21 % | 12.89 % |
| DRUM k=4 | 6.00 % | +0.71 % | 26.56 % |
| DRUM k=3 | 12.14 % | +2.43 % | 56.25 % |
| **DLZS nearest-linear** | **16.84 %** | **−1.89 %** | **33.33 %** |

Cross-check: the DRUM paper reports 1.47 % mean relative error for DRUM6; the
golden model gives 1.468 % on a pure random sample (the 1.49 % above includes
the corner set, which skews toward boundary cases).

### 8-bit exhaustive — all 65,536 ordered pairs

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

DLZS is not an accuracy play: DRUM6 is about 11× more accurate, and even DRUM3
has a lower mean error (though a worse worst case). The case for DLZS is
hardware cost, and whether its error is tolerable for top-k attention ranking
— a consistent scaling bias does not change a ranking, the spread of the error
does. That is the Week 10–11 study.

---

## 5. The optimized DLZS architecture (`dlzs_opt`)

### Where the original design spent its time

The first DLZS design wrapped the unsigned core in a full sign-magnitude shell:
negate A, negate B, run the core, negate the 32-bit result. Its critical path
was one long series chain:

    abs(A) → LZC → 16:1 mux for the round bit → 5-bit add → 5-stage shifter → 32-bit negate

The 32-bit output negate alone is 8 CARRY4s at the end of the path.

### The rule behind every change

> The sign can be folded, for free, into any part of the datapath that is
> **linear**. It must be removed before any part that works on the
> **magnitude**.

In DLZS only A goes through a magnitude operation (the leading-one snap). B is
only shifted, and a left shift is linear in two's complement. So B never needs
to leave two's complement.

### The four changes

1. **Keep B signed.** If A is negative, negate B *before* the shift (17 bits,
   so −(−32768) fits), since −(B·2^e) = (−B)·2^e. The 32-bit output negate is
   gone. This B branch depends only on raw input bits, so it runs in parallel
   with A's path and is off the critical path.
2. **Merge the round-up into the leading-one detector.** Build

       V = M | ((M & (M >> 1)) << 2)          M = |A|

   Bit i of V is M[i] OR (M[i−1] AND M[i−2]). The leading-one position of V
   *is* the snapped exponent, ties rounding up. A "11" pair at the top of M
   plants a 1 one place above the leading one; otherwise every pair plants at
   or below it. Verified against the reference snap for all 65,535 non-zero
   16-bit values. This removes the 16:1 round-bit mux and the adder.
3. **Four-bit exponent, two-level shifter.** For signed inputs the snapped
   exponent never exceeds 15 (checked over every magnitude), so it is 4 bits.
   A LUT6 is a 4:1 mux, so the shift is two LUT levels: `e[3:2]` first (it is
   ready earliest), then `e[1:0]`.
4. **Zero guard moved into the B branch.** A = 0 forces the prepared B to 0,
   instead of adding a LUT level at the output.

The critical path is now:

    abs(A) → V logic merged into the LZC → two shifter levels

Post-route this is **8 logic levels** against 15 for the original design.

### Output range

The largest output magnitude is 2^30, the same as the exact multiplier. DLZS
can produce −2^30 (A = 32767 rounds up to 2^15, B = −32768), one step below
exact's most negative product −2^30 + 2^15. Both fit the same 32-bit port.

### Verification

`tb/opt` — 8 tests, ~950,000 vectors, all passing. The snap block is checked
exhaustively over every legal magnitude, the B branch exhaustively over all
65,536 B in every flag combination, the shifter over every shift against the
extremes, and the assembled design over all 65,536 A × 10 B against **both**
the golden model and the original verified `dlzc_mult_top`. Re-injecting the
two bugs found during development (raw A into the snap, a missing +1 in the
negate) fails 5 of the 8 tests.

---

## 6. DRUM: audit and FPGA-optimized implementation

### Audit of the published code (scale-lab/DRUM @ 2c7ef20)

| Check | Result |
|---|---|
| Vendored `DRUM6_16_u.v` vs upstream | identical logic (header comment added) |
| Vendored `DRUM4_16_u.v` vs upstream | identical logic; module names suffixed `4` so both cores compile together, and the upstream typo `ux_16_3` fixed — upstream does not elaborate as released |
| Both cores vs upstream's parameterized `dsmk_mn` | 0 mismatches in 1,148,576 vectors each (k=4 and k=6) |
| Upstream `DRUM6_16_s.v` signed wrapper | **broken**: product sign computed with AND instead of XOR |
| Upstream `DRUMk_M_N_s.v` signed wrapper | **broken**: one's complement (`~a`) instead of two's complement, off by one on every negative path |
| Our `drum_signed_top` | same shell structure as upstream `DRUM6_16_s`, with XOR |
| Golden model vs paper | DRUM6 mean relative error 1.468 % vs the paper's 1.47 % |

### Why DRUM cannot use the DLZS sign trick

DRUM truncates **both** operands, and truncation works on the magnitude: on a
negative two's-complement number the "leading one" is always bit 15, and
dropping low bits rounds toward −∞ instead of toward zero. So both operands
need |X|. This is a property of the algorithm, not an effort gap.

### The FPGA-optimized DRUM (`drum_opt`, K = 3..8)

The key idea is **sign-carrying operands with no negation**. After truncation,
each operand is a small K-bit number, and each of its two forms carries the
sign for free:

- **exact case** (|X| < 2^K): X itself fits in K+1 bits, so its own low bits
  are the signed value;
- **truncated case**: DRUM's operand is `{1, m, 1}` — odd — and negating an odd
  number needs no carry, so −`{1,m,1}` is `{1, 0, ~m, 1}`.

A signed (K+1)×(K+1) multiply then gives the correctly signed product, and
Vivado folds the sign into its partial products. There is no output negate and
no zero special case. The design also uses the same structured `lzc_16` as
DLZS, computes the exact-case flag in parallel with it, and computes the shift
amount off the critical path.

Verification: `tb/drum_opt` — all six K elaborated side by side; the operand
block exhaustively over all 65,536 inputs for every K, the top over all
65,536 A × 10 B for every K against the golden model **and**, for K = 4 and 6,
against the published DRUM cores. All passing.

---

## 7. Implementation results

Post-route, out-of-context, LUT-only (`-max_dsp 0`, verified 0 DSPs on every
row), xc7z020clg400-1, 10 ns clock constraint. Every design sits in the same
harness: two 16-bit input registers, the multiplier, one 32-bit output
register. Fmax = 1000 / (10 − WNS).

### All designs

| Design | Slice LUTs | LUT cells | WNS (ns) | Fmax (MHz) | Logic levels | Route share of path |
|---|---|---|---|---|---|---|
| `exact_lut` | 265 | 357 | +0.411 | 104.29 | 15 | 53 % |
| `dlzs_signed` (original) | 213 | 220 | −0.409 | 96.07 | 15 | 63 % |
| **`dlzs_opt`** | **145** | **169** | **+1.770** | **121.51** | **8** | 64 % |
| `drum4_signed` (published) | 259 | 262 | −3.056 | 76.59 | 22 | 60 % |
| `drum6_signed` (published) | 364 | 365 | −6.078 | 62.20 | 25 | 62 % |
| `drum_opt3` | 233 | 236 | −1.502 | 86.94 | 16 | 63 % |
| `drum_opt4` | 273 | 278 | −3.051 | 76.62 | 17 | 66 % |
| `drum_opt6` | 318 | 327 | −3.864 | 72.13 | 20 | 64 % |
| `drum_opt8` | 403 | 408 | −4.424 | 69.33 | 21 | 63 % |

`exact_lut` is the exact multiplier built **without DSP blocks**:
`$signed(a) * $signed(b)` under `-max_dsp 0`, with the DSP count parsed from
the utilization report and confirmed 0 after both synthesis and routing. It is
the fair reference for LUT-only approximate designs. A DSP-mapped exact row
(one DSP48E1) is planned as a separate "what the FPGA gives you for free"
reference and is deliberately not mixed into the LUT-only comparison.

*Slice LUTs* (from `post_route/utilization.txt`) is the physical area and the
column to quote. *LUT cells* is what `summary.txt` counts; dual-output LUT
packing makes it larger, by 92 for the exact multiplier. `drum_opt8` reports
65 flip-flops because the placer replicated one input register.

### Head-to-head comparisons

| Comparison | Area (Slice LUTs) | Fmax | What it shows |
|---|---|---|---|
| `dlzs_opt` vs `exact_lut` | **−45.3 %** | **+16.5 %** | the headline: faster and smaller than exact |
| `dlzs_opt` vs `dlzs_signed` | −31.9 % | +26.5 % | the architectural gain alone (same arithmetic) |
| `dlzs_signed` vs `drum4_signed` | −17.8 % | +25.4 % | matched sign shells: the algorithms alone |
| `drum_opt6` vs `drum6_signed` | −12.6 % | +16.0 % | what the published DRUM6 RTL left on the table |
| `drum_opt4` vs `drum4_signed` | +5.4 % | +0.0 % | no gain at K=4 — the published design was already near its limit |
| `drum_opt3` vs `exact_lut` | −12.1 % | −16.6 % | the cheapest DRUM: smaller than exact, but slower |

### Accuracy against cost

| Design | MRED | Slice LUTs | Fmax (MHz) | Beats exact on |
|---|---|---|---|---|
| exact | 0 | 265 | 104.3 | — |
| DRUM-opt k=8 | 0.37 % | 403 | 69.3 | nothing |
| DRUM-opt k=6 | 1.49 % | 318 | 72.1 | nothing |
| DRUM-opt k=4 | 6.00 % | 273 | 76.6 | nothing |
| DRUM-opt k=3 | 12.14 % | 233 | 86.9 | area only |
| **DLZS-opt** | **16.84 %** | **145** | **121.5** | **area and speed** |

Two findings follow, both specific to this setup (16-bit, LUT-only 7-series,
single-cycle):

1. **The exact LUT multiplier dominates DRUM for every K ≥ 4** — DRUM is less
   accurate, larger and slower. The 7-series carry chains make an exact
   multiplier cheap, while DRUM's two leading-one detectors, two bit-select
   muxes and a multiplier on the critical path map poorly to LUTs. This is not
   a contradiction of the DRUM paper, which evaluated an ASIC flow.
2. **DLZS-opt is the only design that beats exact on both axes.** Its cost is
   accuracy: 16.8 % mean error against 12.1 % for the cheapest DRUM. Whether
   that is acceptable is an application question, answered in Week 10–11.

### Power

Total on-chip power is 0.105–0.113 W for every row, but about 0.103 W of that
is **device static power** — leakage of the whole Zynq-7020, identical for
every design and unrelated to the multiplier. The comparison is in **dynamic**
power, and most fairly in **energy per multiplication**:

    E (pJ) = P_dynamic (mW) × clock period (ns)

Energy per operation does not depend on the clock the estimate was made at, so
it stays fair even though several designs miss the 10 ns target.

**Preliminary figures** — Vivado's default vectorless estimate (12.5 % input
toggle rate assumed), post-route, 10 ns clock:

| Design | Dynamic power | Energy / multiply | vs exact |
|---|---|---|---|
| `exact_lut` | 5 mW | 50 pJ | — |
| `dlzs_signed` | 4 mW | 40 pJ | −20 % |
| **`dlzs_opt`** | **2 mW** | **20 pJ** | **−60 %** |
| `drum4_signed` | 6 mW | 60 pJ | +20 % |
| `drum6_signed` | 9 mW | 90 pJ | +80 % |
| `drum_opt3` | 4 mW | 40 pJ | −20 % |
| `drum_opt4` | 5 mW | 50 pJ | 0 % |
| `drum_opt6` | 7 mW | 70 pJ | +40 % |
| `drum_opt8` | 10 mW | 100 pJ | +100 % |

Read these as a **ranking, not measurements**. `report_power` prints watts to
three decimals, so every value is rounded to the nearest 1 mW — `dlzs_opt`'s
"2 mW" means 1.5–2.5 mW and exact's "5 mW" means 4.5–5.5 mW, so the saving is
somewhere between roughly 1.8× and 3.7×. The input activity is also Vivado's
default guess, not the uniform random operands the error tables use. The
pattern matches the area results: `dlzs_opt` lowest, the exact multiplier
below every DRUM with K ≥ 4.

**Refined run — `make power`** (script `synth/power.tcl`). It reopens each
routed checkpoint and:

- applies **identical activity** to the 32 data inputs of every design: 50 %
  toggle rate and 0.5 static probability, which is what uniform random
  operands produce (each bit changes with probability ½ per cycle);
- reports in **microwatts** (`set_units -power mW`, three decimals), removing
  the 1 mW rounding;
- records dynamic, logic, signal and clock power, energy per multiply and
  Vivado's confidence level in `synth_result/<design>/power_summary.txt`.

Vivado typically rates activity propagated this way as "Medium" confidence.
"High" needs a SAIF file from simulating the routed netlist with the same
vectors; `power.tcl` is written so that swapping `set_switching_activity` for
`read_saif` is the only change.

### Caveats on these numbers

- **The two passing designs' Fmax is understated.** `exact_lut` and `dlzs_opt`
  meet the 10 ns target, and the router stops improving a path once it passes.
  A tighter-period run is needed for their true maximum; the three-way
  ordering is unlikely to change, but the margin may.
- **One placement per design.** Run-to-run variation is a few percent; the
  headline margins are larger than that, the `drum_opt4` vs `drum4_signed`
  difference is not.
- **Power is preliminary** — see "Power" below.
- **`dlzs_opt` vs the DRUM rows is not shell-matched** — DRUM needs two input
  negates, DLZS one. That difference is algorithmic and is stated as such;
  `dlzs_signed` vs `drum4_signed` is the matched-shell comparison.
- **Not yet built:** `drum_opt5`, `drum_opt7`, the DSP-mapped exact reference
  row, and Mitchell RTL.

---

## 8. RTL

    rtl/lzc_8.sv            8-bit leading-one detector
    rtl/lzc_16.sv           16-bit, two cascaded lzc_8 blocks
    rtl/dlzc_mult.sv        unsigned 16x16 -> 32 DLZS core (original)
    rtl/dlzc_mult_top.sv    sign-magnitude shell around it (original)
    rtl/dlzs_snap_exp.sv    |A| -> snapped exponent e, via the merged-round V vector
    rtl/dlzs_b_prep.sv      B branch: sign-extend, conditional negate, zero guard
    rtl/dlzc_shift.sv       two-level barrel shifter, e[3:2] then e[1:0]
    rtl/dlzc_opt_top.sv     optimized signed DLZS top

    baselines/drum_opt/drum_opt_operand.sv   |X| -> sign-carrying operand + shift
    baselines/drum_opt/drum_opt_shift.sv     final shift
    baselines/drum_opt/drum_opt_top.sv       optimized signed DRUM(K) top

Things that are easy to get wrong and were got right:

- **`output_power` is not a leading-zero count** despite the module name: it
  is ⌊log₂ x⌋, the shift amount the datapath consumes.
- **Magnitude nets are unsigned.** |−32768| = 32768 fits 16-bit storage but
  not the signed range; declaring those nets `signed` breaks the design.
- **Sign extension happens before negation.** The B branch extends B to 17
  bits and then negates; negating at 16 bits loses +32768.
- **The B branch reads raw input bits only.** Taking `a_zero` from inside the
  A branch would put the B branch behind A's critical path.
- **Overflow bounds are asserted, not argued.** |p| ≤ 2^30 for DLZS; for
  DRUM, which can overestimate, the largest result for every K (≈1.68·10⁹ at
  K = 3) is checked to fit the 32-bit signed port.

---

## 9. Repository layout

    rtl/                    DLZS design sources (original and optimized)
    baselines/
      drum/                 vendored DRUM cores (upstream licence) + our signed shell
      drum_opt/             our FPGA-optimized DRUM(K)
      exact/                exact multiplier
    synth/
      synth_ooc.tcl         OOC LUT-only synthesis + place and route of every design
      power.tcl             activity-driven power from the routed checkpoints
      constraints/ooc_clock.xdc
      wrappers/             identical register harnesses, one per design family
    tb/
      dirs.mk  common.mk    shared cocotb plumbing
      lzc/ mult/ drum/ exact/ opt/ drum_opt/     one directory per bench
    src/golden_model.py     bit-exact reference models, no float in any datapath
    src/metrics.py          MRED, NMED, max RED, signed bias, error rate
    src/sweep.py            8-bit exhaustive + 16-bit sampled sweeps
    tests/test_golden_model.py    19-test regression suite
    synth_result/<design>/  committed synthesis and post-route reports
    docs/progress.md

The golden model is the **authority**. RTL is verified against the model, not
against the exact product — an approximate multiplier that matched the exact
product would be a bug.

---

## 10. Running it

From the repo root:

    make test      # golden-model regression suite (19 tests)
    make sweep     # error sweeps -> results/
    make sim       # all six cocotb benches
    make lint      # Verilator lint on all six
    make smoke     # fast test + sim, for the pre-commit loop
    make synth     # Vivado OOC synth + place and route -> synth_result/
    make designs   # list the buildable designs
    make synth-one DESIGN=dlzs_opt
    make power     # activity-driven power from the routed checkpoints

| Bench | Tests | Random-count variable |
|---|---|---|
| `tb/lzc` | 3 | `LZC_N_RANDOM` |
| `tb/mult` | 5 | `MULT_N_RANDOM` |
| `tb/drum` | 7 | `DRUM_N_RANDOM` |
| `tb/exact` | 8 | `EXACT_N_RANDOM` |
| `tb/opt` | 8 | `OPT_N_RANDOM` |
| `tb/drum_opt` | 5 | `DRUM_OPT_N_RANDOM` |

Synthesis options go after `-tclargs`:

    vivado -mode batch -source synth/synth_ooc.tcl -tclargs dlzs_opt exact_lut -force
    vivado -mode batch -source synth/synth_ooc.tcl -tclargs -period 8 -force

Every run writes to `synth_result/<design>/`, so copy that folder aside before
a run at a different period.

**Vivado under WSL.** If `vivado` is a shell alias to the Windows
`vivado.bat`, `make` cannot see it. Export the same command so the Makefile
picks it up:

    export VIVADO='cmd.exe /c "C:\AMDDesignTools\2025.2\Vivado\bin\vivado.bat"'

The `Route 35-198` warning about `HD.PARTPIN_LOCS` is expected in OOC runs and
does not affect any reported number: every port lands on a harness register,
and port paths are unconstrained.

### Reproducibility

The 8-bit sweep is exhaustive. The 16-bit sweep combines a fixed-seed uniform
sample (seed **20260828**) with an explicit corner set, and both are recorded
in the output header. DLZS is asymmetric, so input pairs are **ordered**:
(a, b) and (b, a) are different experiments and both appear. The benches
import their 16-bit stimulus from `sweep.sampled_pairs()`, so the verified
vectors and the published error tables are the same set.

---

## 11. Known issues

1. **`metrics.py` signed bias.** Dividing by `abs(p)` flips the sign on
   negative products, so signed `bias` averages to ≈ 0 regardless of the
   core. The comment there claims otherwise. Characterize bias on magnitudes,
   or divide by `p` for a magnitude-consistent sign.
2. **Mitchell worst-case note.** `golden_model.py` says the −11.1 % worst case
   is at mantissas near 0.44; it is at exactly 0.5.
3. **Fmax of passing designs is understated** (§7) — tighter-period run pending.
   **Power is preliminary** (1 mW resolution, default activity) — `make power`
   pending.
4. **The RTL is fixed at 16 bits.** No 8-bit synthesis numbers and no
   exhaustive 8-bit model/RTL equivalence yet.
5. **No simulation log is committed.**
6. **Vendored DRUM lint warnings are waived, not fixed** (`WIDTHEXPAND`,
   `UNUSEDSIGNAL`), scoped to the benches that compile upstream code.

---

## 12. Roadmap

| Week | Scope | Status |
|------|-------|--------|
| 1–2 | Literature lock + golden model | done |
| 3–5 | DLZS RTL + verification | done |
| 6–7 | Baselines, OOC LUT-only synthesis, comparison table | mostly done — optimized DLZS and DRUM built and routed; remaining: Mitchell RTL, DSP-mapped exact row, `drum_opt5/7`, tighter-period run |
| 8–9 | AXI-Lite wrapper, PYNQ-Z2 overlay, ≥10,000 vectors hardware-vs-sim | |
| 10–11 | Attention Q/K from DistilBERT, top-k index overlap vs hardware cost | |
| 12–13 | MBM-style error compensation, accuracy-vs-LUTs Pareto front | |
| 14 | Buffer, thesis writeup, defense dry-run | |

Scope is cut from the **top tier down** if the schedule slips — compensation
first, then the application study — never the baseline characterization.

**Designed-in test hook for Week 12.** The compensation LUT must reduce to
uncompensated DLZS when it is all zeros. That degenerate-parameter test is the
same shape as `test_drum_degenerates_to_exact_at_k_equals_w`, the strongest
test in the suite, and it should exist from the compensation module's first
commit.

---

## 13. Environment

- **Board:** PYNQ-Z2 (primary); Arty A7-100T (optional stretch)
- **Tools:** Vivado, Icarus Verilog / Verilator, cocotb, Python 3, PyTorch
- **Synthesis constraints:** out-of-context, `USE_DSP="no"`,
  matched bit-widths, identical input distributions across all designs. The
  exact multiplier is reported twice — LUT-only, and DSP-mapped as a separate
  reference row.

---

## 14. References

1. J. N. Mitchell, "Computer Multiplication and Division Using Binary
   Logarithms," *IRE Transactions on Electronic Computers*, 1962.
2. S. Hashemi, R. I. Bahar, S. Reda, "DRUM: A Dynamic Range Unbiased
   Multiplier for Approximate Applications," *ICCAD*, 2015.
3. Wang et al., "SOFA: A Compute-Memory Optimized Sparsity Accelerator via
   Cross-Stage Coordinated Tiling," *MICRO*, 2024. — origin of the DLZS scheme.
4. MBM (Mitchell-based multiplier with error compensation) — the model for the
   Week 12–13 compensation tier.

Related work also includes power-of-two weight quantization, against which this
scheme must be positioned rather than compared favourably by default.