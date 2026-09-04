"""
sweep.py — Error characterization sweeps for the DLZS-AM golden model.

Generates the Week 1–2 gate evidence: an error table across all four DLZS snap
interpretations plus Mitchell, DRUM(k), at 8-bit exhaustive and 16-bit sampled.

Usage
-----
    python3 src/sweep.py              # both sweeps
    python3 src/sweep.py --w8         # 8-bit exhaustive only
    python3 src/sweep.py --w16        # 16-bit sampled only
    python3 src/sweep.py --n 2000000  # override 16-bit sample size

Outputs (written to results/)
-----------------------------
    sweep_w8_exhaustive.csv / .txt
    sweep_w16_sampled.csv   / .txt

Reproducibility
---------------
The 8-bit sweep is exhaustive: all 65,536 ordered pairs, no sampling, nothing
to seed. The 16-bit sweep CANNOT be exhaustive (4.3e9 pairs), so it combines:

  * a fixed-seed uniform random sample, and
  * an explicit corner-case set: zeros, ones, all-ones, exact powers of two,
    values one below and one above each power, and the linear-nearest tie
    values 1.5 * 2^k.

The seed is recorded in the output header. An unreproducible sample is not
evidence, so do not remove it. The corner set is included in full and its size
is reported separately, since it is deliberately non-uniform and will skew the
sampled metrics slightly toward boundary behaviour — that is intentional, and
the header states it so the number is not read as an unbiased estimate.

DLZS is asymmetric in its operands: operand A is snapped, B is shifted. Input
pairs are therefore ORDERED — (a,b) and (b,a) are different experiments and
both appear. Do not deduplicate them.
"""

import argparse
import csv
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from golden_model import DESIGNS          # noqa: E402
from metrics import error_metrics, format_table  # noqa: E402


SEED = 20260828
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "results")

CSV_FIELDS = [
    "design", "w", "n_total", "n_red",
    "mred", "max_red", "bias", "nmed", "max_aed", "error_rate",
]


# ---------------------------------------------------------------------------
# Input set construction
# ---------------------------------------------------------------------------

def exhaustive_pairs(w):
    """All (a, b) ordered pairs at width w. Only tractable for w <= 8."""
    n = 1 << w
    return [(a, b) for a in range(n) for b in range(n)]


def corner_values(w):
    """Boundary operands that must appear in any sampled sweep.

    Rationale for each class:
      0, 1                  zero guard and the k == 0 shift edge
      2^k                   exact powers -- all snap modes must agree
      2^k - 1, 2^k + 1      just below/above a binade boundary, where the
                            leading-one position changes
      1.5 * 2^k             linear-nearest TIE values; the only inputs where a
                            tie-break disagreement between model and RTL shows
      2^w - 1               all-ones, the maximum-magnitude operand
    """
    vals = {0, 1, (1 << w) - 1}
    for k in range(w):
        p = 1 << k
        vals.add(p)
        if p - 1 >= 0:
            vals.add(p - 1)
        if p + 1 < (1 << w):
            vals.add(p + 1)
        if k >= 1:
            tie = p + (1 << (k - 1))          # 1.5 * 2^k
            if tie < (1 << w):
                vals.add(tie)
    return sorted(vals)


def sampled_pairs(w, n_random, seed=SEED):
    """Fixed-seed random sample plus the full corner-case cross product.

    Returns (pairs, n_corner) so the caller can report how much of the set is
    deliberately non-uniform.
    """
    corners = corner_values(w)
    corner_pairs = [(a, b) for a in corners for b in corners]

    rng = random.Random(seed)
    hi = (1 << w) - 1
    random_pairs = [(rng.randint(0, hi), rng.randint(0, hi))
                    for _ in range(n_random)]

    return corner_pairs + random_pairs, len(corner_pairs)


# ---------------------------------------------------------------------------
# Sweep driver
# ---------------------------------------------------------------------------

def run_sweep(pairs, w):
    """Evaluate every design in DESIGNS over `pairs`, return {name: metrics}.

    The exact reference is computed once and reused, and `exact` is skipped as
    a design under test — its metrics would be identically zero and the RED
    denominator check in error_metrics would still hold, but the row carries no
    information and clutters the table.
    """
    exact_vals = [a * b for a, b in pairs]

    results = {}
    for name, fn in DESIGNS.items():
        if name == "exact":
            continue
        approx_vals = [fn(a, b, w) for a, b in pairs]
        results[name] = error_metrics(exact_vals, approx_vals, w)
    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(path, results, w):
    """One row per design. n_total and n_red are per-row rather than in a
    footer so that nothing is lost when the CSV is read by plotting code or
    pasted into the report."""
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for name, m in results.items():
            row = {"design": name, "w": w}
            row.update({k: m[k] for k in CSV_FIELDS if k in m})
            writer.writerow(row)


def write_txt(path, text):
    with open(path, "w") as f:
        f.write(text + "\n")


def make_header(w, kind, n_total, n_corner=None, n_random=None, seed=None):
    """Provenance block. A table with no width, no sample size and no seed on
    it is unusable six months later, so this goes into every artifact."""
    lines = [
        f"DLZS-AM error characterization",
        f"width w = {w}",
        f"input set: {kind}",
        f"designs: {', '.join(k for k in DESIGNS if k != 'exact')}",
        f"total pairs: {n_total}",
    ]
    if n_corner is not None:
        lines.append(f"  corner-case pairs: {n_corner} (deliberately "
                     f"non-uniform; boundary behaviour is over-represented)")
        lines.append(f"  random pairs:      {n_random} (seed = {seed})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def sweep_w8():
    w = 8
    pairs = exhaustive_pairs(w)
    results = run_sweep(pairs, w)

    header = make_header(w, "exhaustive (all ordered pairs)", len(pairs))
    text = header + "\n\n" + format_table(results)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    write_csv(os.path.join(RESULTS_DIR, "sweep_w8_exhaustive.csv"), results, w)
    write_txt(os.path.join(RESULTS_DIR, "sweep_w8_exhaustive.txt"), text)
    print(text)
    return results


def sweep_w16(n_random):
    w = 16
    pairs, n_corner = sampled_pairs(w, n_random)
    results = run_sweep(pairs, w)

    header = make_header(w, "sampled + corner cases", len(pairs),
                         n_corner=n_corner, n_random=n_random, seed=SEED)
    text = header + "\n\n" + format_table(results)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    write_csv(os.path.join(RESULTS_DIR, "sweep_w16_sampled.csv"), results, w)
    write_txt(os.path.join(RESULTS_DIR, "sweep_w16_sampled.txt"), text)
    print(text)
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--w8", action="store_true", help="8-bit exhaustive only")
    ap.add_argument("--w16", action="store_true", help="16-bit sampled only")
    ap.add_argument("--n", type=int, default=1_000_000,
                    help="random sample size for the 16-bit sweep")
    args = ap.parse_args()

    run_both = not (args.w8 or args.w16)

    if args.w8 or run_both:
        sweep_w8()
    if run_both:
        print()
    if args.w16 or run_both:
        sweep_w16(args.n)


if __name__ == "__main__":
    main()