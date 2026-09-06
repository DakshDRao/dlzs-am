"""
test_mult.py -- cocotb verification of dlzc_mult (unsigned) and
dlzc_mult_top (signed) against the golden model.

Both DUTs are pure combinational; there is no clock and no reset. Stimulus is
applied, a delta-settling delay is inserted, outputs are compared.

Reference
---------
unsigned : golden_model.dlzs_nearest_linear(a, b, 16)
signed   : golden_model.signed_wrap(dlzs_nearest_linear, a, b, 16)

The signed reference is the wrapper, not a re-derivation. dlzc_mult_top is a
sign-magnitude shell around the SAME core, so if this file computed the signed
expectation independently it would be testing two implementations of the
wrapper against each other rather than testing the RTL against the spec.

Snap mode
---------
The RTL implements nearest-linear with ties rounding UP. That choice is spec,
not accident (golden_model.dlzs_nearest_linear), so DESIGN is pinned here as a
single name. If the spec is ever changed to floor/ceil/nearest-log, changing
this one line must be enough -- if it is not, the testbench has grown an
assumption it should not have.

Width subtlety on the signed path
---------------------------------
abs(-2^15) == 32768 does not fit an unsigned 16-bit operand's RANGE even though
it fits its storage, so signed_wrap invokes the core at w+1. The RTL relies on
exactly the same thing implicitly: abs_value1 is declared unsigned [15:0], and
0x8000 read as unsigned is 32768. Declaring those intermediates `signed` would
break the DUT, and test_signed_corners covers precisely that vector.

Overflow claim
--------------
The signed product magnitude never exceeds 2^30, because shamt == 16 would
require lead_one == 15 AND a round-up, and the only magnitude with lead_one 15
is 32768, which is an exact power of two and therefore never rounds up. That is
a load-bearing and non-obvious property -- test_signed_no_overflow asserts it
directly so it fails loudly if the operand width or the tie-break ever change.

Coverage
--------
unsigned : the sweep set from src/sweep.sampled_pairs(), imported verbatim so
           the verified vectors and the published error tables are the same
           set, plus a directed corner test.
signed   : the same sweep pairs reinterpreted as two's complement, which is a
           uniform sample of the signed space since the underlying draw is
           uniform over all 16-bit patterns, plus directed corners.
"""

import os
import sys

import cocotb
from cocotb.triggers import Timer

# src/ is put on PYTHONPATH by tb/common.mk, so the golden model and the sweep
# stimulus resolve without per-file sys.path surgery. Kept as a fallback so the
# file still imports when opened directly by an editor or pytest.
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from golden_model import DESIGNS, signed_wrap, to_signed   # noqa: E402
from sweep import sampled_pairs                            # noqa: E402


W = 16

# The snap mode the RTL implements. See "Snap mode" above.
DESIGN_NAME = "dlzs_nearest_linear"
DESIGN = DESIGNS[DESIGN_NAME]

SETTLE_NS = 1


def read_signed(handle):
    """Two's complement read of a signal handle.

    cocotb 2.x renamed LogicArray.signed_integer to .to_signed() and deprecates
    the property. Both spellings are probed so the testbench runs unchanged on
    either release rather than emitting a wall of DeprecationWarnings that
    train the reader to ignore warnings.
    """
    value = handle.value
    to_signed_fn = getattr(value, "to_signed", None)
    if callable(to_signed_fn):
        return to_signed_fn()
    return value.signed_integer

# Matches sweep.py's default so the multiplier stimulus is the same set used
# for the published tables. `or` rather than a get() default: an
# exported-but-empty make variable arrives as "", which is present in
# os.environ and would defeat the default. Lower than the LZC default because
# this is a two-operand block -- the pair space is 2^32, so no setting makes
# the run exhaustive and there is nothing to be gained by pretending otherwise.
N_RANDOM = int(os.environ.get("MULT_N_RANDOM", "") or 200_000)

