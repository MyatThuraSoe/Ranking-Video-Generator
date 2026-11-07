import os
import sys

import cairo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import asset_processor as ap
from core.easing import calculate_progress
from utils.config import TOP_N


class SceneAssets:
    """Holds all pre-rendered surfaces. Built ONCE per config change."""

    def __init__(self):
        self.bg_surface = None
        self.tile_surface = None
        self.tile_size = (0, 0)
        self.avatars = {}  # row index -> cairo surface


def layout_metrics(cfg, n_items):
    scale = cfg.scale()
    title_size = 54 * scale
    top = cfg.height * 0.16
    bottom = cfg.height * 0.96
    avail_h = bottom - top
    row_h = avail_h / max(1, n_items)
    bar_h = row_h * 0.72
    badge_zone = 78 * scale if cfg.show_badges else 16 * scale
    left_margin = 24 * scale + badge_zone
    right_margin = 210 * scale
    max_bar_w = max(60.0, cfg.width - left_margin - right_margin)
    min_w = 30 * scale
    return dict(scale=scale, title_size=title_size, top=top, row_h=row_h,
                bar_h=bar_h, left_margin=left_margin,
                max_bar_w=max_bar_w, min_w=min_w)


def build_assets(cfg, df):
    assets = SceneAssets()
    n = min(TOP_N, len(df))
    m = layout_metrics(cfg, n)
    bar_h = int(m["bar_h"])

    if cfg.bg_mode == "image" and cfg.bg_image and os.path.isfile(cfg.bg_image):
        try:
            assets.bg_surface = ap.process_background_image(
                cfg.bg_image, cfg.width, cfg.height, cfg.bg_blur, cfg.bg_dim)
        except Exception as e:
            print(f"[warn] background image failed: {e}")

    if cfg.tile_image and os.path.isfile(cfg.tile_image):
        assets.tile_surface, assets.tile_size = ap.process_tile_image(
            cfg.tile_image, bar_h, int(cfg.tile_radius), int(cfg.tile_opacity),
            cfg.tint_enabled, cfg.tint_color)

    avatar_size = max(8, int(bar_h * 0.82))
    for i in range(n):
        path = df.iloc[i].get("image")
        if isinstance(path, str) and path.strip() and path.strip().lower() != "nan" \
                and os.path.isfile(path.strip()):
            surf = ap.process_avatar_image(path.strip(), avatar_size, cfg.avatar_shape)
            if surf is not None:
                assets.avatars[i] = surf

    if getattr(cfg, "camera_mode", "flat") == "incline":
        from core import incline_renderer as ir
        ir.build_incline_assets(cfg, df, assets, ap)
    return assets


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


def _draw_background(ctx, cfg, assets):
    if assets.bg_surface is not None:
        ctx.save()
        ctx.set_source_surface(assets.bg_surface, 0, 0)
        ctx.paint()
        ctx.restore()
        return
    if cfg.bg_mode == "gradient":
        grad = cairo.LinearGradient(0, 0, 0, cfg.height)
        grad.add_color_stop_rgb(0, *cfg.bg_color2)
        grad.add_color_stop_rgb(1, *cfg.bg_color)
        ctx.set_source(grad)
    else:
        ctx.set_source_rgb(*cfg.bg_color)
    ctx.paint()


def _draw_badge(ctx, cfg, m, rank, cx, cy):
    if not cfg.show_badges:
        return
    scale = m["scale"]
    font_size = cfg.rank_font_size * scale
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(font_size)
    label = str(rank)
    xb, yb, tw, th, _, _ = ctx.text_extents(label)

    if cfg.badge_shape == "text":
        ctx.set_source_rgb(1, 1, 1)
        ctx.move_to(cx - tw / 2 - xb, cy - th / 2 - yb)
        ctx.show_text(label)
        return

    pad = 12 * scale
    if cfg.badge_shape == "circle":
        r = max(tw, th) / 2 + pad
        ctx.set_source_rgb(*cfg.badge_color)
        ctx.arc(cx, cy, r, 0, 6.2831853)
        ctx.fill()
    else:  # pill
        bw = tw + pad * 2.4
        bh = th + pad * 1.5
        ctx.set_source_rgb(*cfg.badge_color)
        _rounded_rect(ctx, cx - bw / 2, cy - bh / 2, bw, bh, bh / 2)
        ctx.fill()

    ctx.set_source_rgb(*cfg.rank_color)
    ctx.move_to(cx - tw / 2 - xb, cy - th / 2 - yb)
    ctx.show_text(label)


