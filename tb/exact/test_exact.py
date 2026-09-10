"""
test_exact.py -- cocotb verification of the exact 16x16 signed baseline
(baselines/exact/exact.sv) and its pipelined synthesis harness
(synth/wrappers/exact_wrapper.sv) against src/golden_model.

This is the Week 6-7 reference row. It is deliberately the same shape as
test_drum.py, drives the same stimulus set, and judges results the same way, so
that "exact verified" means the same thing as "DRUM verified" and "DLZS
verified".

Why an exact multiplier needs a testbench at all
------------------------------------------------
It looks like the one design that cannot be wrong -- it is a single `*`. Two
reasons it still gets a bench, and the second is the one that bites:

1. It is the reference. Every MRED, NMED and bias in the comparison table is
   computed against this row. A fault here is the only fault in the repo that
   produces no contradicting symptom anywhere else: the approximate designs
   would all be scored against a wrong product and would all still "agree"
   with each other. Nothing else in the suite would go red.

2. `exact.sv` casts with $signed() but declares its ports UNSIGNED. That works
   -- 16x16 -> 32 is evaluated in the 32-bit assignment context and the cast
   forces sign extension -- but it works for a reason that is one edit away
   from being untrue. Dropping either $signed() turns every negative operand
   into a large positive one and the design still elaborates, still simulates,
   and is still wrong only in the two mixed-sign quadrants. That is the same
   failure shape as upstream DRUM6_16_s, and it is caught the same way: by a
   directed cross product over all four quadrants, not by a random sweep.

What is under test
------------------
DUT                    reference
exact                  a * b, and independently signed_wrap(exact_u, a, b, 16)
exact_wrapper          the same product, delayed by exactly 2 clocks

The two references for the core are checked to AGREE as well as to match the
RTL. signed_wrap composed with the unsigned exact model must reduce to plain
signed multiplication -- it is the degenerate case of the sign-magnitude
scheme, the same shape of property test as
test_drum_degenerates_to_exact_at_k_equals_w. If signed_wrap were subtly wrong
about -32768, every signed row in the comparison would inherit the error, so
the identity is asserted rather than assumed.

Overflow
--------
There is none, and that is checked rather than argued. The largest magnitude a
signed 16x16 product can reach is |-32768 * -32768| = 2^30, comfortably inside
a 32-bit signed range whose limit is 2^31 - 1. So the exact row never
saturates, never wraps, and needs no guard -- which is what makes it usable as
a reference without qualification.

Pipeline
--------
exact_wrapper registers both operands on one edge and the product on the next,
so its latency is exactly 2 clocks with full throughput -- one new result every
cycle, not one every two. The scoreboard checks the LATENCY as well as the
values: an off-by-one in the pipe would still produce correct-looking products
against shifted inputs, and a sweep that compares result i to input i-1 would
pass a design that had silently lost a stage.
"""

import os
import sys
from collections import deque

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

# src/ is put on PYTHONPATH by tb/common.mk, so the golden model and the sweep
# stimulus resolve without per-file sys.path surgery. Kept as a fallback so the
# file still imports when opened directly by an editor or pytest.
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from golden_model import exact as exact_u, signed_wrap, to_signed   # noqa: E402
from sweep import sampled_pairs                                    # noqa: E402


W = 16
SETTLE_NS = 1
CLK_PERIOD_NS = 10
LATENCY = 2                 # clocks from operands applied to registered product

# Loop-iterations of lag, which is NOT the same number as LATENCY, and the
# difference is worth a name rather than a magic -1 buried in a slice.
#
# The driving loop sets the operands and THEN awaits the edge, so the first
# input register captures on the very edge that iteration i waits for. A pair
# applied during iteration i is therefore visible at the output after the edge
# of iteration i+1 -- one iteration of lag, from two clocks of latency. Getting
# this wrong is self-concealing: a scoreboard one entry too deep reports every
# vector as broken by exactly one step, which reads like a design fault.
PIPE_DEPTH = LATENCY - 1

MAX_REPORTED_FAILURES = 20

N_RANDOM = int(os.environ.get("EXACT_N_RANDOM", "") or 200_000)

MASK16 = (1 << W) - 1
INT_MIN = -(1 << (W - 1))
INT_MAX = (1 << (W - 1)) - 1


# ---------------------------------------------------------------------------
# Reference
# ---------------------------------------------------------------------------

