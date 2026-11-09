"""Score values are free text: the CSV maker owns format and ranking order.

Plain numbers keep the studio's prefix/suffix/decimals formatting; anything
else ("$1.2M", "9.58s", "Gold") is displayed exactly as written. Bar heights
use a lenient numeric parse when every row has one, otherwise they step down
in listed order (first row = #1 = tallest).
"""
import re

_MULTIPLIERS = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}
_LEADING = re.compile(r"^([+-]?\d*\.?\d+)([kKmMbBtT]?)")


def plain_number(raw):
    """Float for plain numeric text (commas allowed), else None."""
    try:
        return float(str(raw).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def numeric_value(raw):
    """Lenient height value: plain, currency, %, K/M/B/T, leading number."""
    plain = plain_number(raw)
    if plain is not None:
        return plain
    text = str(raw).replace(",", "").replace(" ", "").lstrip("$€£¥₹")
    match = _LEADING.match(text)
    if not match:
        return None
    return float(match.group(1)) * _MULTIPLIERS.get(match.group(2).lower(), 1)


_COMPACT = ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K"))


def compact_number(x):
    """200000000 -> '200M', 30000 -> '30K', 4278166 -> '4.28M'."""
    ax = abs(x)
    for div, suf in _COMPACT:
        if ax >= div:
            v = x / div
            d = 2 if abs(v) < 10 else (1 if abs(v) < 100 else 0)
            txt = f"{v:.{d}f}"
            if "." in txt:
                txt = txt.rstrip("0").rstrip(".")
            return txt + suf
    return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.2f}"


def wants_compact(mode, values, suffix):
    """auto: compact big numbers unless the user supplied their own unit."""
    mode = str(mode or "auto").lower()
    if mode in ("on", "true", "yes"):
        return True
    if mode in ("off", "false", "no"):
        return False
    nums = [abs(v) for v in values if v is not None]
    return bool(nums) and max(nums) >= 1e5 and not str(suffix or "").strip()


def display_value(raw, prefix, suffix, decimals, compact=False):
    plain = plain_number(raw)
    if plain is None:
        return str(raw).strip()
    if compact:
        return f"{prefix}{compact_number(plain)}{suffix}"
    if decimals > 0:
        num = f"{plain:,.{decimals}f}"
    else:
        num = f"{int(round(plain)):,}"
    return f"{prefix}{num}{suffix}"