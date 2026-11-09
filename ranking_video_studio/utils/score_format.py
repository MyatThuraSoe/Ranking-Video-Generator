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


def display_value(raw, prefix, suffix, decimals):
    plain = plain_number(raw)
    if plain is None:
        return str(raw).strip()
    if decimals > 0:
        num = f"{plain:,.{decimals}f}"
    else:
        num = f"{int(round(plain)):,}"
    return f"{prefix}{num}{suffix}"