def reference(a, b):
    """The expected signed product, computed two independent ways.

    Plain `a * b` is the obvious one. signed_wrap(exact_u, ...) is the same
    number arrived at through the sign-magnitude machinery every other signed
    row in the comparison goes through. They must agree for all inputs; if they
    ever do not, the fault is in signed_wrap and it is contaminating DRUM and
    DLZS too, so it is worth one assert per vector to find out here.
    """
    direct = a * b
    viawrap = signed_wrap(exact_u, a, b, W)
    assert direct == viawrap, (
        f"golden model self-inconsistency at a={a} b={b}: "
        f"a*b={direct} but signed_wrap(exact)={viawrap} -- "
        "the fault is in signed_wrap, not in the RTL"
    )
    return direct


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------

class Checker:
    """Accumulates mismatches so one run reports every failing class of input
    rather than aborting on the first vector. Also tallies by sign quadrant --
    a sign-extension fault shows as a clean quadrant pattern (both mixed
    quadrants fully broken, both same-sign quadrants clean) and a datapath
    fault does not. That distinction is what a raw pass/fail count throws away.
    """

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
                self.name, a, a & MASK16, b, b & MASK16, got, expected,
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


def read_signed(handle, context=""):
    """cocotb 2.x renamed LogicArray.signed_integer to .to_signed(). Probe both
    so the bench runs unchanged on either release.

    X/Z is trapped here rather than left to raise out of the conversion, so an
    undriven output reports as a design fault with a pointer at the likely
    cause instead of as a library traceback. For this bench that is the
    expected first symptom of a miswired pipeline register, so it is worth the
    dedicated message.
    """
    value = handle.value
    text = str(value).lower()
    if "x" in text or "z" in text:
        raise AssertionError(
            f"{context}output is not resolvable ({value}). An all-X product "
            "usually means the output register is never assigned, or the "
            "instance output and the register are fighting for the same net."
        )
    fn = getattr(value, "to_signed", None)
    return fn() if callable(fn) else value.signed_integer


def corner_operands_signed():
    """Binade edges and their negations, plus the values a sign bug singles
    out. -32768 is the vector of record: its magnitude does not fit the signed
    range, so it is the operand most likely to be broken by an abs() done in
    the wrong width or by a missing sign extension.
    """
    vals = {0, 1, 2, 3, -1, -2, -3, INT_MAX, INT_MIN, INT_MIN + 1}
    for k in range(W - 1):
        p = 1 << k
        for v in (p - 1, p, p + 1):
            if INT_MIN <= v <= INT_MAX:
                vals.add(v)
            if INT_MIN <= -v <= INT_MAX:
                vals.add(-v)
    # Patterns whose halves differ, so a 16-bit slice taken from the wrong end
    # of a 32-bit expression does not accidentally look right.
    vals.update({0x5555 - 0x10000, 0x5555, -21845, 21845, 255, -255, 256, -256})
    return sorted(v for v in vals if INT_MIN <= v <= INT_MAX)


def signed_sweep_pairs():
    """The published sweep stimulus reinterpreted as two's complement.

    Imported from sweep.sampled_pairs() verbatim, exactly as test_drum.py and
    test_mult.py do, so the exact reference row is exercised over the same
    input set as the designs it is the reference FOR.
    """
    raw, n_corner = sampled_pairs(W, N_RANDOM)
    return [(to_signed(a, W), to_signed(b, W)) for a, b in raw], n_corner


# ---------------------------------------------------------------------------
# Combinational core -- baselines/exact/exact.sv
# ---------------------------------------------------------------------------

async def drive_core(dut, name, pairs):
    checker = Checker(dut, name)
    for a, b in pairs:
        dut.c_a.value = a & MASK16
        dut.c_b.value = b & MASK16
        await Timer(SETTLE_NS, "ns")
        got = read_signed(dut.c_p, f"{name}: ")
        checker.compare(a, b, got, reference(a, b))
    checker.finish()


@cocotb.test()
async def test_core_corners(dut):
    """Directed cross product over all four sign quadrants.

    This is the test that fails loudly if either $signed() cast is dropped from
    exact.sv, or if the ports are ever narrowed. It is directed rather than
    random because the failure is quadrant-shaped: a sample drawn mostly from
    (+,+) would pass an unsigned multiplier.
    """
    ops = corner_operands_signed()
    pairs = [(a, b) for a in ops for b in ops]
    dut._log.info("exact core: %d directed corner pairs (%d x %d)",
                  len(pairs), len(ops), len(ops))
    await drive_core(dut, "exact core corners", pairs)


