"""
test_drum.py -- cocotb verification of the vendored DRUM baseline against
src/golden_model.drum().

This is the Week 6-7 gate item "DRUM open-source Verilog checked against my own
drum() model before it is trusted". It is deliberately the same shape as
test_mult.py, drives the same stimulus set, and judges results the same way, so
that "DRUM verified" and "DLZS verified" mean the same thing.

What is under test
------------------
DUT                          reference
drum_signed_top #(.K(6))     signed_wrap(drum(.,.,6,.), a, b, 16)
drum_signed_top #(.K(4))     signed_wrap(drum(.,.,4,.), a, b, 16)
DRUM6_16_u  (bare core)      drum(a, b, 6, 16)   -- unsigned, raw patterns
DRUM4_16_u  (bare core)      drum(a, b, 4, 16)   -- unsigned, raw patterns

The bare cores are checked SEPARATELY from the wrappers on purpose. If only the
signed path were tested, a core fault and a wrapper fault would be
indistinguishable -- which is precisely the failure mode that made upstream's
DRUM6_16_s look plausible: its core is correct and only its sign logic is not.

Stimulus
--------
Imported from src/sweep.sampled_pairs() verbatim, exactly as test_mult.py does,
so DRUM and DLZS are characterized over the same input set and the comparison
table's rows are commensurable. Plus a directed signed-corner cross product,
because the random draw does not guarantee all four sign quadrants are
populated at low sample sizes -- and the sign quadrant is where upstream's
wrappers fail.

Zero handling
-------------
DRUM needs no explicit zero guard, unlike dlzc_mult. Its LOD emits all-zeros on
a zero operand, P_Encoder takes its default arm returning 0, and mm/nn fall
through to a[k-1:0] == 0, so tmp == 0. That is checked here rather than
asserted in prose: zero appears in both corner sets on both operands.
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

from golden_model import drum, signed_wrap, to_signed   # noqa: E402
from sweep import sampled_pairs                         # noqa: E402


W = 16
SETTLE_NS = 1
MAX_REPORTED_FAILURES = 20

N_RANDOM = int(os.environ.get("DRUM_N_RANDOM", "") or 200_000)


def drum_k(k):
    """Bind k so the design has the (a, b, w) signature signed_wrap expects."""
    return lambda a, b, w: drum(a, b, k, w)


class Checker:
    """Accumulates mismatches so one run reports every failing class of input
    rather than aborting on the first vector. Also tallies by sign quadrant --
    a wrapper fault shows as a clean quadrant pattern, a core fault does not,
    and that distinction is what separates upstream's two bugs."""

    def __init__(self, dut, name):
        self.dut = dut
        self.name = name
        self.checked = 0
        self.failures = []
        self.quad = {q: [0, 0] for q in ("++", "+-", "-+", "--")}

    def compare(self, a, b, got, expected):
        self.checked += 1
        q = ("+" if a >= 0 else "-") + ("+" if b >= 0 else "-")
        self.quad[q][0] += 1
        if got == expected:
            return
        self.quad[q][1] += 1
        self.failures.append((a, b, got, expected))
        if len(self.failures) <= MAX_REPORTED_FAILURES:
            self.dut._log.error(
                "%s mismatch: a=%d (0x%04X) b=%d (0x%04X) -> got %d, expected %d",
                self.name, a, a & 0xFFFF, b, b & 0xFFFF, got, expected,
            )

    def finish(self):
        n_fail = len(self.failures)
        if n_fail:
            breakdown = ", ".join(
                f"{q} {bad}/{tot}" for q, (tot, bad) in self.quad.items() if tot
            )
            hidden = max(0, n_fail - MAX_REPORTED_FAILURES)
            a, b, got, exp = self.failures[0]
            summary = f"{self.name}: {n_fail} of {self.checked} pairs mismatched"
            if hidden:
                summary += f" ({hidden} not individually logged)"
            summary += f"; by quadrant: {breakdown}"
            summary += f"; first failure a={a} b={b} got={got} expected={exp}"
            raise AssertionError(summary)
        self.dut._log.info("%s: %d pairs checked, all match the golden model",
                           self.name, self.checked)


def read_signed(handle):
    """cocotb 2.x renamed LogicArray.signed_integer to .to_signed(). Probe both
    so the bench runs unchanged on either release."""
    value = handle.value
    fn = getattr(value, "to_signed", None)
    return fn() if callable(fn) else value.signed_integer


async def drive_signed(dut, name, pairs, a_sig, b_sig, r_sig, design):
    checker = Checker(dut, name)
    for a, b in pairs:
        a_sig.value = a & 0xFFFF
        b_sig.value = b & 0xFFFF
        await Timer(SETTLE_NS, "ns")
        checker.compare(a, b, read_signed(r_sig), signed_wrap(design, a, b, W))
    checker.finish()


async def drive_unsigned(dut, name, pairs, a_sig, b_sig, r_sig, design):
    checker = Checker(dut, name)
    for a, b in pairs:
        a_sig.value = a
        b_sig.value = b
        await Timer(SETTLE_NS, "ns")
        checker.compare(a, b, int(r_sig.value), design(a, b, W))
    checker.finish()


def corner_operands_unsigned():
    vals = {0, 1, 2, 3, 0xFFFF, 0xFFFE, 0x8000, 0x7FFF}
    for k in range(W):
        p = 1 << k
        vals.update({p, p - 1, p + 1})
        # DRUM's truncation boundary: k1 > K-1 selects the shifted path.
        # +-1 around each binade edge straddles it in both directions.
    return sorted(v for v in vals if 0 <= v < (1 << W))


