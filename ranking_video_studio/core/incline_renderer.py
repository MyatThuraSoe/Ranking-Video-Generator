"""Incline-camera 3D tower renderer (Cinematic Tracking Camera).

Towers are fully built from frame 0 and never move. The camera tracks
left-to-right from the smallest tower to the biggest. Its pace is
height-aware: segments leading into taller / steeply rising towers get
extra screen time, and the elevation leads the pan so the camera rises
toward each INCOMING tower top -- where the logo, nameplate and value
live -- keeping it locked in frame and never cut off.
Still streams frame-by-frame: nothing is buffered, all assets pre-built.
"""
import math
import random

import cairo

from core.easing import calculate_progress
from core.scaling import compute_fractions, scale_note
from utils.config import TOP_N
from utils.score_format import display_value, numeric_value, wants_compact

# ---- World layout (metres) ----
SLOT    = 4.2     # distance between tower centres along X
TOWER_W = 2.6     # width of the SHORTEST tower (X axis)
TOWER_W_MAX = 3.7 # width of the tallest tower: leaders get a bigger face for text
TOWER_D = 2.4     # tower depth  (Z axis)
MAX_H   = 9.5     # height of the #1 tower
MIN_H   = 1.2     # legacy minimum; cfg.min_tower_h overrides (see render)

_HORISON_COL = (0.62, 0.66, 0.70)   # fog / distance fade colour


# ---------------------------------------------------------------- vector math
def _norm(v):
    l = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / l, v[1] / l, v[2] / l)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _lerp(a, b, t):
    return a + (b - a) * t


def _mix(c1, c2, t):
    return (_lerp(c1[0], c2[0], t), _lerp(c1[1], c2[1], t), _lerp(c1[2], c2[2], t))


def _focus_height(xs_hs, x_val):
    """Smoothstep-interpolated tower height at world x = x_val.

    xs_hs is a list of (x, height) sorted by ascending x. Used to raise the
    camera in lock-step with the tower it is currently passing so tall tower
    tops (and their logos/nameplates) never leave the frame.
    """
    if not xs_hs:
        return MIN_H
    if x_val <= xs_hs[0][0]:
        return xs_hs[0][1]
    if x_val >= xs_hs[-1][0]:
        return xs_hs[-1][1]
    for j in range(len(xs_hs) - 1):
        x0, h0 = xs_hs[j]
        x1, h1 = xs_hs[j + 1]
        if x0 <= x_val <= x1:
            span = (x1 - x0) or 1.0
            tl = (x_val - x0) / span
            ts = tl * tl * (3.0 - 2.0 * tl)   # smoothstep
            return h0 + (h1 - h0) * ts
    return xs_hs[-1][1]


def _pan_segments(tower_pts, x_min, x_max):
    """Weighted path segments for the pan.

    A segment leading into a taller tower (absolute height) or a steep
    rise (height jump) costs more progress, so the camera dwells slightly
    longer there instead of rushing past the reveal.
    """
    breaks = [x_min]
    breaks.extend(x for x, _h in tower_pts if x_min < x < x_max)
    breaks.append(x_max)
    clamp = tower_pts[-1][0] if tower_pts else x_max
    segs = []
    total = 0.0
    for b0, b1 in zip(breaks, breaks[1:]):
        length = b1 - b0
        if length <= 1e-6:
            continue
        # heights the camera actually frames while crossing this segment
        # (elevation leads the pan by ~one slot)
        h0 = _focus_height(tower_pts, min(clamp, b0 + SLOT * 0.9))
        h1 = _focus_height(tower_pts, min(clamp, b1 + SLOT * 0.9))
        jump = max(0.0, h1 - h0) / MAX_H
        weight = length * (1.0 + 0.45 * (h1 / MAX_H) + 1.10 * jump)
        # Suspense: linger on the last three reveals (#3, #2, then the leader)
        from_end = max(0.0, (x_max - b1) / SLOT)
        if from_end < 3.0:
            weight *= 1.0 + 0.85 * (3.0 - from_end) / 3.0
        segs.append((b0, b1, total, weight))
        total += weight
    return segs, total


def _monotone_slopes(us, xs):
    """Fritsch-Carlson tangents for a monotone C1 cubic Hermite interpolant.

    us / xs are strictly increasing knot coordinates. The returned slopes
    guarantee the curve never overshoots (camera never reverses) and that
    velocity is continuous across every knot -- no lurch at tower boundaries.
    """
    n = len(us)
    if n < 2:
        return [0.0] * n
    d = [(xs[k + 1] - xs[k]) / (us[k + 1] - us[k])
         if us[k + 1] > us[k] else 0.0 for k in range(n - 1)]
    m = [0.0] * n
    m[0] = d[0]
    m[-1] = d[-1]
    for k in range(1, n - 1):
        m[k] = 0.0 if d[k - 1] * d[k] <= 0.0 else (d[k - 1] + d[k]) * 0.5
    for k in range(n - 1):
        if d[k] == 0.0:
            m[k] = 0.0
            m[k + 1] = 0.0
            continue
        a = m[k] / d[k]
        b = m[k + 1] / d[k]
        if a < 0.0:
            m[k] = 0.0
            a = 0.0
        if b < 0.0:
            m[k + 1] = 0.0
            b = 0.0
        s = a * a + b * b
        if s > 9.0:
            tau = 3.0 / math.sqrt(s)
            m[k] = tau * a * d[k]
            m[k + 1] = tau * b * d[k]
    return m


