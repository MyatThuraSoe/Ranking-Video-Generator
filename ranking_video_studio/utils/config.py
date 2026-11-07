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

MAX_ROWS = 50
TOP_N = 10
MAX_DIMENSION = 2560


@dataclass
class RenderConfig:
    # format
    width: int = 1080
    height: int = 1920
    fps: int = 30
    duration: float = 8.0
    crf: int = 18
    encode_preset: str = "fast"

    # animation
    speed: float = 1.0
    easing: str = "cubic"

    # title / background
    title: str = "TOP RANKINGS"
    bg_mode: str = "gradient"  # solid | gradient | image
    bg_color: tuple = (0.07, 0.07, 0.14)
    bg_color2: tuple = (0.17, 0.10, 0.32)
    bg_image: str = ""
    bg_blur: int = 10
    bg_dim: int = 40

    # bars / tiles
    bar_color: tuple = (0.16, 0.47, 0.89)
    tile_image: str = ""
    tile_radius: int = 16
    tile_opacity: int = 100
    tint_enabled: bool = False
    tint_color: tuple = (0.2, 0.5, 1.0)
    shadow_enabled: bool = True

    # avatars
    avatar_shape: str = "circle"  # circle | rounded | square

    # badges
    show_badges: bool = True
    badge_shape: str = "pill"  # pill | circle | text
    badge_color: tuple = (1.0, 0.76, 0.16)
    rank_color: tuple = (0.05, 0.05, 0.10)
    rank_font_size: int = 28

    # audio
    audio_file: str = ""
    audio_volume: int = 100

    # ---- Incline 3D tower camera ----
    camera_mode: str = "flat"      # "flat" | "incline"
    camera_move: str = "pan"       # "pan" | "static" | "push" | "follow"
    cam_height: float = 3.5        # camera eye height
    cam_distance: float = 34.0     # distance behind row
    cam_side: float = 1.9          # lateral offset = incline angle
    cam_fov: float = 1.05          # focal multiplier
    cam_look_height: float = 2.0
    tower_color: tuple = (0.80, 0.76, 0.64)
    plate_color: tuple = (0.24, 0.13, 0.12)
    value_color: tuple = (0.48, 0.06, 0.10)
    sky_top: tuple = (0.29, 0.49, 0.71)
    sky_bottom: tuple = (0.74, 0.80, 0.84)
    skyline_image: str = ""
    value_prefix: str = "$ "
    value_suffix: str = " B"
    value_decimals: int = 1

    def scale(self):
        return max(0.6, min(self.width, self.height) / 1080.0)

    def asset_signature(self):
        """Fields that require rebuilding pre-rendered assets when changed."""
        return (
            self.width, self.height, self.bg_mode, self.bg_image,
            self.bg_blur, self.bg_dim, self.tile_image, self.tile_radius,
            self.tile_opacity, self.tint_enabled, self.tint_color,
            self.avatar_shape, self.camera_mode, self.skyline_image,
        )