def corner_operands_signed():
    """Unsigned corners reinterpreted plus their negations. -32768 is the
    vector of record: its magnitude does not fit an unsigned 16-bit range, and
    it is the operand most likely to be broken by a `signed` on an internal
    net -- in DRUM's case, on a_temp."""
    vals = set()
    for u in corner_operands_unsigned():
        s = to_signed(u, W)
        vals.add(s)
        if -s <= (1 << (W - 1)) - 1:
            vals.add(-s)
    vals.update({0, 1, -1, -3, 3, (1 << (W - 1)) - 1, -(1 << (W - 1))})
    lo, hi = -(1 << (W - 1)), (1 << (W - 1)) - 1
    return sorted(v for v in vals if lo <= v <= hi)


# ---------------------------------------------------------------------------
# Unsigned cores -- vendored verbatim, checked in isolation
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_core_k6_sweep(dut):
    """DRUM6_16_u against drum(k=6). Core only, no sign logic in the path."""
    pairs, n_corner = sampled_pairs(W, N_RANDOM)
    dut._log.info("DRUM6_16_u: %d pairs (%d corner + %d random)",
                  len(pairs), n_corner, N_RANDOM)
    await drive_unsigned(dut, "DRUM6_16_u", pairs,
                         dut.u_a, dut.u_b, dut.u_r6, drum_k(6))


@cocotb.test()
async def test_core_k4_sweep(dut):
    """DRUM4_16_u against drum(k=4). Note this file carries a one-line fix to
    an upstream instantiation typo; without it the module does not elaborate.
    See baselines/drum/README.md §1a."""
    pairs, n_corner = sampled_pairs(W, N_RANDOM)
    dut._log.info("DRUM4_16_u: %d pairs (%d corner + %d random)",
                  len(pairs), n_corner, N_RANDOM)
    await drive_unsigned(dut, "DRUM4_16_u", pairs,
                         dut.u_a, dut.u_b, dut.u_r4, drum_k(4))


# ---------------------------------------------------------------------------
# Signed wrappers -- ours, structurally matched to dlzc_mult_top
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_signed_k6_corners(dut):
    """Directed cross product over all four sign quadrants.

    This is the test that fails loudly on upstream DRUM6_16_s (AND instead of
    XOR on the sign) and on DRUMk_M_N_s (one's complement instead of two's).
    It is directed rather than random because the failure is quadrant-shaped:
    a sample drawn mostly from (+,+) would pass a broken wrapper.
    """
    ops = corner_operands_signed()
    pairs = [(a, b) for a in ops for b in ops]
    dut._log.info("drum_signed_top K=6: %d directed corner pairs (%d x %d)",
                  len(pairs), len(ops), len(ops))
    await drive_signed(dut, "drum_signed_top K=6 corners", pairs,
                       dut.s_a, dut.s_b, dut.s_r6, drum_k(6))


@cocotb.test()
async def test_signed_k6_sweep(dut):
    """The sweep set reinterpreted as two's complement -- the same stimulus
    test_mult.py drives at the DLZS core, so the two designs are characterized
    over identical inputs."""
    raw, n_corner = sampled_pairs(W, N_RANDOM)
    pairs = [(to_signed(a, W), to_signed(b, W)) for a, b in raw]
    dut._log.info("drum_signed_top K=6: %d sweep pairs signed (%d corner + %d random)",
                  len(pairs), n_corner, N_RANDOM)
    await drive_signed(dut, "drum_signed_top K=6 sweep", pairs,
                       dut.s_a, dut.s_b, dut.s_r6, drum_k(6))


@cocotb.test()
async def test_signed_k4_corners(dut):
    ops = corner_operands_signed()
    pairs = [(a, b) for a in ops for b in ops]
    dut._log.info("drum_signed_top K=4: %d directed corner pairs", len(pairs))
    await drive_signed(dut, "drum_signed_top K=4 corners", pairs,
                       dut.s_a, dut.s_b, dut.s_r4, drum_k(4))


@cocotb.test()
async def test_signed_k4_sweep(dut):
    raw, n_corner = sampled_pairs(W, N_RANDOM)
    pairs = [(to_signed(a, W), to_signed(b, W)) for a, b in raw]
    dut._log.info("drum_signed_top K=4: %d sweep pairs signed", len(pairs))
    await drive_signed(dut, "drum_signed_top K=4 sweep", pairs,
                       dut.s_a, dut.s_b, dut.s_r4, drum_k(4))


@cocotb.test()
async def test_min_negative(dut):
    """-32768 against everything, both K.

    abs(-32768) == 32768 == 16'h8000 read as unsigned, which is in range for
    the core's unsigned port but not for a signed 16-bit value. golden_model's
    signed_wrap invokes the core at w+1 for exactly this reason. The RTL relies
    on abs_value1/2 being declared UNSIGNED; a well-meaning `signed` on those
    nets breaks precisely this vector and nothing else.
    """
    lo = -(1 << (W - 1))
    others = [lo, lo + 1, -21845, -256, -1, 0, 1, 256, 21845, (1 << (W - 1)) - 1]
    pairs = [(lo, b) for b in others] + [(a, lo) for a in others]
    await drive_signed(dut, "drum_signed_top K=6 min-negative", pairs,
                       dut.s_a, dut.s_b, dut.s_r6, drum_k(6))
    await drive_signed(dut, "drum_signed_top K=4 min-negative", pairs,
                       dut.s_a, dut.s_b, dut.s_r4, drum_k(4))
