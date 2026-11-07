"""Incline-camera 3D tower renderer (Static Towers + Camera Pan).

Towers are fully built from frame 0. The camera tracks left-to-right,
moving from the smallest tower to the biggest tower.
Still streams frame-by-frame: nothing is buffered, all assets pre-built.
"""
import math
import random

import cairo

from core.easing import calculate_progress
from utils.config import TOP_N

# ---- World layout (metres) ----
SLOT    = 3.2     # distance between tower centres along X
TOWER_W = 2.4     # tower width  (X axis)
TOWER_D = 2.4     # tower depth  (Z axis)
MAX_H   = 9.5     # height of the #1 tower
MIN_H   = 1.2     # minimum visible height

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


class Camera:
    """Simple look-at perspective camera."""

    def __init__(self, w, h, focal):
        self.w, self.h, self.f = w, h, focal
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
                self.h * 0.5 - _dot(d, self.up) * s,
                s, z)


# ---------------------------------------------------------------- asset prep
def build_incline_assets(cfg, df, assets, ap_module):
    """Called once per config change from render_engine.build_assets()."""
    scale = cfg.scale()
    assets.incline_logos = {}
    assets.incline_flags = {}

    n = min(TOP_N, len(df))
    for i in range(n):
        row = df.iloc[i]
        path = row.get("image")
        if isinstance(path, str) and path.strip() and path.strip().lower() != "nan":
            surf = ap_module.process_avatar_image(path.strip(), int(360 * scale), "square")
            if surf is not None:
                assets.incline_logos[i] = surf
        fpath = row.get("flag")
        if isinstance(fpath, str) and fpath.strip() and fpath.strip().lower() != "nan":
            surf = ap_module.make_waving_flag(fpath.strip(), int(150 * scale))
            if surf is not None:
                assets.incline_flags[i] = surf

    # Skyline silhouette strip (user image, or deterministic procedural city)
    assets.skyline = None
    assets.skyline_rects = None
    if getattr(cfg, "skyline_image", ""):
        import os
        from PIL import Image
        if os.path.isfile(cfg.skyline_image):
            img = Image.open(cfg.skyline_image).convert("RGBA")
            h = max(40, int(cfg.height * 0.20))
            img = img.resize((cfg.width, h), Image.Resampling.LANCZOS)
            assets.skyline = ap_module.pil_surface(img)
    if assets.skyline is None:
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


