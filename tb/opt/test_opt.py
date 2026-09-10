"""
test_opt.py -- cocotb verification of the optimised ("sign-extend B") DLZS
multiplier, block by block and then assembled.

All DUTs are pure combinational; there is no clock and no reset. Stimulus is
applied, a settling delay is inserted, outputs are compared.

Blocks and references
---------------------
dlzs_snap_exp   e == golden_model.dlzs_snap_exponent(m, 16), m = 1..32768
                (exhaustive). The RTL computes e with the merged-round vector
                V = m | ((m & (m >> 1)) << 2); the reference is the plain
                lead_one + round-bit definition, so this checks the trick
                against the spec rather than against itself.
dlzs_b_prep     bp == 0 / -B / B for (a_zero, a_neg), all 65,536 B in every
                flag combination (exhaustive).
dlzc_shift      p == bp * 2^e over the legal input range bp in [-32767, 32768],
                e in [0, 15]: every e against the extremes plus a random
                sample of bp.
dlzc_opt_top    against golden_model.signed_wrap(dlzs_nearest_linear, a, b, 16)
                AND against the old verified dlzc_mult_top on the same
                operands. Two independent implementations of the same spec
                agreeing is stronger than either alone.

Why dlzs_snap_exp is only tested up to 32768
--------------------------------------------
That is its documented precondition. Above 49151 the vector V would need a
17th bit; the top can never produce such a magnitude, because |A| <= 32768 for
a signed 16-bit A. Testing outside the precondition would report failures that
cannot happen in the assembled design.

Why e is not checked at m == 0
------------------------------
The top masks A == 0 in the B branch (bp = 0), so e's value there is never
observed. The assembled-design tests cover A == 0 end to end.
"""

import os
import random
import sys

import cocotb
from cocotb.triggers import Timer

# src/ is put on PYTHONPATH by tb/common.mk. Kept as a fallback so the file
# still imports when opened directly by an editor or pytest.
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from golden_model import (   # noqa: E402
    DESIGNS,
    dlzs_snap_exponent,
    signed_wrap,
    to_signed,
)
from sweep import sampled_pairs   # noqa: E402


W = 16
DESIGN = DESIGNS["dlzs_nearest_linear"]
SETTLE_NS = 1

S_MIN, S_MAX = -(1 << (W - 1)), (1 << (W - 1)) - 1     # -32768, 32767

# `or` rather than a get() default: an exported-but-empty make variable
# arrives as "", which would defeat the default.
N_RANDOM = int(os.environ.get("OPT_N_RANDOM", "") or 200_000)

# Fixed seed for the bench's own random draws (the sweep set carries its own).
SEED = 20260910

MAX_REPORTED_FAILURES = 20


