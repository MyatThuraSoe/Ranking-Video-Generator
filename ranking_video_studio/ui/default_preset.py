"""The factory default look: the packaged "Sample Template 1".

The shipping default is the Sample Template 1 staged into the build seed
(16:9 landscape, low cinematic camera, warm ground tones), so a fresh install
opens on the creator's chosen style. When no packaged template is present
(bare source checkout without a staged seed) the curated hook look below is
used instead. Keys match ``MainWindow.capture_template()`` so the window can
apply the preset with ``apply_template()``.
"""
import json

from utils import app_paths
from utils.config import TOP_N

_TITLE = "WHO TAKES #1?"

_FALLBACK = {
    "top_n": TOP_N,
    "aspect": "9:16 Vertical FHD (1080x1920)",
    "quality": "Ultra High (CRF 18)",
    "fps": "30",
    "preset": "fast",
    "low_resource": True,
    "speed": 1.0,
    "easing": "Smooth Deceleration (Cubic)",
    "title": _TITLE,
    "title_align": "Center",
    "title_size": 72,
    "title_color": [1.0, 1.0, 1.0],
    "title_margin": 74,
    "bg_mode": "Sky Gradient",
    "bg_blur": 10,
    "bg_dim": 40,
    "shadow": True,
    "show_badges": True,
    "badge_shape": "Pill",
    "badge_color": [1.0, 0.76, 0.16],
    "badge_size": 1.3,
    "rank_size": 40,
    "rank_color": [0.05, 0.05, 0.10],
    "name_size": 0.38,
    "name_color": [1.0, 1.0, 1.0],
    "value_size": 0.34,
    "value_color": [0.55, 0.05, 0.08],
    "text_size": 0.22,
    "text_color": [0.34, 0.29, 0.24],
    "extra_size": 0.20,
    "extra_color": [0.40, 0.34, 0.28],
    "value_prefix": "$ ",
    "value_suffix": " B",
    "value_decimals": 1,
    "cam_elev": 33,
    "cam_dist": 195,
    "cam_side": 24,
    "cam_ahead": 16,
    "cam_focus": 5,
    "fov": 114,
    "tower_color": [0.84, 0.79, 0.65],
    "plate_color": [0.16, 0.13, 0.16],
    "sky_top": [0.10, 0.22, 0.45],
    "sky_bottom": [0.72, 0.85, 0.95],
    "ground_color": [0.44, 0.44, 0.46],
    "skyline_color": [0.30, 0.31, 0.33],
    "avatar_shape": "Circle",
    "avatar_size": 1.0,
    "avatar_radius": 0,
    "avatar_border_color": [1.0, 1.0, 1.0],
    "avatar_border_size": 0,
    "audio_volume": 100,
}


def curated_template(row_count=None):
    """Return the packaged default look as a template settings dict.

    ``row_count`` caps "Items to show" to the dataset size so the preset
    stays honest on smaller tables.
    """
    settings = dict(_FALLBACK)
    path = app_paths.default_template_path()
    if path:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh).get("settings", {})
            if isinstance(loaded, dict) and loaded:
                settings = dict(loaded)
        except (OSError, ValueError):
            pass
    top_n = TOP_N
    if row_count is not None:
        top_n = max(1, min(TOP_N, int(row_count)))
    settings["top_n"] = top_n
    return settings