def _monotone_eval(u, us, xs, m):
    """Evaluate the monotone cubic Hermite curve at u (clamped to the ends)."""
    n = len(us)
    if n == 0:
        return 0.0
    if u <= us[0]:
        return xs[0]
    if u >= us[-1]:
        return xs[-1]
    for k in range(n - 1):
        if us[k] <= u <= us[k + 1]:
            h = us[k + 1] - us[k]
            if h <= 0.0:
                return xs[k]
            t = (u - us[k]) / h
            t2 = t * t
            t3 = t2 * t
            return ((2 * t3 - 3 * t2 + 1) * xs[k]
                    + (t3 - 2 * t2 + t) * h * m[k]
                    + (-2 * t3 + 3 * t2) * xs[k + 1]
                    + (t3 - t2) * h * m[k + 1])
    return xs[-1]


def _adaptive_pan_x(e, segs, total, x_min, x_max):
    """Map eased progress 0..1 onto a smooth, height-aware pan path.

    The weighted segment lengths become knot spacing: a segment leading into
    a tall / steeply rising tower spans more progress, so the camera dwells
    there. A monotone cubic through those knots keeps velocity continuous
    (cinematic glide) instead of the old piecewise-linear speed jumps.
    """
    if not segs or total <= 0.0:
        return _lerp(x_min, x_max, e)
    us = [0.0]
    xs = [x_min]
    for _b0, b1, cum, weight in segs:
        us.append((cum + weight) / total)
        xs.append(b1)
    m = _monotone_slopes(us, xs)
    return _monotone_eval(min(1.0, max(0.0, e)), us, xs, m)


def _clamp01(x):
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def _smoothstep(x):
    x = _clamp01(x)
    return x * x * (3.0 - 2.0 * x)


def _smootherstep(x):
    x = _clamp01(x)
    return x * x * x * (x * (x * 6.0 - 15.0) + 10.0)


def _trapezoid_ease(u, ramp=0.08):
    """Position for a trapezoid velocity profile: soft start, steady cruise,
    soft stop. With many towers the old cubic ease-out flew past the first
    half of the list; this keeps a near-constant, readable pace."""
    u = _clamp01(u)
    r = max(1e-3, min(0.45, ramp))
    k = 1.0 - r
    if u < r:
        return 0.5 * u * u / r / k
    if u > 1.0 - r:
        d = 1.0 - u
        return 1.0 - 0.5 * d * d / r / k
    return (0.5 * r + (u - r)) / k


def _pan_ease(u, style, n):
    """Pan progress: user easing for short lists, steady cruise for long ones."""
    if n > 12:
        return _trapezoid_ease(u)
    return calculate_progress(u, style)


def _smax(a, b, k):
    """Smooth maximum (C1): clamps without a velocity hitch."""
    return 0.5 * (a + b + math.sqrt((a - b) * (a - b) + k * k))


def _avg_focus_height(xs_hs, x, spread):
    """Box-filtered tower height around x: smooths the auto-zoom so the dolly
    never twitches as individual towers pass."""
    pts = (-1.0, -0.5, 0.0, 0.5, 1.0)
    return sum(_focus_height(xs_hs, x + p * spread) for p in pts) / len(pts)


def _pill_text(ctx, text, cx, cy, px, fg, bg, alpha=1.0, bold=True, pad=0.55):
    """Centred text on a rounded dark pill (used for footnote / callout)."""
    if not text or alpha <= 0.01:
        return
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(px)
    xb, yb, tw, th, _, _ = ctx.text_extents(text)
    pw, ph = tw + px * pad * 2.0, th + px * pad * 1.2
    _rounded_rect(ctx, cx - pw / 2, cy - ph / 2, pw, ph, ph / 2)
    ctx.set_source_rgba(bg[0], bg[1], bg[2], 0.62 * alpha)
    ctx.fill()
    ctx.set_source_rgba(fg[0], fg[1], fg[2], alpha)
    ctx.move_to(cx - tw / 2 - xb, cy - th / 2 - yb)
    ctx.show_text(text)


def _draw_vignette(ctx, w, h, strength):
    if strength <= 0.01:
        return
    diag = math.hypot(w, h) / 2.0
    g = cairo.RadialGradient(w / 2, h / 2, diag * 0.50, w / 2, h / 2, diag)
    g.add_color_stop_rgba(0, 0, 0, 0, 0.0)
    g.add_color_stop_rgba(1, 0, 0, 0, min(0.85, strength))
    ctx.set_source(g)
    ctx.rectangle(0, 0, w, h)
    ctx.fill()


class Camera:
    """Simple look-at perspective camera."""

    def __init__(self, w, h, focal):
        self.w, self.h, self.f = w, h, focal
        self.shift_y = 0.0       # lens shift (px): recentres without tilting
        self.pos = (0.0, 0.0, 0.0)
        self.right = (1.0, 0.0, 0.0)
        self.up = (0.0, 1.0, 0.0)
        self.fwd = (0.0, 0.0, 1.0)

    def look_at(self, pos, target):
        self.pos = pos
        self.fwd = _norm(_sub(target, pos))
        self.right = _norm(_cross((0.0, 1.0, 0.0), self.fwd))
        self.up = _cross(self.fwd, self.right)

    def project(self, p):
        """World point -> (screen_x, screen_y, pixels_per_unit, depth)."""
        d = _sub(p, self.pos)
        z = _dot(d, self.fwd)
        if z < 0.15:
            return None
        s = self.f / z
        return (self.w * 0.5 + _dot(d, self.right) * s,
                self.h * 0.5 + self.shift_y - _dot(d, self.up) * s,
                s, z)


