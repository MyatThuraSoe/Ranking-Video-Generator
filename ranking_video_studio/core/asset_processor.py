"""Pre-render image assets ONCE before the render loop (never per-frame)."""
import cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps


def _surface_from_pil(img):
    """Convert a PIL RGBA image to a Cairo ARGB32 surface.

    Cairo stores premultiplied alpha; PIL is straight alpha, so RGB must be
    premultiplied here or transparent pixels leak color when composited.
    """
    img = img.convert("RGBA")
    arr = np.asarray(img).astype(np.uint16)
    arr[..., :3] = arr[..., :3] * arr[..., 3:4] // 255
    img = Image.fromarray(arr.astype(np.uint8), "RGBA")
    w, h = img.size
    stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, w)
    raw = img.tobytes("raw", "BGRA")
    buf = bytearray(stride * h)
    if stride == w * 4:
        buf[:] = raw
    else:
        for y in range(h):
            buf[y * stride:(y + 1) * stride] = raw[y * w * 4:(y + 1) * w * 4]
    surface = cairo.ImageSurface.create_for_data(
        buf, cairo.FORMAT_ARGB32, w, h, stride)
    return surface


def _rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return mask


def process_background_image(path, w, h, blur, dim):
    """Load, fit, blur and dim a background image. Returns Cairo surface."""
    img = Image.open(path).convert("RGB")
    img = ImageOps.fit(img, (w, h), Image.Resampling.LANCZOS)
    if blur and blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur))
    if dim and dim > 0:
        overlay = Image.new("RGB", (w, h), (0, 0, 0))
        img = Image.blend(img, overlay, min(dim, 100) / 100.0)
    return _surface_from_pil(img)


def process_tile_image(path, bar_h, radius, opacity, tint_enabled, tint_color):
    """Prepare a custom tile PNG scaled to bar height.

    Returns (cairo_surface, (w, h)) or (None, (0, 0)) on failure.
    """
    try:
        img = Image.open(path).convert("RGBA")
    except Exception:
        return None, (0, 0)
    ratio = bar_h / max(1, img.height)
    tw = max(1, int(img.width * ratio))
    img = img.resize((tw, bar_h), Image.Resampling.LANCZOS)

    if radius > 0:
        img.putalpha(_rounded_mask((tw, bar_h), min(radius, bar_h // 2)))

    if tint_enabled:
        tint = Image.new("RGBA", (tw, bar_h),
                         (int(tint_color[0] * 255), int(tint_color[1] * 255),
                          int(tint_color[2] * 255), 90))
        img = Image.alpha_composite(img, tint)

    if opacity < 100:
        alpha = img.getchannel("A").point(lambda p: int(p * opacity / 100))
        img.putalpha(alpha)

    return _surface_from_pil(img), (tw, bar_h)


def process_avatar_image(path, size, shape):
    """Center-crop to square, apply shape mask. Returns surface or None."""
    try:
        img = Image.open(path).convert("RGBA")
    except Exception:
        return None
    img = ImageOps.fit(img, (size, size), Image.Resampling.LANCZOS)
    if shape == "circle":
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
        img.putalpha(mask)
    elif shape == "rounded":
        img.putalpha(_rounded_mask((size, size), max(2, size // 5)))
    return _surface_from_pil(img)


def pil_surface(img):
    """Public helper: PIL RGBA image -> premultiplied Cairo surface."""
    return _surface_from_pil(img)


def make_waving_flag(image_path, h_px):
    """Pre-warp a flag image into a waving sprite (once, before render loop)."""
    import math as _m
    img = Image.open(image_path).convert("RGBA")
    aspect = img.width / max(1, img.height)
    w_px = int(h_px * aspect * 1.4)
    img = img.resize((w_px, h_px), Image.Resampling.LANCZOS)

    amp = int(h_px * 0.14)
    out = Image.new("RGBA", (w_px, h_px + 2 * amp), (0, 0, 0, 0))
    for x in range(w_px):
        frac = x / max(1, w_px - 1)
        off = int(_m.sin(frac * _m.pi * 2.2) * amp * frac)   # wave grows to fly-end
        out.paste(img.crop((x, 0, x + 1, h_px)), (x, amp + off))
    return _surface_from_pil(out)
