"""
golden_model.py — Bit-exact reference models for approximate multipliers.

This module is the authority against which all RTL is verified. Every design
here is implemented in pure Python integer arithmetic: no floats appear in any
datapath, so results are exactly reproducible and can be compared bit-for-bit
with SystemVerilog simulation output.

Designs implemented
-------------------
exact                 : reference w x w multiplication
dlzs_floor            : DLZS, operand A snapped DOWN to 2^floor(log2 A)
dlzs_ceil             : DLZS, operand A snapped UP   to 2^ceil(log2 A)
dlzs_nearest_linear   : DLZS, A snapped to nearer power of two (linear metric)
dlzs_nearest_log      : DLZS, A snapped to nearer power of two (log metric)
mitchell              : Mitchell (1962) log-domain multiplier, both operands
drum                  : DRUM(k) dynamic-range unbiased multiplier

DLZS background
---------------
DLZS (differential leading-zero summation) originates in SOFA (Wang et al.,
MICRO 2024). It converts ONE operand to the log domain via its leading-zero
count -- snapping it to a power of two -- and shifts the other operand, so the
multiply becomes shift-only hardware. SOFA Eq. 1a-1c is notationally ambiguous
about snap direction, which is why all four interpretations are implemented
here and characterized empirically before a spec is chosen.

Convention: operand A is always the snapped operand, operand B is shifted.
An adaptive variant (snap whichever operand has the smaller mantissa) is
deliberately NOT implemented here; it costs a comparator plus two muxes on the
wide datapath and is deferred until the fixed-choice numbers are in.

Zero handling
-------------
lead_one() is undefined at zero and raises. Every multiplier guards zero
operands explicitly and returns 0, which is exactly correct. This guard must be
mirrored in RTL -- a missing zero path is the most common source of
model/RTL divergence.
"""

__all__ = [
    "lead_one",
    "exact",
    "dlzs_floor",
    "dlzs_ceil",
    "dlzs_nearest_linear",
    "dlzs_nearest_log",
    "mitchell",
    "drum_extract",
    "drum",
    "to_signed",
    "to_unsigned",
    "signed_wrap",
    "DESIGNS",
    "SIGNED_DESIGNS",
]


# ---------------------------------------------------------------------------
# Primitive
# ---------------------------------------------------------------------------

def lead_one(a, w):
    """Position of the most significant set bit of `a`, i.e. floor(log2 a).

    This is the value a hardware leading-zero counter produces as
    (w - 1) - LZC(a). Raises on zero rather than returning a plausible-looking
    index, so that any caller which forgets the zero guard fails loudly instead
    of silently computing b << 0 == b.
    """
    assert 0 <= a < (1 << w), f"operand {a} out of range for width {w}"
    if a == 0:
        raise ValueError("lead_one undefined for 0")
    return a.bit_length() - 1


# ---------------------------------------------------------------------------
# Reference
# ---------------------------------------------------------------------------

def exact(a, b, w):
    """Exact w x w unsigned product. `w` is accepted for signature uniformity
    and used only to range-check the operands."""
    assert 0 <= a < (1 << w), f"operand {a} out of range for width {w}"
    assert 0 <= b < (1 << w), f"operand {b} out of range for width {w}"
    return a * b


# ---------------------------------------------------------------------------
# DLZS family -- one operand snapped to a power of two, the other shifted
# ---------------------------------------------------------------------------

def dlzs_floor(a, b, w):
    """DLZS with A snapped DOWN: A -> 2^floor(log2 A).

    Relative error of A is -m/(1+m) for mantissa m in [0,1), i.e. (-0.5, 0].
    Always underestimates; strong negative bias; worst case -50%.
    """
    if a == 0 or b == 0:
        return 0
    return b << lead_one(a, w)


def dlzs_ceil(a, b, w):
    """DLZS with A snapped UP: A -> 2^ceil(log2 A).

    Relative error of A is in [0, +1.0). Always overestimates. Exact powers of
    two are left alone -- `a & (a - 1)` is non-zero only when A has a non-zero
    mantissa, i.e. only when there is something to round.
    """
    if a == 0 or b == 0:
        return 0
    k = lead_one(a, w)
    if a & (a - 1):          # A is not an exact power of two
        k = k + 1
    return b << k


def dlzs_nearest_linear(a, b, w):
    """DLZS with A snapped to the nearer power of two, LINEAR metric.

    Midpoint between 2^k and 2^(k+1) is 1.5 * 2^k, i.e. mantissa m = 0.5.
    Since the mantissa's most significant bit is bit (k-1) of A, the round-up
    decision is a single bit test -- in RTL, one wire tapped off the bit below
    the leading one. Relative error of A is in [-0.25, +0.333].

    TIE-BREAK: A == 1.5 * 2^k rounds UP (ties away from zero). This is a
    specification, not an accident, and the RTL must match it bit-for-bit.
    Tie values at w=8 are {3, 6, 12, 24, 48, 96, 192} -- corner-case list.

    The `k > 0` guard exists only to protect the shift: k == 0 means A == 1,
    which has no mantissa bits and would make (k - 1) a negative shift count.
    """
    if a == 0 or b == 0:
        return 0
    k = lead_one(a, w)
    if k > 0 and (a >> (k - 1)) & 1:
        k = k + 1
    return b << k