def _draw_sky_ground(ctx, cfg, cam, focus_x, skyline, skyline_rects):
    w, h = cfg.width, cfg.height
    far = cam.project((focus_x - 400.0, 0.0, 0.0))
    horizon = far[1] if far else h * 0.42
    horizon = max(h * 0.18, min(h * 0.62, horizon))

    sky = cairo.LinearGradient(0, 0, 0, horizon)
    sky.add_color_stop_rgb(0, *cfg.sky_top)
    sky.add_color_stop_rgb(1, *cfg.sky_bottom)
    ctx.set_source(sky)
    ctx.rectangle(0, 0, w, horizon + 1)
    ctx.fill()

    ground = cairo.LinearGradient(0, horizon, 0, h)
    ground.add_color_stop_rgb(0, 0.44, 0.44, 0.46)
    ground.add_color_stop_rgb(1, 0.28, 0.28, 0.30)
    ctx.set_source(ground)
    ctx.rectangle(0, horizon, w, h - horizon)
    ctx.fill()

    # skyline silhouette sitting on the horizon
    if skyline is not None:
        sh = skyline.get_height()
        ctx.save()
        ctx.set_source_surface(skyline, 0, horizon - sh + 2)
        ctx.paint_with_alpha(0.92)
        ctx.restore()
    elif skyline_rects:
        band = cfg.height * 0.16
        ctx.set_source_rgba(0.30, 0.31, 0.33, 0.95)
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

    n = min(TOP_N, len(df))
    if n == 0:
        return
    scale = cfg.scale()
    t = min(1.0, progress * cfg.speed)

    # --- CAMERA MOVEMENT (default: pan left to right) ---
    e = calculate_progress(t, "cubic")
    # Bounds chosen so the view starts on the smallest tower and ends
    # framed on the leader (look-ahead offset compensated).
    x_min = -SLOT * 1.2
    x_max = (n - 1) * SLOT - SLOT * 1.2
    move = getattr(cfg, "camera_move", "pan")
    focal_mult = 1.0
    if move == "static":
        cam_x = (x_min + x_max) * 0.5
    elif move == "push":
        cam_x = x_max
        focal_mult = 1.0 + 0.10 * e
    elif move == "follow":
        cam_x = x_max
    else:  # pan
        cam_x = _lerp(x_min, x_max, e)
    look_x = cam_x - SLOT * 1.2  # look back along the row: near tower right,
    #                            # row receding to upper-left like the sample
    focal = max(cfg.width, cfg.height) * getattr(cfg, "cam_fov", 1.05) * focal_mult
    cam = Camera(cfg.width, cfg.height, focal)
    cam.look_at((cam_x + getattr(cfg, "cam_side", 1.9), cfg.cam_height, -cfg.cam_distance),
                (look_x, getattr(cfg, "cam_look_height", 1.5), 0.0))

    _draw_sky_ground(ctx, cfg, cam, cam_x,
                     getattr(assets, "skyline", None),
                     getattr(assets, "skyline_rects", None))

    # Title (watermark style, top-left like the sample)
    if cfg.title and cfg.title.strip():
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(40 * scale)
        ctx.set_source_rgba(1, 1, 1, 0.92)
        ctx.move_to(26 * scale, 52 * scale)
        ctx.show_text(cfg.title)

    max_score = float(df["score"].iloc[0]) or 1.0
    if max_score <= 0:
        max_score = 1.0

    # --- STATIC TOWER PLACEMENT (no growth: towers exist from frame 0) ---
    towers = []
    for i in range(n):
        score = float(df.iloc[i]["score"])
        h_final = MIN_H + (MAX_H - MIN_H) * (score / max_score)
        # Rank N (smallest) on the left, Rank 1 (biggest) on the right
        x = (n - 1 - i) * SLOT
        depth = cam.project((x, 0, 0))
        towers.append(dict(i=i, x=x, h=h_final, score=score,
                           row=df.iloc[i], z=depth[3] if depth else 99))

    towers.sort(key=lambda d: -d["z"])     # painter's algorithm: far -> near

    base = cfg.tower_color
    for tw in towers:
        x, h, i = tw["x"], tw["h"], tw["i"]
        fog = max(0.0, min(0.55, (tw["z"] - cfg.cam_distance * 0.8) / 45.0))
        c_front = _mix(base, _HORISON_COL, fog)
        c_side = _mix((base[0] * 0.72, base[1] * 0.72, base[2] * 0.72), _HORISON_COL, fog)
        c_top = _mix((min(1, base[0] * 1.14), min(1, base[1] * 1.14), min(1, base[2] * 1.14)),
                     _HORISON_COL, fog)

        hw, hd = TOWER_W / 2.0, TOWER_D / 2.0

        # Ground shadow (sun from left)
        _fill_quad(ctx, cam,
                   [(x + hw, 0.01, -hd), (x + hw + 2.3, 0.01, -hd + 0.7),
                    (x + hw + 2.3, 0.01, hd + 0.7), (x + hw, 0.01, hd)],
                   (0, 0, 0), 0.22)

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
        s = front[0][2]                    # pixels-per-world-unit at this depth

        # Name plate on the face
        name = str(tw["row"]["name"])
        plate_y = max(0.45, h - 0.62)
        pc = cam.project((x, plate_y, -hd - 0.02))
        if pc:
            ctx.select_font_face("Serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            fs = 0.34 * s
            ctx.set_font_size(fs)
            xb, yb, twd, thd, _, _ = ctx.text_extents(name)
            pw, ph = twd + 0.55 * s, 0.66 * s
            ctx.set_source_rgb(*cfg.plate_color)
            _rounded_rect(ctx, pc[0] - pw / 2, pc[1] - ph / 2, pw, ph, 0.09 * s)
            ctx.fill()
            ctx.set_source_rgb(1, 1, 1)
            ctx.move_to(pc[0] - twd / 2 - xb, pc[1] + fs * 0.35 - yb - fs / 2)
            ctx.show_text(name)

        # Value on the face (static: towers already exist)
        vc = cam.project((x, max(0.30, h - 1.45), -hd - 0.02))
        if vc:
            dec = getattr(cfg, "value_decimals", 1)
            num = f"{tw['score']:,.{dec}f}" if dec > 0 else f"{int(round(tw['score'])):,}"
            label = f"{cfg.value_prefix}{num}{cfg.value_suffix}"
            ctx.select_font_face("Serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            ctx.set_font_size(0.30 * s)
            ctx.set_source_rgb(*cfg.value_color)
            xb, yb, twd, thd, _, _ = ctx.text_extents(label)
            ctx.move_to(vc[0] - twd / 2 - xb, vc[1] + 0.20 * s - yb)
            ctx.show_text(label)

        # Logo floating above the top
        logo = getattr(assets, "incline_logos", {}).get(i)
        if logo is not None:
            top = cam.project((x, h + 0.25, 0))
            if top:
                _billboard_surface(ctx, logo, top[0], top[1], 1.6, top[2], alpha=1.0)

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
