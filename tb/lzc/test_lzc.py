"""
test_lzc.py -- cocotb verification of lzc_8 / lzc_16 against the golden model.

The DUTs are pure combinational leading-one detectors. There is no clock and no
reset; stimulus is applied, a delta-settling delay is inserted, and outputs are
compared against src/golden_model.lead_one.

What "golden" means here
------------------------
`output_power` is NOT a leading-ZERO count despite the module name. It is the
index of the most significant set bit, i.e. floor(log2 x), which is exactly
what golden_model.lead_one() returns and exactly what the DLZS datapath
consumes as its shift amount. The hardware LZC relationship is
    output_power == (w - 1) - LZC(x)
so if a future revision changes the RTL to emit a true zero-count, this
testbench will correctly start failing rather than silently accepting a
datapath that shifts by the wrong amount.

lead_one() raises on zero by design, so the zero input is handled as its own
case rather than by extending the model.

Coverage
--------
w=8 : exhaustive. All 256 operands.

w=16: the SAME operand values used by the 16-bit error sweep, imported
      directly from src/sweep.sampled_pairs() rather than reconstructed here.
      Reconstruction would silently drift the moment the seed, the corner set
      or the draw order changes in sweep.py, and a testbench that claims to
      match the characterization set must actually match it.

      The sweep produces ORDERED PAIRS for a two-operand multiplier. The LZC is
      a one-operand block, so the pairs are flattened and deduplicated. At the
      default sample size this reduces to all 65,536 values -- 2e6 draws over a
      65,536-value space leaves nothing uncovered -- so the 16-bit run is also
      exhaustive in practice. That is reported at runtime rather than assumed,
      because it stops being true if LZC16_N_RANDOM is set low.

Zero convention
---------------
`output_power` is architecturally DON'T-CARE when all_zero is asserted; the
consumer must gate on all_zero. The current RTL happens to drive 0 there, and
CHECK_ZERO_POWER pins that behaviour so an accidental change is visible. Set it
False if a future revision deliberately leaves the field undriven or uses it to
carry something else -- that is a spec decision, not a bug, and this flag is
where it gets recorded.
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

from golden_model import lead_one          # noqa: E402
from sweep import sampled_pairs            # noqa: E402


# Settling delay for the combinational DUT. Any non-zero delay works; 1 ns is
# used so waveform dumps stay readable at one input vector per nanosecond.
SETTLE_NS = 1

# Pin the RTL's zero-case output_power. See "Zero convention" above.
CHECK_ZERO_POWER = True

# Matches sweep.py's own default so the 16-bit stimulus is identical to the set
# used for the published error tables. Override only to shorten a smoke run.
# `or` rather than a get() default: an exported-but-empty make variable arrives
# as "", which is present in os.environ and would defeat the default.
N_RANDOM = int(os.environ.get("LZC16_N_RANDOM", "") or 1_000_000)

# Stop after this many distinct failures so a systematically broken DUT reports
# a readable summary instead of 65,536 log lines.
MAX_REPORTED_FAILURES = 20


def golden(value, width):
    """Reference (output_power, all_zero) for an operand.

    Returns output_power as None when the value is zero, marking the field as
    don't-care so the comparison logic decides what to enforce rather than
    inventing an expected value here.
    """
    assert 0 <= value < (1 << width)
    if value == 0:
        return None, 1
    return lead_one(value, width), 0


class Checker:
    """Accumulates mismatches so one run reports every failing class of input
    rather than aborting on the first vector."""

    def __init__(self, dut, name):
        self.dut = dut
        self.name = name
        self.checked = 0
        self.failures = []

    def compare(self, operand, got_power, got_zero, exp_power, exp_zero):
        self.checked += 1
        bad = []

        if got_zero != exp_zero:
            bad.append(f"all_zero: got {got_zero}, expected {exp_zero}")

        if exp_power is None:
            # Zero input: output_power is don't-care unless pinned.
            if CHECK_ZERO_POWER and got_power != 0:
                bad.append(f"output_power on zero input: got {got_power}, "
                           f"expected 0 by current RTL convention")
        elif got_power != exp_power:
            bad.append(f"output_power: got {got_power}, expected {exp_power}")

        if bad:
            self.failures.append((operand, bad))
            if len(self.failures) <= MAX_REPORTED_FAILURES:
                self.dut._log.error(
                    "%s mismatch on operand %d (0x%X, %s): %s",
                    self.name, operand, operand,
                    format(operand, "b").zfill(operand.bit_length() or 1),
                    "; ".join(bad),
                )

    def finish(self):
        n_fail = len(self.failures)
        if n_fail:
            hidden = max(0, n_fail - MAX_REPORTED_FAILURES)
            summary = (f"{self.name}: {n_fail} of {self.checked} operands "
                       f"mismatched")
            if hidden:
                summary += f" ({hidden} not individually logged)"
            summary += f"; first failing operand = {self.failures[0][0]}"
            raise AssertionError(summary)
        self.dut._log.info("%s: %d operands checked, all match the golden "
                           "model", self.name, self.checked)


async def drive_and_check(dut, name, operands, width, in_sig, pow_sig, zero_sig):
    """Apply each operand, settle, compare. Shared by both widths so the two
    tests cannot drift apart in how they judge a result."""
    checker = Checker(dut, name)

    for value in operands:
        in_sig.value = value
        # Positional unit argument: cocotb 1.x names it `units`, 2.x `unit`.
        await Timer(SETTLE_NS, "ns")

        exp_power, exp_zero = golden(value, width)
        checker.compare(
            value,
            int(pow_sig.value),
            int(zero_sig.value),
            exp_power,
            exp_zero,
        )

    checker.finish()


@cocotb.test()
async def test_lzc_8_exhaustive(dut):
    """All 256 operands. Nothing about an 8-bit block justifies sampling."""
    dut.operand_16.value = 0        # hold the other DUT quiet
    operands = range(1 << 8)

    dut._log.info("lzc_8: exhaustive sweep, %d operands", 1 << 8)
    await drive_and_check(
        dut, "lzc_8", operands, 8,
        dut.operand_8, dut.power_8, dut.all_zero_8,
    )


@cocotb.test()
async def test_lzc_16_sweep_operands(dut):
    """The 16-bit sweep's operand set, imported from sweep.py verbatim."""
    dut.operand_8.value = 0

    pairs, n_corner = sampled_pairs(16, N_RANDOM)
    operands = sorted({v for pair in pairs for v in pair})

    total = 1 << 16
    dut._log.info(
        "lzc_16: %d distinct operands from the sweep set "
        "(%d corner pairs + %d random pairs, seed per sweep.py) "
        "-- %.2f%% of the %d-value space",
        len(operands), n_corner, N_RANDOM,
        100.0 * len(operands) / total, total,
    )
    if len(operands) == total:
        dut._log.info("lzc_16: sweep set covers the full operand space; "
                      "this run is exhaustive")
    else:
        missing = total - len(operands)
        dut._log.warning("lzc_16: %d operands NOT covered by this sample "
                         "(LZC16_N_RANDOM reduced?)", missing)

    await drive_and_check(
        dut, "lzc_16", operands, 16,
        dut.operand_16, dut.power_16, dut.all_zero_16,
    )


@cocotb.test()
async def test_lzc_16_binade_boundaries(dut):
    """Directed test on the 8/7 seam and every binade edge.

    The sweep set already contains these, but they are re-run standalone
    because they are the vectors that catch the specific merge bug this design
    is prone to: an inverted select on the upper-half all_zero flag swaps the
    halves and puts every result off by 8. 0x0080 -> 7 and 0x0100 -> 8 fail
    immediately under that bug while random stimulus buries it in a pass rate.
    """
    dut.operand_8.value = 0

    operands = []
    for k in range(16):
        p = 1 << k
        operands.extend([p, p - 1, p + 1])
    operands = sorted(v for v in set(operands) if 0 <= v < (1 << 16))

    dut._log.info("lzc_16: %d directed binade-boundary operands", len(operands))
    await drive_and_check(
        dut, "lzc_16", operands, 16,
        dut.operand_16, dut.power_16, dut.all_zero_16,
    )