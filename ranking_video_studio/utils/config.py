from dataclasses import dataclass, field

RESOLUTIONS = {
    "9:16 Vertical 2K (1440x2560)": (1440, 2560),
    "16:9 Landscape 2K (2560x1440)": (2560, 1440),
    "9:16 Vertical FHD (1080x1920)": (1080, 1920),
    "16:9 Landscape FHD (1920x1080)": (1920, 1080),
    "1:1 Square 2K (1440x1440)": (1440, 1440),
    "4:5 Portrait (1080x1350)": (1080, 1350),
}

QUALITY_PRESETS = {
    "Near Lossless (CRF 15)": 15,
    "Ultra High (CRF 18)": 18,
    "Balanced Web (CRF 23)": 23,
}

ENCODE_PRESETS = ["ultrafast", "fast", "medium", "slow"]
FPS_OPTIONS = [24, 30, 60]

MAX_ROWS = 100
TOP_N = 10
MAX_DIMENSION = 2560
BASE_DURATION = 8.0   # video seconds at 1.0x camera speed; duration = BASE / speed


@dataclass
class RenderConfig:
    # format
    width: int = 1080
    height: int = 1920
    fps: int = 30
    duration: float = 8.0
    crf: int = 18
    encode_preset: str = "fast"
    low_resource: bool = True   # Eco: limit FFmpeg to 2 threads (0% GPU, quiet PC)

    # animation
    speed: float = 1.0
    easing: str = "cubic"
    top_n: int = 10            # how many ranked items to render (defaults to dataset size)

    # title / background
    title: str = "TOP RANKINGS"
    title_align: str = "left"    # left | center | right
    title_font_size: int = 40    # px (scaled)
    title_color: tuple = (1.0, 1.0, 1.0)
    title_top_margin: int = 24   # px from top edge to text top (scaled)
    bg_mode: str = "sky"         # sky | image
    bg_image: str = ""
    bg_blur: int = 10
    bg_dim: int = 40

    shadow_enabled: bool = True

    # avatars
    avatar_shape: str = "circle"  # circle | rounded | square
    avatar_size: float = 1.0      # scale of the image sprite on the tower
    avatar_border_radius: float = 0.0  # 0..1 corner rounding (square/rounded)
    avatar_border_color: tuple = (1.0, 1.0, 1.0)
    avatar_border_size: float = 0.0    # 0..0.45 border thickness (frac of half)

    # badges
    show_badges: bool = True
    badge_shape: str = "pill"  # pill | circle | text
    badge_color: tuple = (1.0, 0.76, 0.16)
    badge_size: float = 1.0   # scale of the badge background shape
    rank_color: tuple = (0.05, 0.05, 0.10)
    rank_font_size: int = 28

    # typography (per-element font size in world units + RGB color)
    name_font_size: float = 0.34
    name_color: tuple = (1.0, 1.0, 1.0)
    value_font_size: float = 0.30
    text_font_size: float = 0.20
    text_color: tuple = (0.85, 0.85, 0.88)
    extra_font_size: float = 0.18
    extra_color: tuple = (0.80, 0.82, 0.85)

    # audio
    audio_file: str = ""
    audio_volume: int = 100

    # ---- Incline 3D tower camera ----
    cam_elevation: float = 3.5     # camera height ABOVE the tracked tower top
    cam_distance: float = 26.0     # distance behind row
    cam_side: float = 1.9          # lateral offset = incline angle
    cam_fov: float = 1.05          # focal multiplier
    cam_look_ahead: float = 1.2    # aim this far along the row (recession dir)
    cam_focus_offset: float = 0.5  # look-at height above tower top (frames logos)
    tower_color: tuple = (0.80, 0.76, 0.64)
    plate_color: tuple = (0.24, 0.13, 0.12)
    value_color: tuple = (0.48, 0.06, 0.10)
    sky_top: tuple = (0.29, 0.49, 0.71)
    sky_bottom: tuple = (0.74, 0.80, 0.84)
    value_prefix: str = "$ "
    value_suffix: str = " B"
    value_decimals: int = 1

    def scale(self):
        return max(0.6, min(self.width, self.height) / 1080.0)

    def asset_signature(self):
        """Fields that require rebuilding pre-rendered assets when changed."""
        return (
            self.width, self.height, self.bg_mode, self.bg_image,
            self.bg_blur, self.bg_dim, self.avatar_shape,
            self.avatar_border_radius, self.avatar_border_color,
            self.avatar_border_size,
            self.top_n,
        )
