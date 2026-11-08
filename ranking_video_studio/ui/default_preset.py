"""The recommended startup look: a short-form ranking video built to hook.

The choices here are deliberate and aimed at retention rather than at being
neutral defaults:

* **Curiosity-gap title** -- "WHO TAKES #1?" opens a question the video
  answers last, which is the classic reason to keep watching.
* **Centered, large title** -- reads instantly on a phone and frames the
  skyline below it.
* **Tight cinematic camera** -- towers fill the frame instead of floating in
  empty space, and the #1 tower stays the hero at the end.
* **Gold rank badges on a deep navy sky** -- the warm accent against cool
  blue is the strongest contrast pair available, so rank numbers pop.
* **Dark red values on cream towers** -- readable at a glance without
  competing with the names.
* **Larger world-unit typography** -- names, values and subtitles stay
  legible after downscaling to a phone feed.
* **9:16 / 1080x1920 / 30 fps / CRF 18** -- the upload preset short-form
  platforms actually want, with a small file and clean edges.

Values use the same keys as ``MainWindow.capture_template()`` so the window
can apply the preset with ``apply_template()``.  Only pre-existing user
choices such as imported data, background image and music are left alone.
"""
from utils.config import TOP_N

#: Spacing between the top edge and the title, tuned so the title sits in the
#: empty sky band rather than over the skyline.
_TITLE = "WHO TAKES #1?"


def curated_template(row_count=None):
    """Return the recommended look as a template dict.

    ``row_count`` lets callers cap "Items to show" to the dataset size; the
    spinner clamps any value, but passing the count keeps the preset honest.
    """
    top_n = TOP_N
    if row_count is not None:
        top_n = max(1, min(TOP_N, int(row_count)))

    return {
        # -- pacing & output -------------------------------------------------
        "top_n": top_n,
        "aspect": "9:16 Vertical FHD (1080x1920)",
        "quality": "Ultra High (CRF 18)",
        "fps": "30",
        "preset": "fast",
        "low_resource": True,
        "speed": 1.0,
        "easing": "Smooth Deceleration (Cubic)",

        # -- hook title ------------------------------------------------------
        "title": _TITLE,
        "title_align": "Center",
        "title_size": 72,
        "title_color": [1.0, 1.0, 1.0],
        "title_margin": 74,

        # -- canvas ----------------------------------------------------------
        "bg_mode": "Sky Gradient",
        "bg_blur": 10,
        "bg_dim": 40,
        "shadow": True,

        # -- rank badges -----------------------------------------------------
        "show_badges": True,
        "badge_shape": "Pill",
        "badge_color": [1.0, 0.76, 0.16],
        "badge_size": 1.3,
        "rank_size": 40,
        "rank_color": [0.05, 0.05, 0.10],

        # -- tower typography ------------------------------------------------
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

        # -- camera ----------------------------------------------------------
        "cam_elev": 33,     # 3.3 world units above the tracked tower top
        "cam_dist": 195,    # 19.5 back: close enough to fill the frame
        "cam_side": 24,     # 2.4 lateral: a clear down-the-row recession
        "cam_ahead": 16,    # 1.6 look-ahead keeps incoming tops framed
        "cam_focus": 5,     # 0.5 above the top frames logo and badge
        "fov": 114,         # slightly wide for a cinematic, close feel
        "tower_color": [0.84, 0.79, 0.65],
        "plate_color": [0.16, 0.13, 0.16],
        "sky_top": [0.10, 0.22, 0.45],
        "sky_bottom": [0.72, 0.85, 0.95],
        "ground_color": [0.44, 0.44, 0.46],
        "skyline_color": [0.30, 0.31, 0.33],

        # -- avatars & audio -------------------------------------------------
        "avatar_shape": "Circle",
        "avatar_size": 1.0,
        "avatar_radius": 0,
        "avatar_border_color": [1.0, 1.0, 1.0],
        "avatar_border_size": 0,
        "audio_volume": 100,
    }