def _draw_bar(ctx, cfg, m, assets, x, y, cur_w):
    bar_h = m["bar_h"]
    radius = cfg.tile_radius * m["scale"] if not assets.tile_surface else \
        min(cfg.tile_radius * m["scale"], bar_h / 2)

    if cfg.shadow_enabled:
        ctx.save()
        ctx.set_source_rgba(0, 0, 0, 0.35)
        _rounded_rect(ctx, x + 5 * m["scale"], y + 4 * m["scale"],
                      cur_w, bar_h, radius)
        ctx.fill()
        ctx.restore()

    if assets.tile_surface is not None and assets.tile_size[0] > 0:
        tw, th = assets.tile_size
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(cur_w / tw, bar_h / th)
        ctx.set_source_surface(assets.tile_surface, 0, 0)
        ctx.paint()
        ctx.restore()
    else:
        grad = cairo.LinearGradient(0, y, 0, y + bar_h)
        r, g, b = cfg.bar_color
        grad.add_color_stop_rgb(0, min(1, r * 1.25 + 0.06),
                                min(1, g * 1.25 + 0.06),
                                min(1, b * 1.25 + 0.06))
        grad.add_color_stop_rgb(1, r * 0.82, g * 0.82, b * 0.82)
        ctx.set_source(grad)
        _rounded_rect(ctx, x, y, cur_w, bar_h, radius)
        ctx.fill()


def render_frame(ctx, cfg, df, assets, progress):
    """Draw one complete frame. progress is raw [0,1] (speed applied here)."""
    # Clear once with SOURCE, then composite everything with OVER so that
    # paint() calls (tiles, avatars, background) never erase prior draws.
    ctx.set_operator(cairo.OPERATOR_SOURCE)
    ctx.set_source_rgba(0, 0, 0, 0)
    ctx.paint()
    ctx.set_operator(cairo.OPERATOR_OVER)

    if getattr(cfg, "camera_mode", "flat") == "incline":
        from core import incline_renderer as ir
        return ir.render_incline_frame(ctx, cfg, df, assets, progress)

    n = min(TOP_N, len(df))
    if n == 0:
        _draw_background(ctx, cfg, assets)
        return
    m = layout_metrics(cfg, n)
    scale = m["scale"]

    _draw_background(ctx, cfg, assets)

    # Title
    if cfg.title and cfg.title.strip():
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                             cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(m["title_size"])
        ctx.set_source_rgba(1, 1, 1, 0.96)
        xb, yb, tw, th, _, _ = ctx.text_extents(cfg.title)
        ctx.move_to((cfg.width - tw) / 2 - xb, cfg.height * 0.09 - th / 2 - yb)
        ctx.show_text(cfg.title)

    eased = calculate_progress(min(1.0, progress * cfg.speed), cfg.easing)
    max_score = float(df["score"].iloc[0]) or 1.0
    if max_score <= 0:
        max_score = 1.0

    name_size = 30 * scale
    sub_size = 19 * scale
    score_size = 32 * scale
    avatar_pad = 10 * scale

    for i in range(n):
        row = df.iloc[i]
        score = float(row["score"])
        target_w = max(m["min_w"], (score / max_score) * m["max_bar_w"])
        cur_w = m["min_w"] + (target_w - m["min_w"]) * max(0.0, eased)

        y = m["top"] + i * m["row_h"] + (m["row_h"] - m["bar_h"]) / 2
        x = m["left_margin"]
        cy = y + m["bar_h"] / 2

        _draw_badge(ctx, cfg, m, i + 1, x - 44 * scale, cy)
        _draw_bar(ctx, cfg, m, assets, x, y, cur_w)

        # Avatar
        text_x = x + 16 * scale
        if i in assets.avatars:
            av = assets.avatars[i]
            av_h = av.get_height()
            av_w = av.get_width()
            ctx.save()
            ctx.set_source_surface(av, x + avatar_pad, cy - av_h / 2)
            ctx.paint()
            ctx.restore()
            text_x = x + avatar_pad + av_w + 10 * scale

        name = str(row["name"])
        text = row.get("text")
        text = "" if text is None or str(text).lower() == "nan" else str(text)
        if len(text) > 35:
            text = text[:35]

        # Name + subtitle inside the bar
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                             cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(name_size)
        ctx.set_source_rgba(1, 1, 1, 0.98)
        if text:
            ctx.move_to(text_x, cy - 4 * scale)
            ctx.show_text(name)
            ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                                 cairo.FONT_WEIGHT_NORMAL)
            ctx.set_font_size(sub_size)
            ctx.set_source_rgba(1, 1, 1, 0.72)
            ctx.move_to(text_x, cy + sub_size * 1.35)
            ctx.show_text(text)
        else:
            xb, yb, tw, th, _, _ = ctx.text_extents(name)
            ctx.move_to(text_x, cy - th / 2 - yb)
            ctx.show_text(name)

        # Animated score counter at the right edge of the bar
        cur_score = score * max(0.0, eased)
        score_label = f"{int(round(cur_score)):,}"
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                             cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(score_size)
        ctx.set_source_rgba(1, 1, 1, 0.95)
        xb, yb, tw, th, _, _ = ctx.text_extents(score_label)
        sx = x + cur_w + 14 * scale
        if sx + tw > cfg.width - 8 * scale:
            sx = cfg.width - 8 * scale - tw
        ctx.move_to(sx, cy - th / 2 - yb)
        ctx.show_text(score_label)
