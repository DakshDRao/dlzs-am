"""
cocotb verification of the Mitchell (1962) approximate multiplier.

The unsigned DUT is compared against golden_model.mitchell().
The signed DUT is compared against golden_model.signed_wrap(
    golden_model.mitchell, ...), matching the repository's established
sign-magnitude verification convention.

The directed vectors emphasize:
  * exact powers of two,
  * the no-carry/carry boundary,
  * zero,
  * binade boundaries,
  * -32768 on the signed path.
"""

import os
import sys

import cocotb
from cocotb.triggers import Timer

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from golden_model import mitchell, signed_wrap, to_signed
from sweep import sampled_pairs

W = 16
SETTLE_NS = 1
N_RANDOM = int(os.environ.get("MITCHELL_N_RANDOM", "") or 200_000)
MAX_REPORTED_FAILURES = 20


def read_signed(handle):
    value = handle.value
    fn = getattr(value, "to_signed", None)
    return fn() if callable(fn) else value.signed_integer


class Checker:
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
        if not self.failures:
            self.dut._log.info(
                "%s: %d pairs checked, all match the golden model",
                self.name, self.checked,
            )
            return

        hidden = max(0, len(self.failures) - MAX_REPORTED_FAILURES)
        a, b, got, exp = self.failures[0]
        msg = (
            f"{self.name}: {len(self.failures)} of {self.checked} pairs "
            f"mismatched"
        )
        if hidden:
            msg += f" ({hidden} not individually logged)"
        msg += f"; first failure a={a} b={b} got={got} expected={exp}"
        raise AssertionError(msg)


async def drive_unsigned(dut, name, pairs):
    checker = Checker(dut, name)
    for a, b in pairs:
        dut.u_a.value = a
        dut.u_b.value = b
        await Timer(SETTLE_NS, "ns")
        checker.compare(a, b, int(dut.u_mul.value), mitchell(a, b, W))
    checker.finish()


async def drive_signed(dut, name, pairs):
    checker = Checker(dut, name)
    for a, b in pairs:
        dut.s_a.value = a & 0xFFFF
        dut.s_b.value = b & 0xFFFF
        await Timer(SETTLE_NS, "ns")
        got = read_signed(dut.s_mul)
        expected = signed_wrap(mitchell, a, b, W)
        checker.compare(a, b, got, expected)
    checker.finish()


def corner_operands_unsigned():
    vals = {0, 1, 2, 3, 0xFFFF, 0xFFFE, 0x8000, 0x7FFF}

    # Powers of two and their immediate neighbors.
    for k in range(W):
        p = 1 << k
        vals.update({p - 1, p, p + 1})

    # Mitchell carry seam: ma + mb == 1 is attained by equal 1.5*2^k
    # operands, e.g. 24*24 at k=4.
    for k in range(1, W - 1):
        tie = 3 << (k - 1)
        vals.update({tie - 1, tie, tie + 1})

    return sorted(v for v in vals if 0 <= v < (1 << W))


def corner_operands_signed():
    vals = set()
    for u in corner_operands_unsigned():
        s = to_signed(u, W)
        vals.add(s)
        if -s <= (1 << (W - 1)) - 1:
            vals.add(-s)

    vals.update({
        0, 1, -1, 3, -3,
        (1 << (W - 1)) - 1,
        -(1 << (W - 1)),
    })

    lo, hi = -(1 << (W - 1)), (1 << (W - 1)) - 1
    return sorted(v for v in vals if lo <= v <= hi)


@cocotb.test()
async def test_unsigned_corners(dut):
    ops = corner_operands_unsigned()
    pairs = [(a, b) for a in ops for b in ops]
    dut._log.info(
        "Mitchell unsigned: %d directed pairs (%d x %d)",
        len(pairs), len(ops), len(ops),
    )
    await drive_unsigned(dut, "Mitchell unsigned corners", pairs)


@cocotb.test()
async def test_unsigned_sweep(dut):
    pairs, n_corner = sampled_pairs(W, N_RANDOM)
    dut._log.info(
        "Mitchell unsigned: %d pairs (%d corner + %d random)",
        len(pairs), n_corner, N_RANDOM,
    )
    await drive_unsigned(dut, "Mitchell unsigned sweep", pairs)


@cocotb.test()
async def test_signed_corners(dut):
    ops = corner_operands_signed()
    pairs = [(a, b) for a in ops for b in ops]
    dut._log.info(
        "Mitchell signed: %d directed pairs (%d x %d)",
        len(pairs), len(ops), len(ops),
    )
    await drive_signed(dut, "Mitchell signed corners", pairs)


@cocotb.test()
async def test_signed_sweep(dut):
    raw, n_corner = sampled_pairs(W, N_RANDOM)
    pairs = [(to_signed(a, W), to_signed(b, W)) for a, b in raw]
    dut._log.info(
        "Mitchell signed: %d pairs (%d corner + %d random)",
        len(pairs), n_corner, N_RANDOM,
    )
    await drive_signed(dut, "Mitchell signed sweep", pairs)


@cocotb.test()
async def test_signed_min_negative(dut):
    lo = -(1 << (W - 1))
    others = [
        lo, lo + 1, -21845, -256, -1, 0, 1, 256,
        21845, (1 << (W - 1)) - 1,
    ]
    pairs = [(lo, b) for b in others] + [(a, lo) for a in others]
    await drive_signed(dut, "Mitchell signed -32768 boundary", pairs)
