"""
test_drum_opt.py -- cocotb verification of our FPGA-optimised DRUM(K),
K = 3..8, block by block and assembled.

All DUTs are pure combinational. Every K is elaborated side by side in
drum_opt_tb_top and driven from shared stimulus ports, so each time step
checks all six parameterisations at once.

References
----------
drum_opt_operand  mm_s * 2^p == sign(X) * t * 2^s, where (t, s) is
                  golden_model.drum_extract(|X|, K), AND p == s exactly.
                  drum_extract is the plain truncate-and-force-LSB definition,
                  so this checks the carry-free signed form against the spec,
                  not against a re-derivation of itself. Exhaustive over all
                  65,536 X for every K.
drum_opt_top      golden_model.signed_wrap(drum(.., K), a, b, 16) for every K,
                  AND, for K = 4 and 6, the published DRUM cores inside
                  drum_signed_top on the same operands. Our design agreeing
                  with the authors' own RTL is the claim that makes it a fair
                  DRUM row rather than a new multiplier.

Why the operand check needs both conditions
-------------------------------------------
mm_s * 2^p alone would accept an operand that was scaled differently (say
mm_s doubled, p one lower). The top would still compute the right product,
but the operand block would not match its documented contract, so p is
pinned separately.
"""

import os
import random
import sys

import cocotb
from cocotb.triggers import Timer

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from golden_model import drum, drum_extract, signed_wrap, to_signed   # noqa: E402
from sweep import sampled_pairs                                       # noqa: E402


W = 16
KS = range(3, 9)
PUBLISHED = (4, 6)
SETTLE_NS = 1

S_MIN, S_MAX = -(1 << (W - 1)), (1 << (W - 1)) - 1

N_RANDOM = int(os.environ.get("DRUM_OPT_N_RANDOM", "") or 200_000)
SEED = 20260911

MAX_REPORTED_FAILURES = 20


def read_signed(handle):
    """Two's complement read; probes the cocotb 2.x and 1.x spellings."""
    value = handle.value
    to_signed_fn = getattr(value, "to_signed", None)
    if callable(to_signed_fn):
        return to_signed_fn()
    return value.signed_integer


def drum_model(k):
    """drum() with k bound, in the (a, b, w) shape signed_wrap expects."""
    return lambda a, b, w: drum(a, b, k, w)


MODELS = {k: drum_model(k) for k in KS}


class Checker:
    """Accumulates mismatches so one run reports every failing class of input
    rather than aborting on the first vector."""

    def __init__(self, dut, name):
        self.dut = dut
        self.name = name
        self.checked = 0
        self.failures = []

    def compare(self, stimulus, got, expected):
        self.checked += 1
        if got == expected:
            return
        self.failures.append((stimulus, got, expected))
        if len(self.failures) <= MAX_REPORTED_FAILURES:
            self.dut._log.error("%s mismatch: %s -> got %s, expected %s",
                                self.name, stimulus, got, expected)

    def finish(self):
        n_fail = len(self.failures)
        if n_fail:
            stim, got, exp = self.failures[0]
            hidden = max(0, n_fail - MAX_REPORTED_FAILURES)
            summary = f"{self.name}: {n_fail} of {self.checked} vectors mismatched"
            if hidden:
                summary += f" ({hidden} not individually logged)"
            summary += f"; first failure {stim} got={got} expected={exp}"
            raise AssertionError(summary)
        self.dut._log.info("%s: %d vectors checked, all match",
                           self.name, self.checked)


def finish_all(checkers):
    """Log every checker, then fail once with all failing names, so a bug in
    one K does not hide the status of the others."""
    failed = []
    for c in checkers:
        try:
            c.finish()
        except AssertionError as e:
            failed.append(str(e))
    if failed:
        raise AssertionError(" | ".join(failed))


def idle_all(dut):
    dut.op_x.value = 0
    dut.s_a.value = 0
    dut.s_b.value = 0


def signed_corners():
    """Powers of two and their neighbours, the extremes, and the exact/
    truncated seam 2^K +- 1 for every K, each with its negative."""
    vals = {0, 1, -1, 2, -2, 3, -3, S_MAX, S_MIN, S_MIN + 1}
    for j in range(W - 1):
        for v in (1 << j, (1 << j) - 1, (1 << j) + 1, 3 << j):
            if v <= S_MAX:
                vals.update({v, -v})
    return sorted(v for v in vals if S_MIN <= v <= S_MAX)