MAX_REPORTED_FAILURES = 20


class Checker:
    """Accumulates mismatches so one run reports every failing class of input
    rather than aborting on the first vector."""

    def __init__(self, dut, name):
        self.dut = dut
        self.name = name
        self.checked = 0
        self.failures = []

    def compare(self, a, b, got, expected):
        self.checked += 1
        if got == expected:
            return
        self.failures.append((a, b, got, expected))
        if len(self.failures) <= MAX_REPORTED_FAILURES:
            self.dut._log.error(
                "%s mismatch: a=%d (0x%04X) b=%d (0x%04X) -> got %d, expected %d",
                self.name, a, a & 0xFFFF, b, b & 0xFFFF, got, expected,
            )

    def finish(self):
        n_fail = len(self.failures)
        if n_fail:
            hidden = max(0, n_fail - MAX_REPORTED_FAILURES)
            a, b, got, exp = self.failures[0]
            summary = (f"{self.name}: {n_fail} of {self.checked} pairs "
                       f"mismatched")
            if hidden:
                summary += f" ({hidden} not individually logged)"
            summary += f"; first failure a={a} b={b} got={got} expected={exp}"
            raise AssertionError(summary)
        self.dut._log.info("%s: %d pairs checked, all match the golden model",
                           self.name, self.checked)


async def drive_unsigned(dut, name, pairs):
    checker = Checker(dut, name)
    for a, b in pairs:
        dut.u_a.value = a
        dut.u_b.value = b
        # Positional unit argument: cocotb 1.x names it `units`, 2.x `unit`.
        await Timer(SETTLE_NS, "ns")
        checker.compare(a, b, int(dut.u_mul.value), DESIGN(a, b, W))
    checker.finish()


async def drive_signed(dut, name, pairs):
    checker = Checker(dut, name)
    for a, b in pairs:
        # Assign the raw two's complement pattern; cocotb's signed handle
        # accepts a negative int too, but writing the pattern keeps the
        # stimulus identical to what the unsigned test drives.
        dut.s_a.value = a & 0xFFFF
        dut.s_b.value = b & 0xFFFF
        await Timer(SETTLE_NS, "ns")
        got = read_signed(dut.s_mul)
        checker.compare(a, b, got, signed_wrap(DESIGN, a, b, W))
    checker.finish()


def corner_operands_unsigned():
    """Binade edges, tie values, and saturation points.

    The tie values 1.5 * 2^k are the vectors that separate ties-up from
    ties-down, which is the single spec detail most likely to diverge between
    model and RTL. They are listed explicitly rather than left to random
    stimulus, where a wrong tie-break costs about one pair in 2^16 and hides
    inside a pass rate.
    """
    vals = {0, 1, 2, 3, 0xFFFF, 0xFFFE, 0x8000, 0x7FFF}
    for k in range(W):
        p = 1 << k
        vals.update({p, p - 1, p + 1})
        tie = 3 << k                      # 1.5 * 2^(k+1)
        if tie < (1 << W):
            vals.update({tie - 1, tie, tie + 1})
    return sorted(v for v in vals if 0 <= v < (1 << W))


def corner_operands_signed():
    """Unsigned corners reinterpreted, plus the negatives of each magnitude.

    -32768 is the vector of record: it is the one operand whose magnitude does
    not fit an unsigned 16-bit range, and the one most likely to be broken by
    a well-meaning `signed` on an internal net.
    """
    vals = set()
    for u in corner_operands_unsigned():
        s = to_signed(u, W)
        vals.add(s)
        if -s <= (1 << (W - 1)) - 1:
            vals.add(-s)
    vals.update({0, 1, -1, (1 << (W - 1)) - 1, -(1 << (W - 1))})
    lo, hi = -(1 << (W - 1)), (1 << (W - 1)) - 1
    return sorted(v for v in vals if lo <= v <= hi)