# ---------------------------------------------------------------- asset prep
def build_incline_assets(cfg, df, assets, ap_module):
    """Called once per config change from render_engine.build_assets()."""
    scale = cfg.scale()
    assets.incline_logos = {}
    assets.incline_flags = {}

    n = min(getattr(cfg, "top_n", TOP_N), len(df))
    shape = getattr(cfg, "avatar_shape", "square")
    radius = getattr(cfg, "avatar_border_radius", 0.0)
    bcolor = getattr(cfg, "avatar_border_color", (1.0, 1.0, 1.0))
    bsize = getattr(cfg, "avatar_border_size", 0.0)
    assets.incline_bar_surface = None
    gpath = getattr(cfg, "tower_image", "")
    if isinstance(gpath, str) and gpath.strip() and gpath.strip().lower() != "nan":
        assets.incline_bar_surface = ap_module.process_tower_bar_image(
            gpath.strip(), int(512 * scale))
    for i in range(n):
        row = df.iloc[i]
        path = row.get("image")
        if isinstance(path, str) and path.strip() and path.strip().lower() != "nan":
            surf = ap_module.process_avatar_image(
                path.strip(), int(360 * scale), shape, radius, bcolor, bsize)
            if surf is not None:
                assets.incline_logos[i] = surf
        fpath = row.get("flag")
        if isinstance(fpath, str) and fpath.strip() and fpath.strip().lower() != "nan":
            surf = ap_module.make_waving_flag(fpath.strip(), int(150 * scale))
            if surf is not None:
                assets.incline_flags[i] = surf

    # Procedural city skyline silhouette on the horizon (deterministic)
    rnd = random.Random(42)
    assets.skyline_rects = []
    x = 0.0
    while x < 1.0:
        w = rnd.uniform(0.02, 0.06)
        assets.skyline_rects.append((x, w, rnd.uniform(0.25, 1.0)))
        x += w + rnd.uniform(0.004, 0.02)
    return assets


# ---------------------------------------------------------------- drawing helpers
def _fill_quad(ctx, cam, pts, color, alpha=1.0):
    proj = [cam.project(p) for p in pts]
    if any(p is None for p in proj):
        return None
    ctx.set_source_rgba(color[0], color[1], color[2], alpha)
    ctx.move_to(proj[0][0], proj[0][1])
    for p in proj[1:]:
        ctx.line_to(p[0], p[1])
    ctx.close_path()
    ctx.fill()
    return proj


def _billboard_surface(ctx, surf, px, py, world_h, s, alpha=1.0):
    """Draw a cairo surface as a camera-facing sprite, bottom-centred at px,py."""
    oh = surf.get_height() or 1
    ow = surf.get_width() or 1
    target_h = world_h * s
    if target_h <= 1:
        return
    k = target_h / oh
    ctx.save()
    if alpha < 1.0:
        ctx.push_group()
    ctx.translate(px - (ow * k) / 2.0, py - target_h)
    ctx.scale(k, k)
    ctx.set_source_surface(surf, 0, 0)
    ctx.paint()
    if alpha < 1.0:
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(alpha)
    ctx.restore()


def _billboard_stretch(ctx, surf, px, py, world_w, world_h, s, alpha=1.0):
    """Draw a surface stretched to world_w x world_h, bottom-centred at px,py."""
    oh = surf.get_height() or 1
    ow = surf.get_width() or 1
    tw, th = world_w * s, world_h * s
    if tw <= 1 or th <= 1:
        return
    ctx.save()
    if alpha < 1.0:
        ctx.push_group()
    ctx.translate(px - tw / 2.0, py - th)
    ctx.scale(tw / ow, th / oh)
    ctx.set_source_surface(surf, 0, 0)
    ctx.paint()
    if alpha < 1.0:
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(alpha)
    ctx.restore()


def _wrap_text(ctx, text, max_width):
    """Greedy word-wrap to max_width px using the current font; splits overlong words."""
    lines = []
    for para in str(text).split("\n"):
        words = para.split()
        if not words:
            lines.append("")
            continue
        cur = ""
        for word in words:
            trial = f"{cur} {word}" if cur else word
            if ctx.text_extents(trial)[4] <= max_width:
                cur = trial
            elif not cur:
                chunk = ""
                for ch in word:
                    if chunk and ctx.text_extents(chunk + ch)[4] > max_width:
                        lines.append(chunk)
                        chunk = ch
                    else:
                        chunk += ch
                cur = chunk
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines or [""]


def _draw_lines(ctx, lines, cx, first_cy, line_h):
    """Draw wrapped lines centred on cx, first line glyph-centred at first_cy."""
    for k, ln in enumerate(lines):
        if not ln:
            continue
        xb, yb, twd, thd, _, _ = ctx.text_extents(ln)
        cy = first_cy + k * line_h
        ctx.move_to(cx - twd / 2 - xb, cy - yb - thd / 2)
        ctx.show_text(ln)


_REF_PX = 200.0


def _ref_width(ctx, serif_bold, text, px):
    """Width of ``text`` at ``px`` measured from a large reference size, so the
    result is linear in px (no small-size hinting jitter between towers)."""
    _set_face_font(ctx, serif_bold, _REF_PX)
    return ctx.text_extents(text)[4] * (px / _REF_PX)


