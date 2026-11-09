"""Bar-height scaling for data with a huge dynamic range.

Linear heights make a 30,000 vs 200,000,000 chart unreadable: everything but
the top few bars collapses to the minimum height. This module maps values to
a 0..1 fraction using one of several scales, always preserving ranking order.

Modes
-----
auto    pick from the dynamic range (max / min) -- the default
linear  height ~ value            (use when values are within ~4x)
sqrt    height ~ sqrt(value)      (moderate spread, up to ~25x)
log     height ~ log(value)       (any spread; millions vs billions)
rank    equal steps by rank       (ignores magnitude completely)

A small ``rank_blend`` mixes in equal rank steps for the non-linear modes so
neighbouring towers never look identical even when their values are close.
"""
import math

MODES = ("auto", "linear", "sqrt", "log", "rank")

SCALE_NOTES = {
    "log": "Bars use a logarithmic scale",
    "sqrt": "Bars use a square-root scale",
    "rank": "Bars show rank order, not exact size",
}


def dynamic_range(values):
    """max/min ratio over positive values; inf when zeros or negatives exist."""
    if not values:
        return 1.0
    lo, hi = min(values), max(values)
    if lo <= 0:
        return math.inf if hi > 0 else 1.0
    return hi / lo


def resolve_mode(values, mode="auto"):
    mode = (mode or "auto").lower()
    if mode in ("linear", "sqrt", "log", "rank"):
        return mode
    r = dynamic_range(values)
    if r <= 4.0:
        return "linear"
    if r <= 25.0:
        return "sqrt"
    return "log"


def _rank_fracs(values):
    """1.0 for the largest value down to 0.0 for the smallest, equal steps."""
    n = len(values)
    if n <= 1:
        return [1.0] * n
    order = sorted(range(n), key=lambda i: values[i], reverse=True)
    out = [0.0] * n
    for pos, i in enumerate(order):
        out[i] = 1.0 - pos / (n - 1)
    return out


def _log_fracs(values):
    """Log scale anchored at the smallest value; safe for zeros/negatives."""
    vmin, vmax = min(values), max(values)
    span = vmax - vmin
    if span <= 0:
        return [1.0] * len(values)
    if vmin > 0:
        s = vmin                       # exactly log(v / vmin)
    else:
        shifted = sorted(v - vmin for v in values if v - vmin > 0)
        s = max(shifted[0] if shifted else span, span * 1e-6)
    denom = math.log1p(span / s)
    return [math.log1p((v - vmin) / s) / denom for v in values]


def compute_fractions(values, mode="auto", rank_blend=0.12):
    """Return (fractions in 0..1, resolved_mode). Order of ``values`` kept."""
    n = len(values)
    if n == 0:
        return [], "linear"
    mode = resolve_mode(values, mode)
    vmax = max(values)
    vmin = min(values)

    if mode == "rank":
        return _rank_fracs(values), mode

    if mode == "linear":
        top = vmax if vmax > 0 else 1.0
        return [max(0.0, v / top) for v in values], mode

    if mode == "sqrt":
        span = vmax - vmin
        if span <= 0:
            base = [1.0] * n
        else:
            base = [math.sqrt(max(0.0, (v - vmin) / span)) for v in values]
    else:  # log
        base = _log_fracs(values)

    w = max(0.0, min(0.5, float(rank_blend)))
    if w > 0 and n > 1:
        rk = _rank_fracs(values)
        base = [(1 - w) * b + w * r for b, r in zip(base, rk)]
    return base, mode


def scale_note(mode):
    return SCALE_NOTES.get(mode, "")