@cocotb.test()
async def test_unsigned_corners(dut):
    """Directed cross product over binade edges and tie values."""
    dut.s_a.value = 0
    dut.s_b.value = 0

    ops = corner_operands_unsigned()
    pairs = [(a, b) for a in ops for b in ops]
    dut._log.info("dlzc_mult: %d directed corner pairs (%d x %d operands)",
                  len(pairs), len(ops), len(ops))
    await drive_unsigned(dut, "dlzc_mult corners", pairs)


@cocotb.test()
async def test_unsigned_sweep(dut):
    """The sweep set, imported from sweep.py verbatim."""
    dut.s_a.value = 0
    dut.s_b.value = 0

    pairs, n_corner = sampled_pairs(W, N_RANDOM)
    dut._log.info(
        "dlzc_mult: %d pairs from the sweep set (%d corner + %d random, "
        "seed per sweep.py) -- %.6f%% of the %d-pair space",
        len(pairs), n_corner, N_RANDOM,
        100.0 * len(pairs) / (1 << (2 * W)), 1 << (2 * W),
    )
    await drive_unsigned(dut, "dlzc_mult sweep", pairs)


@cocotb.test()
async def test_signed_corners(dut):
    """Directed cross product including -32768 against everything.

    Also covers negative zero: 0 paired with a negative operand asserts the
    sign bit while the magnitude path returns 0, and the RTL negates it. That
    is harmless only because the two's complement of 0 is 0, which is worth
    proving rather than assuming.
    """
    dut.u_a.value = 0
    dut.u_b.value = 0

    ops = corner_operands_signed()
    pairs = [(a, b) for a in ops for b in ops]
    dut._log.info("dlzc_mult_top: %d directed corner pairs (%d x %d operands)",
                  len(pairs), len(ops), len(ops))
    await drive_signed(dut, "dlzc_mult_top corners", pairs)


@cocotb.test()
async def test_signed_sweep(dut):
    """The sweep set reinterpreted as two's complement."""
    dut.u_a.value = 0
    dut.u_b.value = 0

    raw, n_corner = sampled_pairs(W, N_RANDOM)
    pairs = [(to_signed(a, W), to_signed(b, W)) for a, b in raw]
    dut._log.info(
        "dlzc_mult_top: %d pairs from the sweep set reinterpreted signed "
        "(%d corner + %d random)", len(pairs), n_corner, N_RANDOM,
    )
    await drive_signed(dut, "dlzc_mult_top sweep", pairs)


@cocotb.test()
async def test_signed_no_overflow(dut):
    """The product magnitude never reaches 2^31, so the signed output cannot
    wrap. See "Overflow claim" in the module docstring.

    Checked on the RTL rather than argued on paper: the extremal case is
    +-32768 against the largest-shifting magnitude, and the model is checked
    alongside so a change that breaks the bound fails here first, in the one
    test whose name says what it is protecting.
    """
    dut.u_a.value = 0
    dut.u_b.value = 0

    lo = -(1 << (W - 1))
    extremes = [lo, lo + 1, (1 << (W - 1)) - 1, -0x6000, 0x6000, -0x4000]
    pairs = [(a, b) for a in extremes for b in extremes]

    worst = 0
    checker = Checker(dut, "dlzc_mult_top overflow")
    for a, b in pairs:
        dut.s_a.value = a & 0xFFFF
        dut.s_b.value = b & 0xFFFF
        await Timer(SETTLE_NS, "ns")
        expected = signed_wrap(DESIGN, a, b, W)
        checker.compare(a, b, read_signed(dut.s_mul), expected)
        worst = max(worst, abs(expected))
    checker.finish()

    dut._log.info("dlzc_mult_top: worst |product| over extremes = %d (2^%d)",
                  worst, worst.bit_length() - 1)
    assert worst <= (1 << 30), (
        f"product magnitude {worst} exceeds the 2^30 bound the 32-bit signed "
        f"output relies on"
    )