def _set_face_font(ctx, serif_bold, px):
    if serif_bold:
        ctx.select_font_face("Serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    else:
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(px)


def _rounded_rect(ctx, x, y, w, h, r):
    r = max(0.0, min(r, h / 2.0, w / 2.0))
    ctx.new_path()
    ctx.move_to(x + r, y)
    ctx.line_to(x + w - r, y)
    ctx.arc(x + w - r, y + r, r, -1.5707963, 0)
    ctx.line_to(x + w, y + h - r)
    ctx.arc(x + w - r, y + h - r, r, 0, 1.5707963)
    ctx.line_to(x + r, y + h)
    ctx.arc(x + r, y + h - r, r, 1.5707963, 3.1415927)
    ctx.line_to(x, y + r)
    ctx.arc(x + r, y + r, r, 3.1415927, 4.7123890)
    ctx.close_path()


def _draw_sky_ground(ctx, cfg, cam, focus_x, skyline_rects, bg_surface,
                     canvas_surface=None):
    w, h = cfg.width, cfg.height
    if canvas_surface is not None:
        # Full-canvas image replaces the whole backdrop: sky, skyline, ground
        ctx.save()
        ctx.set_source_surface(canvas_surface, 0, 0)
        ctx.paint()
        ctx.restore()
        return
    far = cam.project((focus_x - 400.0, 0.0, 0.0))
    horizon = far[1] if far else h * 0.42
    horizon = max(h * 0.30, min(h * 0.66, horizon))

    if cfg.bg_mode == "image" and bg_surface is not None:
        # User photo (already blurred/dimmed) as the scene backdrop
        ctx.save()
        ctx.set_source_surface(bg_surface, 0, 0)
        ctx.paint()
        ctx.restore()
    else:
        sky = cairo.LinearGradient(0, 0, 0, horizon)
        sky.add_color_stop_rgb(0, *cfg.sky_top)
        sky.add_color_stop_rgb(1, *cfg.sky_bottom)
        ctx.set_source(sky)
        ctx.rectangle(0, 0, w, horizon + 1)
        ctx.fill()

    gc = getattr(cfg, "ground_color", (0.44, 0.44, 0.46))
    ground = cairo.LinearGradient(0, horizon, 0, h)
    ground.add_color_stop_rgb(0, *gc)
    # 0.64 keeps the original horizon-to-floor shading depth for any hue
    ground.add_color_stop_rgb(1, gc[0] * 0.64, gc[1] * 0.64, gc[2] * 0.64)
    ctx.set_source(ground)
    ctx.rectangle(0, horizon, w, h - horizon)
    ctx.fill()

    # procedural city skyline sitting on the horizon
    if skyline_rects:
        band = cfg.height * 0.16
        sc = getattr(cfg, "skyline_color", (0.30, 0.31, 0.33))
        ctx.set_source_rgba(sc[0], sc[1], sc[2], 0.95)
        for (xf, wf, hf) in skyline_rects:
            ctx.rectangle(xf * w, horizon - hf * band, wf * w, hf * band + 2)
        ctx.fill()


# ---------------------------------------------------------------- MAIN RENDER
def render_incline_frame(ctx, cfg, df, assets, progress):
    """One full frame. progress = raw 0..1 (speed applied here)."""
    ctx.set_operator(cairo.OPERATOR_SOURCE)
    ctx.set_source_rgba(0, 0, 0, 0)
    ctx.paint()
    ctx.set_operator(cairo.OPERATOR_OVER)

    n = min(getattr(cfg, "top_n", TOP_N), len(df))
    if n == 0:
        return
    scale = cfg.scale()
    W, H = cfg.width, cfg.height

    # ---- Timeline: [intro establishing shot] [pan across towers] [hero hold]
    dur = max(0.1, float(getattr(cfg, "duration", 8.0)))
    intro_f = min(float(getattr(cfg, "intro_seconds", 1.4)), dur * 0.15) / dur
    outro_f = min(float(getattr(cfg, "outro_seconds", 3.2)), dur * 0.30) / dur
    t = _clamp01(progress)
    u_pan = _clamp01((t - intro_f) / max(1e-6, 1.0 - intro_f - outro_f))
    intro_u = _clamp01(t / intro_f) if intro_f > 1e-6 else 1.0
    outro_u = _clamp01((t - (1.0 - outro_f)) / outro_f) if outro_f > 1e-6 else 0.0
    t_sec = t * dur

    # Row order is the ranking (the CSV maker owns it). Heights use a scale
    # chosen for the data's dynamic range (log for million-vs-billion gaps);
    # non-numeric scores step down in listed order so row 1 stays tallest.
    values = [numeric_value(df.iloc[i]["score"]) for i in range(n)]
    numeric = all(v is not None for v in values)
    scale_mode = "rank"
    if numeric:
        fracs, scale_mode = compute_fractions(
            values, getattr(cfg, "scale_mode", "auto"),
            getattr(cfg, "rank_blend", 0.12))
    else:
        fracs = [(n - i) / n for i in range(n)]
    min_h = max(0.4, min(MAX_H - 1.0, getattr(cfg, "min_tower_h", 3.2)))
    compact = numeric and wants_compact(
        getattr(cfg, "value_compact", "auto"), values, cfg.value_suffix)

    # --- STATIC TOWERS (fully built; no growth). Computed first because the
    # camera elevation tracks the height of the tower it is currently passing. ---
    tower_pts = []   # (x, height) for smoothstep focus tracking
    towers = []
    for i in range(n):
        h_final = min_h + (MAX_H - min_h) * fracs[i]
        # Rank N (last row) on the left, Rank 1 (first row) on the right
        x = (n - 1 - i) * SLOT
        tower_pts.append((x, h_final))
        fh = (h_final - min_h) / max(1e-6, MAX_H - min_h)
        w_i = TOWER_W + (TOWER_W_MAX - TOWER_W) * _clamp01(fh)
        towers.append(dict(i=i, x=x, h=h_final, w=w_i, row=df.iloc[i]))
    tower_pts.sort(key=lambda p: p[0])     # ascending x for interpolation

    # --- CINEMATIC CAMERA ---------------------------------------------
    e = _pan_ease(u_pan, cfg.easing, n)
    x_min = 0.0
    leader_x = (n - 1) * SLOT                # tallest tower (rank 1) centre
    x_max = max(x_min, leader_x - SLOT * 1.2)   # pan end, framed on the leader
    segs, total = _pan_segments(tower_pts, x_min, x_max)
    cam_x = _adaptive_pan_x(e, segs, total, x_min, x_max)

    height_x = min(leader_x, cam_x + SLOT * 1.1)
    h_focus = _focus_height(tower_pts, height_x)
    cam_elev = getattr(cfg, "cam_elevation", 3.5)
    look_ahead = getattr(cfg, "cam_look_ahead", 1.2)
    focus_off = getattr(cfg, "cam_focus_offset", 0.5)
    cam_dist = cfg.cam_distance
    cam_side = getattr(cfg, "cam_side", 1.9)
    focal = max(W, H) * getattr(cfg, "cam_fov", 1.05)

    settle = max(0.0, (e - 0.8) / 0.2)
    settle = settle * settle * (3.0 - 2.0 * settle)
    base_x = _lerp(cam_x - SLOT * 1.2, leader_x - SLOT * 0.55, settle)
    ahead = _lerp(look_ahead, min(look_ahead, SLOT * 0.62), settle)
    look_x = _smax(base_x + ahead, x_min + SLOT * 0.35, SLOT * 0.9)

    # Auto-framing: dolly so the tower being revealed (plus its logo) fills a
    # fixed share of the frame. Small towers get a close-up instead of floating
    # tiny in the distance; the user's camera distance stays the far limit.
    h_look = _focus_height(tower_pts, min(leader_x, look_x + SLOT * 0.6))
    if getattr(cfg, "cam_auto_frame", True):
        h_avg = _avg_focus_height(tower_pts, height_x, SLOT * 0.9)
        logo_h = 1.6 * getattr(cfg, "avatar_size", 1.0) \
            if getattr(assets, "incline_logos", None) else 0.6
        # leave room above the leader for the winner-reveal card in the finale
        extent = h_avg + logo_h + 1.0 + 2.4 * _smootherstep(outro_u)
        fill = max(0.3, min(0.9, getattr(cfg, "cam_frame_fill", 0.68)))
        z_v = focal * extent / (fill * H)                  # fit height
        z_h = focal * (SLOT * 2.1) / W                     # keep >= ~2 slots wide
        z = max(z_v, z_h, getattr(cfg, "cam_min_distance", 8.0))
        # "Camera distance" is a zoom trim here (19.5 = neutral)
        z *= max(0.6, min(1.7, cam_dist / 19.5))
        elev_eff = cam_elev * max(0.45, min(1.0, z / 19.5))
        # aim at the middle of tower + logo so the composition is centred
        look_y = (h_look + logo_h) * 0.5 + (focus_off - 0.5)
    else:
        z = cam_dist
        elev_eff = cam_elev
        look_y = h_focus + focus_off

    # -- establishing shot: start high & wide, crane down into the pan
    k_in = 1.0 - _smootherstep(intro_u)
    z *= 1.0 + 0.40 * k_in
    elev_eff += 3.2 * k_in
    # -- hero finale: slow push-in with a gentle orbit toward the leader
    k_out = _smootherstep(outro_u)
    z *= 1.0 - 0.05 * k_out
    cam_side += 1.2 * k_out
    elev_eff -= 0.4 * k_out
    # -- subtle handheld drift keeps long holds alive
    sway = getattr(cfg, "cam_sway", 1.0)
    if sway > 0:
        cam_side += 0.30 * sway * math.sin(2 * math.pi * 0.23 * t_sec)
        elev_eff += 0.10 * sway * math.sin(2 * math.pi * 0.31 * t_sec + 1.1)

    cam = Camera(W, H, focal)
    cam_y = h_focus + elev_eff
    # Level camera + lens shift (architectural look): the camera barely pitches,
    # so tower edges stay vertical instead of leaning; the shift then puts the
    # subject back at a title-safe spot a little below the frame centre.
    level = max(0.0, min(1.0, getattr(cfg, "cam_level", 0.85)))
    cam.look_at((cam_x + cam_side, cam_y, -z),
                (look_x, _lerp(look_y, cam_y, level), 0.0))
    anchor = cam.project((look_x, look_y, 0.0))
    if anchor:
        cam.shift_y = H * (0.54 - 0.01 * k_out) - anchor[1]
    cam_dist = z       # fog / depth cues follow the actual camera distance

    # Which tower is "on stage": follows the pan, locks to the leader at the end
    spot_x = _lerp(cam_x + SLOT * 0.9, leader_x, settle)

    _draw_sky_ground(ctx, cfg, cam, cam_x,
                     getattr(assets, "skyline_rects", None),
                     getattr(assets, "bg_surface", None),
                     getattr(assets, "canvas_surface", None))

    title_bottom = 36 * scale
    # Title (alignment / size / color / top margin; multi-line); slides in
    if cfg.title and cfg.title.strip():
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        font_px = getattr(cfg, "title_font_size", 40) * scale
        ctx.set_font_size(font_px)
        t_ease = _smootherstep(intro_u * 1.25)
        tc = getattr(cfg, "title_color", (1, 1, 1))
        side = 26 * scale
        align = getattr(cfg, "title_align", "left")
        top = getattr(cfg, "title_top_margin", 24) * scale
        top -= (1.0 - t_ease) * font_px * 1.6          # drop in from above
        line_h = font_px * 1.25
        for li, line in enumerate(cfg.title.split("\n")):
            if not line.strip():
                continue
            xb, yb, twd, thd, _, _ = ctx.text_extents(line)
            if align == "center":
                tx = (cfg.width - twd) / 2 - xb
            elif align == "right":
                tx = cfg.width - side - twd - xb
            else:
                tx = side - xb
            ty = top + li * line_h - yb
            # soft shadow keeps the title readable over any background
            ctx.set_source_rgba(0, 0, 0, 0.35 * t_ease)
            ctx.move_to(tx + 2 * scale, ty + 2 * scale)
            ctx.show_text(line)
            ctx.set_source_rgba(tc[0], tc[1], tc[2], t_ease)
            ctx.move_to(tx, ty)
            ctx.show_text(line)
            title_bottom = max(title_bottom, top + (li + 1) * line_h)

    # Depth-sort for painter's algorithm (needs the positioned camera)
    for tw in towers:
        d = cam.project((tw["x"], 0, 0))
        tw["z"] = d[3] if d else 99
    towers.sort(key=lambda d: -d["z"])     # far -> near

    base = cfg.tower_color
    spot_strength = max(0.0, min(0.8, getattr(cfg, "spotlight", 0.28)))
    for tw in towers:
        x, h, i = tw["x"], tw["h"], tw["i"]

        # Cull towers that cannot be seen (50-100 items stay fast to render)
        pc = cam.project((x, h * 0.5, 0.0))
        if pc is None:
            continue
        half_px = tw["w"] * pc[2] * 1.3
        if pc[0] < -half_px * 2.5 or pc[0] > W + half_px * 2.5:
            continue

        # Spotlight: towers away from the one on stage dim slightly
        emph = math.exp(-(((x - spot_x) / (SLOT * 1.7)) ** 2))
        dim = spot_strength * (1.0 - emph)

        fog = max(0.0, min(0.55, (tw["z"] - cam_dist * 0.8) / 45.0))
        c_front = _mix(base, _HORISON_COL, fog)
        c_side = _mix((base[0] * 0.72, base[1] * 0.72, base[2] * 0.72), _HORISON_COL, fog)
        c_top = _mix((min(1, base[0] * 1.14), min(1, base[1] * 1.14), min(1, base[2] * 1.14)),
                     _HORISON_COL, fog)
        if dim > 0.0:
            shade = (0.10, 0.11, 0.16)
            c_front = _mix(c_front, shade, dim)
            c_side = _mix(c_side, shade, dim)
            c_top = _mix(c_top, shade, dim)

        hw, hd = tw["w"] / 2.0, TOWER_D / 2.0
        wscale = tw["w"] / TOWER_W      # on-face text grows with the face

        # Ground shadow (sun from left); toggled by the Drop-shadow checkbox
        if getattr(cfg, "shadow_enabled", True):
            _fill_quad(ctx, cam,
                       [(x + hw, 0.01, -hd), (x + hw + 2.3, 0.01, -hd + 0.7),
                        (x + hw + 2.3, 0.01, hd + 0.7), (x + hw, 0.01, hd)],
                       (0, 0, 0), 0.22)

        bar_surf = getattr(assets, "incline_bar_surface", None)
        if bar_surf is not None:
            # The shared image stands in for the whole tower body.
            pb = cam.project((x, 0, -hd))
            if pb is None:
                continue
            s = pb[2]
            _billboard_stretch(ctx, bar_surf, pb[0], pb[1], hw * 2.0, h, s)
        else:
            # Side (+X), front (-Z), top
            _fill_quad(ctx, cam,
                       [(x + hw, 0, -hd), (x + hw, 0, hd), (x + hw, h, hd), (x + hw, h, -hd)],
                       c_side)
            front = _fill_quad(ctx, cam,
                               [(x - hw, 0, -hd), (x + hw, 0, -hd),
                                (x + hw, h, -hd), (x - hw, h, -hd)], c_front)
            _fill_quad(ctx, cam,
                       [(x - hw, h, -hd), (x + hw, h, -hd), (x + hw, h, hd), (x - hw, h, hd)],
                       c_top)
            if not front:
                continue
            s = front[0][2]                # pixels-per-world-unit at this depth

        # Face text: top-down flow layout so wrapped blocks never collide.
        face_w = max(8.0, tw["w"] * s * 0.86)
        name = str(tw["row"]["name"])
        sub = tw["row"].get("text")
        sub = "" if sub is None or str(sub).lower() == "nan" else str(sub)
        extra = tw["row"].get("extratext")
        extra = "" if extra is None or str(extra).lower() == "nan" else str(extra)
        dec = getattr(cfg, "value_decimals", 1)
        value_label = display_value(tw["row"]["score"], cfg.value_prefix,
                                    cfg.value_suffix, dec, compact=compact)
        show_badges = getattr(cfg, "show_badges", True)
        # (kind, text, world font size, serif-bold, color, line factor, pad)
        specs = [("plate", name, getattr(cfg, "name_font_size", 0.34), True,
                  getattr(cfg, "name_color", (1, 1, 1)), 1.22, 0.34)]
        if sub:
            specs.append(("text", sub, getattr(cfg, "text_font_size", 0.20),
                          False, getattr(cfg, "text_color", (0.85, 0.85, 0.88)),
                          1.3, 0.0))
        specs.append(("text", value_label, getattr(cfg, "value_font_size", 0.30),
                      True, cfg.value_color, 1.25, 0.0))
        if extra:
            specs.append(("text", extra, getattr(cfg, "extra_font_size", 0.18),
                          False, getattr(cfg, "extra_color", (0.80, 0.82, 0.85)),
                          1.3, 0.0))

        margin = 0.15          # clear space between neighbouring tower elements
        gap = 0.18             # margin between stacked face text blocks

        # Size the rank badge FIRST so the face flow can reserve room below it
        # and the badge stays inside the tower top instead of spilling onto the
        # name plate or floating above the bar.
        badge_half = 0.0
        badge_y = h
        badge_top = h
        badge_metrics = None
        if show_badges:
            label = str(i + 1)
            ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                                 cairo.FONT_WEIGHT_BOLD)
            bfs = cfg.rank_font_size * scale
            ctx.set_font_size(bfs)
            xb, yb, twd, thd, _, _ = ctx.text_extents(label)
            pad = 6 * scale
            bs = getattr(cfg, "badge_size", 1.0)
            if cfg.badge_shape == "circle":
                half_px = max(max(twd, thd) / 2 + pad * 0.4,
                              (max(twd, thd) / 2 + pad) * bs)
            elif cfg.badge_shape == "pill":
                half_px = max(thd + pad * 0.6, (thd + pad * 1.5) * bs) / 2
            else:
                half_px = thd / 2
            # Cap the badge so it never eats more than ~a third of a short bar.
            badge_half = min(half_px / max(1e-6, s),
                             max(0.05, (h - 2 * margin) * 0.35))
            badge_y = h - margin - badge_half     # top edge a margin below tower top
            badge_top = badge_y + badge_half      # == h - margin
            badge_metrics = (label, xb, yb, twd, thd, bfs, pad, bs)

        plate_y = (badge_y - badge_half - margin) if show_badges else (h - margin)
        avail = max(0.15, plate_y - margin)

        # Per-line width fit, decided ONCE at k=1 so it never depends on depth
        # or on how much the block later shrinks: neighbouring towers therefore
        # wrap the same way. A short name shrinks (down to 78%) to stay on one
        # line, otherwise it wraps on word boundaries -- never mid-word.
        boost = max(0.6, min(1.8, getattr(cfg, "text_boost", 1.12))) * wscale
        fits = []
        for kind, txt, fw, serif, col, lf, pad in specs:
            fk = 1.0
            px0 = fw * boost * s
            if kind == "plate" and "\n" not in txt:
                one = _ref_width(ctx, serif, txt, px0)
                if one > face_w and one * 0.78 <= face_w:
                    fk = face_w / one
            words = txt.split()
            if words:
                ww = max(_ref_width(ctx, serif, wd, px0 * fk) for wd in words)
                if ww > face_w:
                    fk *= face_w / ww
            fits.append(fk)

        def measure(k):
            laid, total = [], 0.0
            for (kind, txt, fw, serif, col, lf, pad), fk in zip(specs, fits):
                fw = fw * boost * fk
                _set_face_font(ctx, serif, fw * k * s)
                lines = _wrap_text(ctx, txt, face_w)
                lh = fw * k * lf
                bh = len(lines) * lh + pad * k
                laid.append((kind, lines, fw * k, serif, col, lh, bh))
                total += bh
            return laid, total + gap * k * (len(laid) - 1)

        k = 1.0
        laid, total = measure(k)
        for _ in range(3):
            if total <= avail:
                break
            k *= avail / total
            laid, total = measure(k)

        cursor = plate_y
        for kind, lines, fw, serif, col, lh, bh in laid:
            center = cursor - bh / 2.0
            pr = cam.project((x, center, -hd - 0.02))
            if pr:
                _set_face_font(ctx, serif, fw * s)
                if kind == "plate":
                    widest = max((ctx.text_extents(ln)[4] for ln in lines),
                                 default=0.0)
                    pw = widest + 0.55 * s
                    ctx.set_source_rgb(*cfg.plate_color)
                    _rounded_rect(ctx, pr[0] - pw / 2, pr[1] - bh * s / 2,
                                  pw, bh * s, 0.09 * s)
                    ctx.fill()
                ctx.set_source_rgb(*col)
                _draw_lines(ctx, lines, pr[0],
                            pr[1] - (len(lines) - 1) * lh * s / 2, lh * s)
            cursor -= bh + gap * k

        # Rank badge on the face, drawn at the position reserved above. The
        # face flow changed the font, so restore the badge font before drawing.
        if badge_metrics is not None:
            label, xb, yb, twd, thd, bfs, pad, bs = badge_metrics
            ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                                 cairo.FONT_WEIGHT_BOLD)
            ctx.set_font_size(bfs)
            draw_half = badge_half * s
            bc = cam.project((x, badge_y, -hd - 0.02))
            if bc:
                if cfg.badge_shape != "text":
                    ctx.set_source_rgb(*cfg.badge_color)
                    if cfg.badge_shape == "circle":
                        ctx.arc(bc[0], bc[1], draw_half, 0, 6.2831853)
                        ctx.fill()
                    else:  # pill
                        bw = max(twd + pad * 0.8, (twd + pad * 2.4) * bs)
                        bh = draw_half * 2
                        _rounded_rect(ctx, bc[0] - bw / 2, bc[1] - bh / 2,
                                      bw, bh, bh / 2)
                        ctx.fill()
                ctx.set_source_rgb(*cfg.rank_color)
                ctx.move_to(bc[0] - twd / 2 - xb, bc[1] - thd / 2 - yb)
                ctx.show_text(label)

        # Logo floating above the tower top, separated by a clear margin. The
        # billboard is bottom-anchored, so logo_y is where its bottom edge sits.
        logo = getattr(assets, "incline_logos", {}).get(i)
        if logo is not None:
            world_h = 1.6 * getattr(cfg, "avatar_size", 1.0)
            logo_y = max(h, badge_top) + margin
            top = cam.project((x, logo_y, 0))
            if top:
                _billboard_surface(ctx, logo, top[0], top[1], world_h, top[2], alpha=1.0)

        # Waving flag on the top-right corner (sprite pre-warped once)
        flag = getattr(assets, "incline_flags", {}).get(i)
        if flag is not None:
            pb = cam.project((x + hw * 0.55, h, hd * 0.45))
            pt = cam.project((x + hw * 0.55, h + 1.15, hd * 0.45))
            if pb and pt:
                ctx.set_source_rgba(0.16, 0.14, 0.11, 1.0)
                ctx.set_line_width(max(1.0, 0.045 * pt[2]))
                ctx.move_to(pb[0], pb[1])
                ctx.line_to(pt[0], pt[1])
                ctx.stroke()
                fh = 0.62 * pt[2]
                ctx.save()
                ctx.translate(pt[0], pt[1])
                ctx.scale(fh / max(1, flag.get_height()), fh / max(1, flag.get_height()))
                ctx.set_source_surface(flag, 0, 0)
                ctx.paint()
                ctx.restore()

    # ------------------------------------------------ winner reveal card (#1)
    pop = _smootherstep((outro_u - 0.10) / 0.35)
    if pop > 0.01:
        lead = next((t_ for t_ in towers if t_["i"] == 0), None)
        if lead is not None:
            logo_up = 1.6 * getattr(cfg, "avatar_size", 1.0) + 0.35 \
                if getattr(assets, "incline_logos", {}).get(0) is not None else 0.0
            top_y = lead["h"] + logo_up + 0.55
            pa = cam.project((lead["x"], top_y, 0.0))
            if pa:
                sc = pa[2] * (0.88 + 0.12 * pop)
                cw, ch = 5.0 * sc, 1.75 * sc
                cx, cy = pa[0], pa[1] - ch / 2.0 - (1.0 - pop) * 0.6 * sc
                pc_ = cfg.plate_color
                _rounded_rect(ctx, cx - cw / 2, cy - ch / 2, cw, ch, 0.22 * sc)
                ctx.set_source_rgba(pc_[0], pc_[1], pc_[2], 0.94 * pop)
                ctx.fill_preserve()
                bc_ = getattr(cfg, "badge_color", (1.0, 0.76, 0.16))
                ctx.set_source_rgba(bc_[0], bc_[1], bc_[2], pop)
                ctx.set_line_width(max(2.0, 0.07 * sc))
                ctx.stroke()
                nm = str(lead["row"]["name"])
                vl = display_value(lead["row"]["score"], cfg.value_prefix,
                                   cfg.value_suffix, getattr(cfg, "value_decimals", 1),
                                   compact=compact)
                inner = cw * 0.9
                npx = 0.66 * sc
                w_ = _ref_width(ctx, True, nm, npx)
                if w_ > inner:
                    npx *= inner / w_
                vpx = 0.60 * sc
                w_ = _ref_width(ctx, True, vl, vpx)
                if w_ > inner:
                    vpx *= inner / w_
                nc_ = getattr(cfg, "name_color", (1, 1, 1))
                _set_face_font(ctx, True, npx)
                ctx.set_source_rgba(nc_[0], nc_[1], nc_[2], pop)
                _draw_lines(ctx, [nm], cx, cy - ch * 0.20, npx)
                _set_face_font(ctx, True, vpx)
                ctx.set_source_rgba(bc_[0], bc_[1], bc_[2], pop)
                _draw_lines(ctx, [vl], cx, cy + ch * 0.22, vpx)

    # ---------------------------------------------------------- post / overlays
    _draw_vignette(ctx, W, H, getattr(cfg, "vignette", 0.30) * (1.0 + 0.5 * k_out))

    fade_in = _smootherstep(intro_u / 0.6)
    # Vertical (Shorts / Reels): the platform UI covers the bottom ~17%
    safe_bottom = H * 0.17 if H > W * 1.3 else 0.0
    note = scale_note(scale_mode) if numeric else ""
    if note and getattr(cfg, "show_scale_note", True):
        _pill_text(ctx, note, W / 2, H - 34 * scale - safe_bottom, 22 * scale,
                   (1, 1, 1), (0, 0, 0), alpha=0.9 * fade_in, bold=False)

    if (getattr(cfg, "show_gap_callout", True) and numeric and n > 1
            and values[n - 1] > 0 and outro_u > 0.25):
        ratio = values[0] / values[n - 1]
        if ratio >= 2.0:
            r_txt = f"{ratio:,.0f}" if ratio >= 100 else f"{ratio:,.1f}"
            _pill_text(ctx, f"#1 is {r_txt}\u00d7 bigger than #{n}",
                       W / 2, H - 84 * scale - safe_bottom, 34 * scale,
                       getattr(cfg, "badge_color", (1.0, 0.76, 0.16)),
                       (0, 0, 0), alpha=_smootherstep((outro_u - 0.25) / 0.4))

    if intro_u < 1.0:                      # fade in from black
        ctx.set_source_rgba(0, 0, 0, 1.0 - fade_in)
        ctx.rectangle(0, 0, W, H)
        ctx.fill()