def read_signed(handle):
    """Two's complement read; probes the cocotb 2.x and 1.x spellings."""
    value = handle.value
    to_signed_fn = getattr(value, "to_signed", None)
    if callable(to_signed_fn):
        return to_signed_fn()
    return value.signed_integer


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
            self.dut._log.error("%s mismatch: %s -> got %d, expected %d",
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


def idle_all(dut):
    """Park every stimulus port so a test only exercises the block it names."""
    dut.sn_m.value = 0
    dut.bpr_b.value = 0
    dut.bpr_a_neg.value = 0
    dut.bpr_a_zero.value = 0
    dut.sh_bp.value = 0
    dut.sh_e.value = 0
    dut.s_a.value = 0
    dut.s_b.value = 0


def signed_corners():
    """Binade edges, powers of two, and tie values 1.5 * 2^k, each with its
    negative, plus the extremes. -32768 is the operand of record: the one
    magnitude that does not fit a 16-bit unsigned range."""
    vals = {0, 1, -1, 2, -2, 3, -3, S_MAX, S_MIN, S_MIN + 1}
    for k in range(W - 1):
        for v in (1 << k, (1 << k) - 1, (1 << k) + 1):
            vals.update({v, -v})
        tie = 3 << k
        for v in (tie - 1, tie, tie + 1):
            if v <= S_MAX:
                vals.update({v, -v})
    return sorted(v for v in vals if S_MIN <= v <= S_MAX)


# ---------------------------------------------------------------------------
# dlzs_snap_exp
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_snap_exp_exhaustive(dut):
    """Every legal magnitude 1..32768 against the reference exponent.

    Powers of two and the tie values 3 * 2^j are included by exhaustion; they
    are logged by name as well because they are where the merged-round vector
    and a round-bit tap would most plausibly disagree."""
    idle_all(dut)
    checker = Checker(dut, "dlzs_snap_exp")
    named = {1 << k for k in range(W)} | {3 << j for j in range(W - 2)}
    named_seen = 0
    for m in range(1, (1 << (W - 1)) + 1):
        dut.sn_m.value = m
        await Timer(SETTLE_NS, "ns")
        checker.compare(f"m={m}", int(dut.sn_e.value), dlzs_snap_exponent(m, W))
        if m in named:
            named_seen += 1
    checker.finish()
    dut._log.info("dlzs_snap_exp: %d powers-of-two / tie values covered",
                  named_seen)


# ---------------------------------------------------------------------------
# dlzs_b_prep
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_b_prep_exhaustive(dut):
    """All 65,536 B in every (a_zero, a_neg) combination.

    (a_zero=1, a_neg=1) cannot occur in the top -- A == 0 is not negative --
    but the module's contract is that a_zero takes priority, so it is checked.
    The vectors of record are B = -32768 with a_neg (must give +32768, which
    proves the 17th bit) and B = -5 pass-through (must stay -5, which proves
    sign extension rather than zero extension)."""
    idle_all(dut)
    checker = Checker(dut, "dlzs_b_prep")
    for a_zero in (0, 1):
        for a_neg in (0, 1):
            dut.bpr_a_zero.value = a_zero
            dut.bpr_a_neg.value = a_neg
            for pattern in range(1 << W):
                b = to_signed(pattern, W)
                dut.bpr_b.value = pattern
                await Timer(SETTLE_NS, "ns")
                expected = 0 if a_zero else (-b if a_neg else b)
                checker.compare(f"b={b} a_zero={a_zero} a_neg={a_neg}",
                                read_signed(dut.bpr_bp), expected)
    checker.finish()


# ---------------------------------------------------------------------------
# dlzc_shift
# ---------------------------------------------------------------------------

BP_MIN, BP_MAX = -(1 << (W - 1)) + 1, 1 << (W - 1)     # -32767, +32768


@cocotb.test()
async def test_shift_extremes(dut):
    """Every e against the extremes of the legal bp range.

    The vectors of record: bp = 32768, e = 15 must give exactly 2^30 (the
    largest output, 0x40000000), and bp = -1, e = 15 must give -32768
    (0xFFFF8000), proving the top bits fill with ones."""
    idle_all(dut)
    checker = Checker(dut, "dlzc_shift extremes")
    extremes = [BP_MIN, BP_MIN + 1, -2, -1, 0, 1, 2, BP_MAX - 1, BP_MAX]
    for e in range(W):
        for bp in extremes:
            dut.sh_bp.value = bp & 0x1FFFF
            dut.sh_e.value = e
            await Timer(SETTLE_NS, "ns")
            checker.compare(f"bp={bp} e={e}", read_signed(dut.sh_p), bp << e)
    checker.finish()


@cocotb.test()
async def test_shift_random(dut):
    """Random bp over the legal range, every e."""
    idle_all(dut)
    checker = Checker(dut, "dlzc_shift random")
    rng = random.Random(SEED)
    n = max(1, N_RANDOM // W)
    for _ in range(n):
        bp = rng.randint(BP_MIN, BP_MAX)
        dut.sh_bp.value = bp & 0x1FFFF
        for e in range(W):
            dut.sh_e.value = e
            await Timer(SETTLE_NS, "ns")
            checker.compare(f"bp={bp} e={e}", read_signed(dut.sh_p), bp << e)
    checker.finish()


# ---------------------------------------------------------------------------
# dlzc_opt_top
# ---------------------------------------------------------------------------

async def drive_top(dut, name, pairs):
    """Check dlzc_opt_top against the golden model and against the old top."""
    model = Checker(dut, f"{name} vs golden model")
    old = Checker(dut, f"{name} vs dlzc_mult_top")
    for a, b in pairs:
        dut.s_a.value = a & 0xFFFF
        dut.s_b.value = b & 0xFFFF
        await Timer(SETTLE_NS, "ns")
        got = read_signed(dut.s_mul)
        model.compare(f"a={a} b={b}", got, signed_wrap(DESIGN, a, b, W))
        old.compare(f"a={a} b={b}", got, read_signed(dut.s_mul_ref))
    model.finish()
    old.finish()


@cocotb.test()
async def test_top_exhaustive_a(dut):
    """Every A (all 65,536) against a fixed set of B.

    The snapped exponent depends only on A, so sweeping A exhaustively covers
    every path through dlzs_snap_exp and every |A| negate case in the top;
    the B set covers the sign and extreme cases of the B branch."""
    idle_all(dut)
    b_set = [S_MIN, S_MIN + 1, -12345, -300, -1, 0, 1, 7, 12345, S_MAX]
    pairs = [(to_signed(pa, W), b) for pa in range(1 << W) for b in b_set]
    dut._log.info("dlzc_opt_top: %d pairs (all A x %d B)", len(pairs), len(b_set))
    await drive_top(dut, "dlzc_opt_top exhaustive-A", pairs)


@cocotb.test()
async def test_top_corners(dut):
    """Directed cross product over binade edges, tie values and extremes.

    Includes zero against negative operands (the case the old design handled
    as 'negative zero') and -32768 against everything."""
    idle_all(dut)
    ops = signed_corners()
    pairs = [(a, b) for a in ops for b in ops]
    dut._log.info("dlzc_opt_top: %d directed corner pairs (%d x %d operands)",
                  len(pairs), len(ops), len(ops))
    await drive_top(dut, "dlzc_opt_top corners", pairs)


@cocotb.test()
async def test_top_sweep(dut):
    """The sweep set from src/sweep.py reinterpreted as two's complement, so
    the verified vectors and the published error tables are the same set."""
    idle_all(dut)
    raw, n_corner = sampled_pairs(W, N_RANDOM)
    pairs = [(to_signed(a, W), to_signed(b, W)) for a, b in raw]
    dut._log.info("dlzc_opt_top: %d sweep pairs (%d corner + %d random)",
                  len(pairs), n_corner, N_RANDOM)
    await drive_top(dut, "dlzc_opt_top sweep", pairs)


@cocotb.test()
async def test_top_output_range(dut):
    """The output stays inside the 32-bit signed port, with |p| <= 2^30.

    Also pins the one output below exact's minimum: A = 32767 snaps up to
    2^15, so A * B at B = -32768 gives -2^30, whereas the exact product's
    minimum is -2^30 + 2^15. Still in range, and asserted here so the range
    claim in the docs is checked rather than argued."""
    idle_all(dut)
    extremes = [S_MIN, S_MIN + 1, S_MAX, -0x6000, 0x6000, -0x5FFF, 0x5FFF]
    pairs = [(a, b) for a in extremes for b in extremes]
    await drive_top(dut, "dlzc_opt_top range", pairs)

    worst = 0
    for a, b in pairs:
        worst = max(worst, abs(signed_wrap(DESIGN, a, b, W)))
    assert worst == (1 << 30), f"worst |product| {worst}, expected 2^30"

    dut.s_a.value = S_MAX & 0xFFFF
    dut.s_b.value = S_MIN & 0xFFFF
    await Timer(SETTLE_NS, "ns")
    got = read_signed(dut.s_mul)
    assert got == -(1 << 30), f"A=32767 B=-32768 gave {got}, expected -2^30"
    dut._log.info("dlzc_opt_top: worst |p| = 2^30, and -2^30 is produced "
                  "at A=32767 B=-32768")