def dlzs_nearest_log(a, b, w):
    """DLZS with A snapped to the nearer power of two, LOG metric.

    The log-space midpoint is sqrt(2) * 2^k, since
        (sqrt(2) * 2^k) / 2^k  ==  2^(k+1) / (sqrt(2) * 2^k)  ==  sqrt(2).
    Squaring both sides of  A >= sqrt(2) * 2^k  removes the radical and gives
    the integer test  A^2 >= 2^(2k+1),  so no float ever enters the datapath.

    Error bounds: the snap is symmetric in RATIO -- A is never off by more than
    a factor of sqrt(2) either way -- but that is NOT symmetric in linear
    relative error. Snapping down gives at worst 1/sqrt(2) - 1 = -0.293;
    snapping up gives at worst 2/sqrt(2) - 1 = +0.414. Measured over the
    exhaustive 8-bit sweep the observed max |RED| is 0.4066 (A=91 -> 128),
    below the +0.414 asymptote because integer A cannot sit exactly on the
    threshold. Do not quote this mode as "+/-0.293" in the report.

    No tie case exists: equality would require A = 2^k * sqrt(2), which is
    irrational and therefore never an integer. One fewer spec detail to match
    in RTL than nearest_linear.

    NOTE for vectorization: A*A reaches ~4.29e9 at w=16, which overflows int32.
    Force int64 in NumPy, or precompute per-k thresholds ceil(sqrt(2) * 2^k)
    and compare A directly (which is also closer to the RTL form).
    """
    if a == 0 or b == 0:
        return 0
    k = lead_one(a, w)
    if a * a >= (1 << (2 * k + 1)):
        k = k + 1
    return b << k


# ---------------------------------------------------------------------------
# Mitchell (1962) -- BOTH operands converted to log domain
# ---------------------------------------------------------------------------

def mitchell(a, b, w):
    """Mitchell's log-domain multiplier.

    Writing A = 2^ka * (1 + ma), the approximation log2(1 + m) ~= m makes the
    binary representation its own logarithm: log2 A ~= ka + ma is literally the
    bits of A rearranged, no computation. Then

        P = 2^(ka+kb) * (1 + ma + mb)                    if ma + mb <  1
        P = 2^(ka+kb+1) * (ma + mb)                      if ma + mb >= 1

    With Ma = A - 2^ka the raw mantissa bits, the denominators cancel:
        2^(ka+kb) * (ma + mb)  ==  (Ma << kb) + (Mb << ka)  ==  `frac`
    which makes both branches pure shift-and-add, and makes the carry test a
    comparison between `frac` and `base` that reuses the same quantity.

    The two branches agree in the limit ma+mb -> 1: the no-carry form tends to
    base + base = 2^(ka+kb+1), which is what the carry form yields. That
    continuity check is the cheapest possible validation of the carry algebra.

    Since log2(1+m) >= m for both operands, Mitchell ALWAYS underestimates.
    Worst-case error is about -11.1%, when both mantissas sit near 0.44.
    """
    if a == 0 or b == 0:
        return 0
    ka, kb = lead_one(a, w), lead_one(b, w)
    Ma, Mb = a - (1 << ka), b - (1 << kb)
    frac = (Ma << kb) + (Mb << ka)      # == 2^(ka+kb) * (ma + mb)
    base = 1 << (ka + kb)               # == 2^(ka+kb)
    if frac < base:                     # ma + mb < 1, no carry
        return base + frac
    return frac << 1                    # carry into the exponent


# ---------------------------------------------------------------------------
# DRUM(k) -- truncation to k significant bits, exact k x k core multiply
# ---------------------------------------------------------------------------

def drum_extract(a, k, w):
    """Extract the k most significant bits of `a` starting at its leading one.

    Returns (truncated_value, shift), where `shift` is the number of dropped
    bits. The caller shifts the k x k product back up by (sa + sb).

    UNBIASED ROUNDING: the dropped bits are approximately uniform on
    [0, 2^s), so their expected value is 2^s / 2 -- exactly half a unit in the
    last place of the truncated field. Forcing the LSB high adds precisely that
    when the LSB was 0, and nothing when it was already 1, so the mean signed
    error sits near zero instead of strictly negative. In hardware the wire is
    tied high and the core multiplier shrinks to (k-1) effective input bits.

    The correction is applied ONLY when s > 0. If the operand already fits in
    k bits nothing was discarded, there is no remainder to compensate for, and
    forcing the LSB would inject error into a value that was exact (e.g. a=4,
    k=4 would become 5). Guarding on `s` rather than on the leading-one
    position is what makes DRUM degenerate correctly to exact multiplication
    at k == w.
    """
    ka = lead_one(a, w)
    s = max(0, ka - k + 1)      # dropped bits; 0 when the operand fits in k
    t = a >> s
    if s > 0:
        t |= 1                  # unbiased rounding for the discarded remainder
    return t, s