@cocotb.test()
async def test_core_sweep(dut):
    """The same stimulus test_mult.py and test_drum.py drive, so the reference
    row and the rows it scores are characterized over identical inputs."""
    pairs, n_corner = signed_sweep_pairs()
    dut._log.info("exact core: %d sweep pairs signed (%d corner + %d random)",
                  len(pairs), n_corner, N_RANDOM)
    await drive_core(dut, "exact core sweep", pairs)


@cocotb.test()
async def test_core_min_negative(dut):
    """-32768 against everything.

    The magnitude 32768 is out of range for a signed 16-bit value, which is
    what breaks the sign-magnitude designs when an intermediate is wrongly
    declared `signed`. exact.sv has no magnitude path at all, so it should be
    immune -- and that immunity is the reason it is the reference. Asserted,
    not assumed.
    """
    others = [INT_MIN, INT_MIN + 1, -21845, -256, -1, 0, 1, 256, 21845, INT_MAX]
    pairs = [(INT_MIN, b) for b in others] + [(a, INT_MIN) for a in others]
    await drive_core(dut, "exact core min-negative", pairs)


@cocotb.test()
async def test_core_no_overflow(dut):
    """The product never leaves the 32-bit signed range, so the reference needs
    no saturation guard.

    The bound is 2^30 at (-32768, -32768), a factor of two inside the 2^31 - 1
    limit. This is checked on the extreme corners specifically -- if a future
    revision widens the operands to 17 bits for a signed-magnitude experiment,
    the bound stops holding and this test is where that shows up.
    """
    extremes = [INT_MIN, INT_MIN + 1, INT_MAX, INT_MAX - 1, 0, 1, -1]
    checker = Checker(dut, "exact core overflow bound")
    limit = 1 << 30
    for a in extremes:
        for b in extremes:
            dut.c_a.value = a & MASK16
            dut.c_b.value = b & MASK16
            await Timer(SETTLE_NS, "ns")
            got = read_signed(dut.c_p, "exact core overflow bound: ")
            checker.compare(a, b, got, reference(a, b))
            assert abs(got) <= limit, (
                f"product magnitude {abs(got)} at a={a} b={b} exceeds the 2^30 "
                "bound the reference row is documented to respect"
            )
    checker.finish()
    dut._log.info("exact core: |product| <= 2^30 on all extreme corners")


# ---------------------------------------------------------------------------
# Pipelined wrapper -- synth/wrappers/exact_wrapper.sv
# ---------------------------------------------------------------------------

async def start_clock(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, "ns").start())


async def flush(dut, cycles=LATENCY + 1):
    """Push zeros through until the pipe holds known values.

    The registers power up to X in Icarus, so without this the first comparison
    reports an unresolvable output and the real question -- whether the
    arithmetic is right -- never gets asked. Zero is used because 0 * 0 == 0 is
    true at every stage, so a flushed pipe reads 0 regardless of depth.
    """
    dut.w_a.value = 0
    dut.w_b.value = 0
    for _ in range(cycles):
        await RisingEdge(dut.clk)
    await Timer(SETTLE_NS, "ns")


async def drive_wrapper(dut, name, pairs):
    """Stream pairs at one per clock and score against a LATENCY-deep model of
    the pipe.

    Full throughput is part of the contract, not an optimization: the harness
    exists so that every design in the comparison carries the same 64 flip
    flops, and a wrapper that only accepted a new operand pair every other
    cycle would not be the same harness the other rows are measured in.
    """
    checker = Checker(dut, name)
    pipe = deque()
    await flush(dut)

    for a, b in pairs:
        dut.w_a.value = a & MASK16
        dut.w_b.value = b & MASK16
        await RisingEdge(dut.clk)
        await Timer(SETTLE_NS, "ns")
        pipe.append((a, b))
        if len(pipe) > PIPE_DEPTH:
            ea, eb = pipe.popleft()
            got = read_signed(dut.w_p, f"{name}: ")
            checker.compare(ea, eb, got, reference(ea, eb))

    # Drain: the last PIPE_DEPTH pairs are still in flight when the stimulus
    # ends.
    # Dropping them would leave the final vectors of every run unchecked, which
    # is exactly where a corner case tends to have been placed on purpose.
    while pipe:
        await RisingEdge(dut.clk)
        await Timer(SETTLE_NS, "ns")
        ea, eb = pipe.popleft()
        got = read_signed(dut.w_p, f"{name}: ")
        checker.compare(ea, eb, got, reference(ea, eb))

    checker.finish()