# ---------------------------------------------------------------------------
# drum_opt_operand
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_operand_exhaustive(dut):
    """Every 16-bit X, every K. The seam of interest is |X| = 2^K - 1 vs 2^K
    (exact vs truncated), and X = -32768, whose magnitude does not fit a
    16-bit signed range; both are covered by exhaustion."""
    idle_all(dut)
    checkers = {k: Checker(dut, f"drum_opt_operand K={k}") for k in KS}
    for pattern in range(1 << W):
        x = to_signed(pattern, W)
        dut.op_x.value = pattern
        await Timer(SETTLE_NS, "ns")
        mag = abs(x)
        for k in KS:
            if mag == 0:
                t, s = 0, 0
            else:
                t, s = drum_extract(mag, k, W + 1)   # W+1: |-32768| = 2^15
            sign = -1 if x < 0 else 1
            got_mm = read_signed(getattr(dut, f"op_mm{k}"))
            got_p = int(getattr(dut, f"op_p{k}").value)
            checkers[k].compare(f"x={x}", (got_mm, got_p), (sign * t, s))
    finish_all(checkers.values())


# ---------------------------------------------------------------------------
# drum_opt_top
# ---------------------------------------------------------------------------

async def drive_top(dut, name, pairs):
    """Every K against the golden model; K = 4, 6 also against the published
    cores. One time step per pair covers all eight comparisons."""
    model = {k: Checker(dut, f"{name} K={k} vs golden model") for k in KS}
    pub = {k: Checker(dut, f"{name} K={k} vs published DRUM{k}")
           for k in PUBLISHED}
    for a, b in pairs:
        dut.s_a.value = a & 0xFFFF
        dut.s_b.value = b & 0xFFFF
        await Timer(SETTLE_NS, "ns")
        for k in KS:
            got = read_signed(getattr(dut, f"mul{k}"))
            model[k].compare(f"a={a} b={b}", got, signed_wrap(MODELS[k], a, b, W))
            if k in pub:
                pub[k].compare(f"a={a} b={b}", got,
                               read_signed(getattr(dut, f"pub{k}")))
    finish_all(list(model.values()) + list(pub.values()))


@cocotb.test()
async def test_top_exhaustive_a(dut):
    """Every A against a fixed set of B, all K. Since the operand blocks are
    identical for A and B, the exhaustive operand test plus this covers both
    sides; the B set holds the extremes, the seam values and a few randoms."""
    idle_all(dut)
    rng = random.Random(SEED)
    b_set = [S_MIN, S_MIN + 1, -1, 0, 1, S_MAX, 255, -256]
    b_set += [rng.randint(S_MIN, S_MAX) for _ in range(2)]
    pairs = [(to_signed(pa, W), b) for pa in range(1 << W) for b in b_set]
    dut._log.info("drum_opt_top: %d pairs (all A x %d B), K = 3..8",
                  len(pairs), len(b_set))
    await drive_top(dut, "exhaustive-A", pairs)


@cocotb.test()
async def test_top_corners(dut):
    """Directed cross product over binade edges, seams and extremes."""
    idle_all(dut)
    ops = signed_corners()
    pairs = [(a, b) for a in ops for b in ops]
    dut._log.info("drum_opt_top: %d directed corner pairs", len(pairs))
    await drive_top(dut, "corners", pairs)


@cocotb.test()
async def test_top_sweep(dut):
    """The sweep set from src/sweep.py reinterpreted as two's complement."""
    idle_all(dut)
    raw, n_corner = sampled_pairs(W, N_RANDOM)
    pairs = [(to_signed(a, W), to_signed(b, W)) for a, b in raw]
    dut._log.info("drum_opt_top: %d sweep pairs (%d corner + %d random)",
                  len(pairs), n_corner, N_RANDOM)
    await drive_top(dut, "sweep", pairs)


@cocotb.test()
async def test_top_output_range(dut):
    """DRUM can OVERestimate (the forced LSB), so its largest result exceeds
    exact's 2^30. The claim that every K still fits the 32-bit signed port is
    checked here on the worst operands rather than argued."""
    idle_all(dut)
    extremes = [S_MIN, S_MIN + 1, S_MAX, -0x6000, 0x6000, -0x7FC0, 0x7FC0]
    pairs = [(a, b) for a in extremes for b in extremes]
    await drive_top(dut, "range", pairs)

    for k in KS:
        worst = max(abs(signed_wrap(MODELS[k], a, b, W)) for a, b in pairs)
        assert worst < (1 << 31), f"K={k}: |product| {worst} does not fit 32-bit signed"
        dut._log.info("K=%d: worst |product| over extremes = %d (%.3f x 2^30)",
                      k, worst, worst / (1 << 30))
