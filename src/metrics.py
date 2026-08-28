"""
metrics.py — Error characterization for approximate multipliers.

Metric definitions are pinned down here because they must be defended in the
report and must match the conventions used in the approximate-computing
literature, or the comparison table against published DRUM/Mitchell figures is
not meaningful.

Definitions
-----------
Let P be the exact product and Ph the approximate product, over a set of N
input pairs.

    RED       = |Ph - P| / P                    (undefined at P = 0)
    MRED      = mean(RED)                       scale-invariant; dominated by
                                                small products
    max RED   = max(RED)                        worst-case relative error
    bias      = mean((Ph - P) / P)              SIGNED -- the sign is the whole
                                                point; predicts ranking
                                                behaviour in the top-k study
    NMED      = mean(|Ph - P|) / P_max          normalized by the MAXIMUM
                                                representable product, not
                                                per-sample, so it is comparable
                                                across designs at equal width
    max AED   = max(|Ph - P|)                   worst-case absolute error
    error rate= fraction of pairs with Ph != P

Zero-product handling
---------------------
RED evaluates to 0/0 when P = 0. This is a removable singularity, not missing
information: every design in golden_model.py guards zero operands and returns
exactly 0, so the true error on those pairs is zero. The formula is defective
there, the data is not.

Accordingly:
  * RED-based metrics (MRED, max RED, bias) are computed over the NON-ZERO
    product subset, and `n_red` is reported alongside so the denominator is
    always visible.
  * Absolute metrics (NMED, max AED) have no singularity and are computed over
    the FULL set.
  * Error rate is computed over the FULL set. Excluding zero pairs here would
    inflate it by pretending legitimate correct answers do not exist.

At w = 8 exhaustive this means n_total = 65536 and n_red = 65025, with 511
zero-product pairs excluded from RED only.

Caveat for the Week 10 application study: RED explodes for small P even when
absolute error is tiny. Real attention scores can be near zero, so MRED may
look poor while top-k overlap stays high. That gap is expected and is a
property of the metric, not of the hardware.
"""

__all__ = ["error_metrics", "p_max_for_width", "format_table"]


def p_max_for_width(w):
    """Maximum representable exact product at width w, used as the NMED
    normalizer. Note that some designs (e.g. dlzs_ceil) can produce results
    ABOVE this value -- dlzs_ceil(255, 255, 8) = 65280 vs exact 65025 -- which
    is legitimate and stays within 2w bits. Size RTL output ports from 2w, not
    from the exact product's range.
    """
    return ((1 << w) - 1) ** 2


def error_metrics(exact_vals, approx_vals, w):
    """Compute the full metric set for one design.

    Parameters
    ----------
    exact_vals  : sequence of exact products
    approx_vals : sequence of approximate products, same order and length
    w           : operand bit-width, used to derive the NMED normalizer

    Returns
    -------
    dict with keys: mred, max_red, bias, nmed, max_aed, error_rate,
                    n_total, n_red
    """
    if len(exact_vals) != len(approx_vals):
        raise ValueError("exact and approx sequences must be the same length")

    n_total = len(exact_vals)
    if n_total == 0:
        raise ValueError("empty input set")

    p_max = ((1 << w) - 1) ** 2

    # --- full-set accumulators (absolute error, no singularity) ------------
    sum_abs = 0
    max_aed = 0
    n_wrong = 0

    # --- non-zero-product accumulators (relative error) -------------------
    sum_abs_red = 0.0
    sum_signed_red = 0.0
    max_red = 0.0
    n_red = 0

    for p, ph in zip(exact_vals, approx_vals):
        d = ph - p
        ad = abs(d)

        sum_abs += ad
        if ad > max_aed:
            max_aed = ad
        if d != 0:
            n_wrong += 1

        if p != 0:
            red = d / p                 # signed
            ared = abs(red)
            sum_abs_red += ared
            sum_signed_red += red
            if ared > max_red:
                max_red = ared
            n_red += 1

    if n_red == 0:
        raise ValueError("no non-zero products; RED metrics undefined")

    return {
        "mred":       sum_abs_red / n_red,
        "max_red":    max_red,
        "bias":       sum_signed_red / n_red,   # signed, do NOT abs()
        "nmed":       (sum_abs / n_total) / p_max,
        "max_aed":    max_aed,
        "error_rate": n_wrong / n_total,
        "n_total":    n_total,
        "n_red":      n_red,
    }


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------

_COLUMNS = [
    ("design",     "{:<20}", "{:<20}"),
    ("MRED",       "{:>9}",  "{:>9.5f}"),
    ("maxRED",     "{:>9}",  "{:>9.5f}"),
    ("bias",       "{:>10}", "{:>+10.5f}"),
    ("NMED",       "{:>10}", "{:>10.6f}"),
    ("maxAED",     "{:>12}", "{:>12d}"),
    ("err_rate",   "{:>9}",  "{:>9.5f}"),
]


def format_table(results, title=None):
    """Render {design_name: metrics_dict} as a fixed-width text table.

    Denominators are printed in the footer rather than as columns, since they
    are identical across designs for a given sweep but must still be visible.
    """
    lines = []
    if title:
        lines.append(title)
    header = "".join(fmt.format(name) for name, fmt, _ in _COLUMNS)
    lines.append(header)
    lines.append("-" * len(header))

    for name, m in results.items():
        row = (
            _COLUMNS[0][2].format(name)
            + _COLUMNS[1][2].format(m["mred"])
            + _COLUMNS[2][2].format(m["max_red"])
            + _COLUMNS[3][2].format(m["bias"])
            + _COLUMNS[4][2].format(m["nmed"])
            + _COLUMNS[5][2].format(m["max_aed"])
            + _COLUMNS[6][2].format(m["error_rate"])
        )
        lines.append(row)

    any_m = next(iter(results.values()))
    lines.append("-" * len(header))
    lines.append(
        f"n_total = {any_m['n_total']} (NMED, maxAED, err_rate); "
        f"n_red = {any_m['n_red']} (MRED, maxRED, bias; zero-product pairs "
        f"excluded, all designs exact on them by construction)"
    )
    return "\n".join(lines)