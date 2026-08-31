"""
test_golden_model.py — Regression suite for the golden model.

Run with `python -m pytest tests/` or directly as `python tests/test_golden_model.py`.

Two kinds of test appear here and both matter:

  * Hand-computed vectors, which pin down specific boundary behaviour
    (tie-breaks, carry seams, exact-power cases).
  * PROPERTY tests over the full 8-bit space, which are far stronger. A
    degenerate parameter setting that must reduce an approximate design to
    exact multiplication -- DRUM at k == w -- is the single best test
    available, because it validates the whole datapath rather than a few
    points. Look for the equivalent in every future design: the Week 12
    compensation LUT must reduce to uncompensated DLZS when the LUT is all
    zeros, and that test should exist from the first commit.

Every expected value below was derived by hand and independently confirmed.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.golden_model import (  # noqa: E402
    lead_one,
    exact,
    dlzs_floor,
    dlzs_ceil,
    dlzs_nearest_linear,
    dlzs_nearest_log,
    mitchell,
    drum,
)

W = 8


# ---------------------------------------------------------------------------
# lead_one
# ---------------------------------------------------------------------------

def test_lead_one():
    assert lead_one(1, W) == 0
    assert lead_one(2, W) == 1
    assert lead_one(255, W) == 7

    try:
        lead_one(0, W)
    except ValueError:
        pass
    else:
        raise AssertionError("lead_one(0) must raise")

    try:
        lead_one(256, W)
    except AssertionError:
        pass
    else:
        raise AssertionError("lead_one must range-check against w")


# ---------------------------------------------------------------------------
# DLZS -- hand vectors
# ---------------------------------------------------------------------------

def test_dlzs_floor_ceil():
    assert dlzs_floor(8, 5, W) == 40      # exact power, exact result
    assert dlzs_ceil(8, 5, W) == 40       # exact power, must NOT round up
    assert dlzs_floor(7, 5, W) == 20      # 7 -> 4,  5 << 2
    assert dlzs_ceil(7, 5, W) == 40       # 7 -> 8,  5 << 3


def test_dlzs_nearest_linear():
    assert dlzs_nearest_linear(1, 5, W) == 5      # k=0, no mantissa bit
    assert dlzs_nearest_linear(22, 5, W) == 80    # 22 -> 16 (below midpoint 24)
    assert dlzs_nearest_linear(26, 5, W) == 160   # 26 -> 32 (above midpoint)
    assert dlzs_nearest_linear(24, 5, W) == 160   # TIE -> up (spec'd)
    assert dlzs_nearest_linear(16, 5, W) == 80    # exact power


def test_dlzs_nearest_linear_tie_values():
    """All midpoints 1.5 * 2^k at w=8 must round up. These are precisely the
    values where an RTL tie-break disagreement would show, so they belong in
    the Week 3-5 corner-case list."""
    for k in range(1, W):
        a = (1 << k) + (1 << (k - 1))     # 3, 6, 12, 24, 48, 96, 192
        assert dlzs_nearest_linear(a, 1, W) == 1 << (k + 1)


def test_dlzs_nearest_log():
    assert dlzs_nearest_log(22, 1, W) == 16   # 22^2 = 484  <  512
    assert dlzs_nearest_log(23, 1, W) == 32   # 23^2 = 529  >= 512
    assert dlzs_nearest_log(1, 1, W) == 1     # k=0: 1 >= 2 is false


def test_nearest_modes_diverge():
    """The two nearest modes MUST differ, or one of them is implemented wrong.
    Linear rounds up above 1.5*2^k, log above sqrt(2)*2^k ~= 1.414*2^k, so
    values in between disagree -- e.g. 23 at k=4."""
    assert dlzs_nearest_linear(23, 1, W) == 16
    assert dlzs_nearest_log(23, 1, W) == 32


def test_dlzs_zero():
    for f in (dlzs_floor, dlzs_ceil, dlzs_nearest_linear, dlzs_nearest_log):
        assert f(0, 5, W) == 0
        assert f(5, 0, W) == 0
        assert f(0, 0, W) == 0


# ---------------------------------------------------------------------------
# Mitchell
# ---------------------------------------------------------------------------

def test_mitchell_vectors():
    assert mitchell(16, 16, W) == 256    # both exact powers -> exact
    assert mitchell(22, 22, W) == 448    # no carry  (exact 484)
    assert mitchell(31, 31, W) == 960    # carry     (exact 961)
    assert mitchell(24, 23, W) == 496    # ma+mb = 0.9375, no carry
    assert mitchell(24, 24, W) == 512    # ma+mb = 1.0 exactly, carry
    assert mitchell(0, 5, W) == 0
    assert mitchell(5, 0, W) == 0


def test_mitchell_carry_continuity():
    """The two branches must agree in the limit ma+mb -> 1. mitchell(24,23)
    approaches and mitchell(24,24) attains 2^(ka+kb+1) = 512."""
    assert mitchell(24, 24, W) == 1 << (4 + 4 + 1)


def test_mitchell_never_overestimates():
    """PROPERTY: log2(1+m) >= m on both operands, so Mitchell is strictly
    one-sided low. A failure here means the carry algebra is broken."""
    for a in range(1, 1 << W):
        for b in range(1, 1 << W):
            assert mitchell(a, b, W) <= a * b


# ---------------------------------------------------------------------------
# DRUM
# ---------------------------------------------------------------------------

def test_drum_vectors():
    assert drum(4, 4, 4, W) == 16        # fits in 4 bits -> exact
    assert drum(16, 16, 4, W) == 324     # s=1, 8|1=9, 81 << 2 (exact 256)
    assert drum(16, 16, 5, W) == 256     # fits in 5 bits -> exact
    assert drum(255, 255, 4, W) == 57600  # 15*15 << 8 (exact 65025)
    assert drum(0, 5, 4, W) == 0
    assert drum(5, 0, 4, W) == 0


def test_drum_lsb_trick_only_when_bits_dropped():
    """a=16 at k=4 drops one bit, so the LSB correction fires and DRUM
    OVERestimates a value that was exactly representable. At k=5 nothing is
    dropped and the result is exact. This is the cost of unbiased rounding."""
    assert drum(16, 16, 4, W) > 16 * 16
    assert drum(16, 16, 5, W) == 16 * 16


def test_drum_degenerates_to_exact_at_k_equals_w():
    """PROPERTY and the strongest test in this file: at k == w nothing is ever
    dropped, so s == 0 everywhere and DRUM must be bit-exact. An off-by-one in
    the dropped-bit computation fails here and nowhere else."""
    for a in range(1, 1 << W):
        for b in range(1, 1 << W):
            assert drum(a, b, W, W) == a * b


def test_drum_monotone_in_k():
    """Larger k keeps more significant bits, so mean absolute error should not
    increase. Sampled rather than exhaustive to keep the suite fast."""
    prev = None
    for k in range(2, W + 1):
        err = sum(abs(drum(a, b, k, W) - a * b)
                  for a in range(1, 1 << W, 7)
                  for b in range(1, 1 << W, 7))
        if prev is not None:
            assert err <= prev, f"k={k} worse than k={k-1}"
        prev = err


# ---------------------------------------------------------------------------
# Cross-design sanity
# ---------------------------------------------------------------------------

def test_exact_is_exact():
    for a in (0, 1, 127, 255):
        for b in (0, 1, 127, 255):
            assert exact(a, b, W) == a * b


def test_snap_ordering():
    """PROPERTY: for any operands, floor <= both nearest modes <= ceil, since
    all four snap the same operand to one of the same two candidate powers."""
    for a in range(1, 1 << W):
        for b in range(1, 1 << W, 13):
            lo = dlzs_floor(a, b, W)
            hi = dlzs_ceil(a, b, W)
            assert lo <= dlzs_nearest_linear(a, b, W) <= hi
            assert lo <= dlzs_nearest_log(a, b, W) <= hi


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\n{len(fns)} tests passed.")