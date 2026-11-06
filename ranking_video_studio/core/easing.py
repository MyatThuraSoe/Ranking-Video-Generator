import math

STYLES = ("cubic", "elastic", "exponential", "linear")


def calculate_progress(t, style="cubic"):
    """Return eased value for input t. t is clamped to [0, 1].

    Elastic output may briefly exceed 1.0 for the overshoot effect.
    """
    t = max(0.0, min(1.0, float(t)))
    if t == 0.0:
        return 0.0
    if t == 1.0:
        return 1.0

    if style == "linear":
        return t
    if style == "elastic":
        c4 = (2 * math.pi) / 3
        return math.pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1
    if style == "exponential":
        return 1 - math.pow(2, -10 * t)
    # cubic ease-out (default)
    return 1 - math.pow(1 - t, 3)