@cocotb.test()
async def test_wrapper_latency(dut):
    """The registered product appears exactly LATENCY clocks after its
    operands -- not one, not three.

    Directed and separate from the value tests on purpose. A pipe that is a
    stage short still produces arithmetically correct products; it just pairs
    them with the wrong inputs. A scoreboard written to the wrong depth would
    then agree with it and report a full pass. So the depth is pinned first,
    with a single impulse against a zeroed background, and only then is it used
    as an assumption by the sweeps below.
    """
    await start_clock(dut)
    await flush(dut)

    a, b = -12345, 6789
    expected = reference(a, b)

    dut.w_a.value = a & MASK16
    dut.w_b.value = b & MASK16
    await RisingEdge(dut.clk)          # edge 1: operands captured
    dut.w_a.value = 0                  # impulse only; background returns to 0
    dut.w_b.value = 0
    await Timer(SETTLE_NS, "ns")
    early = read_signed(dut.w_p, "wrapper latency: ")
    assert early == 0, (
        f"product {early} appeared 1 clock after the operands; the harness is "
        f"{LATENCY} stages and every design in the comparison must match it"
    )

    await RisingEdge(dut.clk)          # edge 2: product registered
    await Timer(SETTLE_NS, "ns")
    got = read_signed(dut.w_p, "wrapper latency: ")
    assert got == expected, (
        f"at {LATENCY} clocks: got {got}, expected {expected} for a={a} b={b}"
    )

    await RisingEdge(dut.clk)          # edge 3: impulse has passed through
    await Timer(SETTLE_NS, "ns")
    late = read_signed(dut.w_p, "wrapper latency: ")
    assert late == 0, (
        f"product {late} still present 3 clocks after a single-cycle impulse; "
        "the pipe is deeper than the harness contract"
    )

    dut._log.info("exact_wrapper: latency confirmed at exactly %d clocks", LATENCY)


@cocotb.test()
async def test_wrapper_corners(dut):
    """Directed quadrant cross product through the registered path.

    The core already passes this combinationally, so a failure here isolates to
    the wrapper: a lost sign extension across the 16-bit input registers, or an
    output register that is narrower than the product.
    """
    await start_clock(dut)
    ops = corner_operands_signed()
    pairs = [(a, b) for a in ops for b in ops]
    dut._log.info("exact_wrapper: %d directed corner pairs", len(pairs))
    await drive_wrapper(dut, "exact_wrapper corners", pairs)


@cocotb.test()
async def test_wrapper_sweep(dut):
    """Back-to-back streaming of the published sweep set, one pair per clock.

    This is the throughput check as much as the value check: LATENCY-deep
    scoreboarding only stays aligned if the wrapper really does accept a new
    pair on every edge.
    """
    await start_clock(dut)
    pairs, n_corner = signed_sweep_pairs()
    dut._log.info("exact_wrapper: %d sweep pairs signed (%d corner + %d random)",
                  len(pairs), n_corner, N_RANDOM)
    await drive_wrapper(dut, "exact_wrapper sweep", pairs)


@cocotb.test()
async def test_wrapper_matches_core(dut):
    """Wrapper and core, same vectors, compared to each other rather than to
    the model.

    Both are checked against the golden model above, so this is redundant on a
    passing run -- and useful on a failing one. If the model and BOTH DUTs
    disagree, the fault is in the reference; if the two DUTs disagree with each
    other, it is in the pipe. That is a question worth being able to answer
    without a second debug session.
    """
    await start_clock(dut)
    ops = corner_operands_signed()[::3]
    pairs = [(a, b) for a in ops for b in ops]
    pipe = deque()
    await flush(dut)
    mismatches = 0

    for a, b in pairs:
        dut.w_a.value = a & MASK16
        dut.w_b.value = b & MASK16
        dut.c_a.value = a & MASK16
        dut.c_b.value = b & MASK16
        await RisingEdge(dut.clk)
        await Timer(SETTLE_NS, "ns")
        pipe.append((a, b, read_signed(dut.c_p, "core (cross-check): ")))
        if len(pipe) > PIPE_DEPTH:
            ea, eb, core_p = pipe.popleft()
            wrap_p = read_signed(dut.w_p, "wrapper (cross-check): ")
            if wrap_p != core_p:
                mismatches += 1
                if mismatches <= MAX_REPORTED_FAILURES:
                    dut._log.error(
                        "core/wrapper divergence at a=%d b=%d: core %d, wrapper %d",
                        ea, eb, core_p, wrap_p)

    assert mismatches == 0, (
        f"{mismatches} of {len(pairs) - PIPE_DEPTH} vectors differ between the "
        "combinational core and the registered wrapper"
    )
    dut._log.info("exact_wrapper agrees with exact core on %d vectors",
                  len(pairs) - PIPE_DEPTH)