def drum(a, b, k, w):
    """DRUM(k): truncate both operands to k significant bits, multiply exactly,
    shift the result back up. The core multiplier is k x k regardless of w,
    which is where the area saving comes from.

    Unlike every other design in this module, DRUM is designed to be unbiased.
    Mitchell and dlzs_floor are strictly negative-biased, dlzs_ceil strictly
    positive, and the nearest modes roughly balanced but not by construction.
    That distinction matters for ranking tasks, where a uniform bias largely
    cancels but variance does not.
    """
    if a == 0 or b == 0:
        return 0
    ta, sa = drum_extract(a, k, w)
    tb, sb = drum_extract(b, k, w)
    return (ta * tb) << (sa + sb)


# ---------------------------------------------------------------------------
# Signed operation -- sign-magnitude wrapper around any unsigned design
# ---------------------------------------------------------------------------
#
# rtl/dlzc_mult_top.sv computes sign = A[w-1] ^ B[w-1], takes the two's
# complement magnitude of each operand, feeds the UNSIGNED core, and negates
# the result if the signs differ. This section is the bit-exact model of that.
#
# Two properties of the wrapper are worth stating explicitly, because both are
# claims the report will make:
#
#   1. The wrapper is EXACT. It introduces no approximation of its own -- it is
#      a bijection composed with the unsigned core. Every bit of error in a
#      signed product is error the unsigned core already had on the magnitudes.
#      The existing unsigned characterization therefore still applies; only the
#      operand DISTRIBUTION changes (see below).
#
#   2. The error is symmetric about zero by construction, since the magnitude
#      path cannot see the sign. This is a good property for the top-k ranking
#      study, and it is also why signed `bias` is a useless metric -- over a
#      symmetric input set it averages to ~0 no matter how biased the core is.
#      Characterize bias on MAGNITUDES.
#
# Distribution note: signed w-bit magnitudes span 0..2^(w-1), so the top binade
# all but disappears -- at w=16 the only magnitude with lead_one == 15 is
# 32768 itself. Signed sweep tables are not comparable to unsigned ones and
# must say which distribution they were taken over.

def to_signed(u, w):
    """Interpret a w-bit pattern as two's complement."""
    assert 0 <= u < (1 << w), f"pattern {u} out of range for width {w}"
    return u - (1 << w) if u >> (w - 1) else u


def to_unsigned(x, w):
    """Two's complement bit pattern of `x` in w bits. Accepts either sign."""
    return x & ((1 << w) - 1)


def signed_wrap(design, a, b, w):
    """Signed w x w product via `design` applied to the magnitudes.

    WIDTH SUBTLETY -- this is the one thing that makes signed operation not a
    drop-in call. abs(-2^(w-1)) == 2^(w-1), which occupies w bits of STORAGE
    but is out of range for a w-bit unsigned operand, so lead_one's
    `a < (1 << w)` assert fires. The core is therefore invoked at width w+1.
    That is a range check only: no design in this module consults `w` for
    anything but the assert, so the datapath is unchanged.

    The RTL gets away with the same thing implicitly, because abs_value1 is
    declared unsigned [15:0] and 0x8000 is simply 32768 there. Declaring those
    intermediates `signed` would break it.

    Negative zero is not a hazard: the core returns 0 for a zero operand, and
    the two's complement of 0 is 0, so the sign bit is harmlessly ignored.
    """
    lo, hi = -(1 << (w - 1)), (1 << (w - 1)) - 1
    assert lo <= a <= hi, f"operand {a} out of range for signed width {w}"
    assert lo <= b <= hi, f"operand {b} out of range for signed width {w}"

    magnitude = design(abs(a), abs(b), w + 1)
    return -magnitude if (a < 0) != (b < 0) else magnitude


# ---------------------------------------------------------------------------
# Registry -- lets sweep/characterization code iterate designs uniformly.
# Every entry is a callable (a, b, w) -> int, so DRUM's k is bound here.
# ---------------------------------------------------------------------------

DESIGNS = {
    "exact":               exact,
    "dlzs_floor":          dlzs_floor,
    "dlzs_ceil":           dlzs_ceil,
    "dlzs_nearest_linear": dlzs_nearest_linear,
    "dlzs_nearest_log":    dlzs_nearest_log,
    "mitchell":            mitchell,
    "drum4":               lambda a, b, w: drum(a, b, 4, w),
    "drum6":               lambda a, b, w: drum(a, b, 6, w),
}
# Same designs under the sign-magnitude wrapper. Signature is (a, b, w) with a
# and b two's complement in range [-2^(w-1), 2^(w-1)-1], so signed sweeps can
# reuse the unsigned driver code unchanged.
#
# `exact` is wrapped too rather than aliased to `a * b`: it exercises the same
# assert path as the approximate entries, so an out-of-range operand fails on
# the reference row instead of surviving to poison the comparison.
SIGNED_DESIGNS = {
    name: (lambda fn: lambda a, b, w: signed_wrap(fn, a, b, w))(fn)
    for name, fn in DESIGNS.items()
}