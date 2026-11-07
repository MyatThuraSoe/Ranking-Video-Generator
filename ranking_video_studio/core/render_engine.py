import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import asset_processor as ap
from core import incline_renderer as ir


class SceneAssets:
    """Holds all pre-rendered surfaces. Built ONCE per config change."""

    def __init__(self):
        self.bg_surface = None


def build_assets(cfg, df):
    assets = SceneAssets()

    if cfg.bg_mode == "image" and cfg.bg_image and os.path.isfile(cfg.bg_image):
        try:
            assets.bg_surface = ap.process_background_image(
                cfg.bg_image, cfg.width, cfg.height, cfg.bg_blur, cfg.bg_dim)
        except Exception as e:
            print(f"[warn] background image failed: {e}")

    ir.build_incline_assets(cfg, df, assets, ap)
    return assets


def render_frame(ctx, cfg, df, assets, progress):
    """Draw one complete frame. progress is raw [0,1] (speed applied inside)."""
    return ir.render_incline_frame(ctx, cfg, df, assets, progress)

