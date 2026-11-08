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


def process_tower_bar_image(path, size):
    """Load an image to stand in for the tower/bar body itself (no crop).

    Downscaled once to keep the render loop cheap; stretched to each bar's
    width/height at draw time. Returns a Cairo surface or None on failure.
    """
    try:
        img = Image.open(path).convert("RGBA")
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        return _surface_from_pil(img)
    except Exception:
        return None


def process_avatar_image(path, size, shape, radius=0.0,
                         border_color=(1.0, 1.0, 1.0), border_size=0.0):
    """Center-crop to square, mask to shape, optionally ring it with a border.

    radius is corner rounding as a fraction of half-size (square/rounded);
    border_size is ring thickness as a fraction of half-size. Returns surface.
    """
    try:
        img = Image.open(path).convert("RGBA")
    except Exception:
        return None
    img = ImageOps.fit(img, (size, size), Image.Resampling.LANCZOS)

    if shape == "circle":
        r_px = size / 2.0
    else:
        frac = max(radius, 0.2) if shape == "rounded" else radius
        r_px = max(0.0, min(frac, 1.0)) * size * 0.5
    b_px = int(round(max(0.0, min(border_size, 0.45)) * size * 0.5))

    def shape_mask(inset, rad):
        m = Image.new("L", (size, size), 0)
        d = ImageDraw.Draw(m)
        box = [inset, inset, size - 1 - inset, size - 1 - inset]
        rad = max(0.0, min(rad, (size - 1 - 2 * inset) / 2.0))
        if shape == "circle":
            d.ellipse(box, fill=255)
        elif rad <= 0.5:
            d.rectangle(box, fill=255)
        else:
            d.rounded_rectangle(box, radius=int(rad), fill=255)
        return m

    outer = shape_mask(0, r_px)
    if b_px > 0:
        inner = shape_mask(b_px, r_px - b_px)
        ring = Image.new("RGBA", (size, size),
                         tuple(int(c * 255) for c in border_color) + (255,))
        ring.putalpha(outer)
        img.putalpha(inner)
        ring.alpha_composite(img)
        img = ring
    else:
        img.putalpha(outer)
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
