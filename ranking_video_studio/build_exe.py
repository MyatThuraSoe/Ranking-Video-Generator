"""Reproducible build for the shippable LRBar-RankGen.exe.

Prepares a branded icon, Windows version metadata and the bundled FFmpeg
encoder, then runs PyInstaller from LRBar-RankGen.spec. Run with the project
virtualenv:  python build_exe.py
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.join(HERE, "packaging")
MASTER_LOGO = os.path.join(HERE, "LRBar RankGen_ Ranking Video Magic.ico")


def _icon_from_master(master, out_dir):
    """Use the user-supplied logo as the single source of branding truth."""
    from PIL import Image
    img = Image.open(master)
    img.size = (256, 256)
    img.convert("RGBA").save(os.path.join(out_dir, "app_icon.png"), "PNG")
    shutil.copy2(master, os.path.join(out_dir, "app_icon.ico"))


def make_icon(out_dir):
    if os.path.isfile(MASTER_LOGO):
        _icon_from_master(MASTER_LOGO, out_dir)
        return
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    size = 1024
    top = np.array([9, 20, 45], dtype=float)
    bottom = np.array([28, 78, 162], dtype=float)
    ramp = np.linspace(0.0, 1.0, size)[:, None, None]
    grad = top[None, None, :] * (1 - ramp) + bottom[None, None, :] * ramp
    bg = Image.fromarray(np.repeat(grad, size, axis=1).astype("uint8"), "RGB").convert("RGBA")

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([24, 24, size - 24, size - 24], radius=228, fill=255)
    bg.putalpha(mask)

    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([120, 60, 720, 560], fill=(120, 200, 255, 70))
    bg = Image.alpha_composite(bg, glow.filter(ImageFilter.GaussianBlur(120)))

    bar_w, gap, base = 148, 54, 800
    x0 = (size - (3 * bar_w + 2 * gap)) // 2
    heights = [236, 360, 498]
    bars = [(x0 + i * (bar_w + gap), base - h, x0 + i * (bar_w + gap) + bar_w, base)
            for i, h in enumerate(heights)]

    bars_mask = Image.new("L", (size, size), 0)
    bd = ImageDraw.Draw(bars_mask)
    for box in bars:
        bd.rounded_rectangle(box, radius=30, fill=255)

    c_top = np.array([125, 235, 252], dtype=float)
    c_bot = np.array([37, 99, 235], dtype=float)
    bgrad = c_top[None, None, :] * (1 - ramp) + c_bot[None, None, :] * ramp
    bars_img = Image.fromarray(np.repeat(bgrad, size, axis=1).astype("uint8"), "RGB").convert("RGBA")

    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([x0 - 10, base - 6, x0 + 3 * bar_w + 2 * gap + 10, base + 26],
                                             radius=20, fill=(0, 0, 0, 90))
    bg = Image.alpha_composite(bg, shadow.filter(ImageFilter.GaussianBlur(14)))
    bg.paste(bars_img, (0, 0), bars_mask)

    gloss = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gloss)
    for (x1, y1, x2, y2) in bars:
        gd.rounded_rectangle([x1 + 14, y1 + 14, x1 + int(bar_w * 0.42), y2 - 16],
                             radius=20, fill=(255, 255, 255, 55))
    bg = Image.alpha_composite(bg, gloss)

    accent = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ad = ImageDraw.Draw(accent)
    cx, cy, r = bars[2][2] - 6, bars[2][1] - 78, 66
    pts = []
    for k in range(8):
        ang = k * 3.14159265 / 4
        rad = r if k % 2 == 0 else r * 0.36
        pts.append((cx + rad * np.sin(ang), cy - rad * np.cos(ang)))
    ad.polygon(pts, fill=(251, 191, 36, 255))
    bg = Image.alpha_composite(bg, accent)
    bg = Image.alpha_composite(bg, accent.filter(ImageFilter.GaussianBlur(26)))

    edge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle([24, 24, size - 24, size - 24], radius=228,
                                           outline=(150, 205, 255, 90), width=6)
    bg = Image.alpha_composite(bg, edge)

    bg.save(os.path.join(out_dir, "app_icon.png"), "PNG")
    bg.save(os.path.join(out_dir, "app_icon.ico"), format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def write_version_info(out_dir):
    text = """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0), prodvers=(1, 0, 0, 0), mask=0x3f, flags=0x0,
    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'LRBar'),
      StringStruct('FileDescription', 'LRBar-RankGen - Animated Ranking Video Generator'),
      StringStruct('FileVersion', '1.0.0'),
      StringStruct('InternalName', 'LRBar-RankGen'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 LRBar'),
      StringStruct('OriginalFilename', 'LRBar-RankGen.exe'),
      StringStruct('ProductName', 'LRBar-RankGen'),
      StringStruct('ProductVersion', '1.0.0')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    with open(os.path.join(out_dir, "version_info.txt"), "w", encoding="utf-8") as fh:
        fh.write(text)


def write_setup_version_info(out_dir):
    text = """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0), prodvers=(1, 0, 0, 0), mask=0x3f, flags=0x0,
    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'LRBar'),
      StringStruct('FileDescription', 'LRBar-RankGen Setup'),
      StringStruct('FileVersion', '1.0.0'),
      StringStruct('InternalName', 'LRBar-RankGen-Setup'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 LRBar'),
      StringStruct('OriginalFilename', 'LRBar-RankGen-Setup.exe'),
      StringStruct('ProductName', 'LRBar-RankGen'),
      StringStruct('ProductVersion', '1.0.0')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    with open(os.path.join(out_dir, "setup_version_info.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(text)


def stage_ffmpeg(out_dir):
    src = shutil.which("ffmpeg")
    if not src:
        raise SystemExit("FFmpeg not found on PATH; install it before building.")
    dst = os.path.join(out_dir, "ffmpeg.exe")
    if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
        shutil.copy2(src, dst)
    return dst


def stage_seed(out_dir):
    """Bundle the current templates, sample logos and a portable sample dataset.

    Image paths in sample_data.json are bare filenames so first-run seeding can
    resolve them against the installed sample_assets folder on any machine.
    """
    from data.demo_data import SAMPLE_ROWS

    seed = os.path.join(out_dir, "seed")
    tpl_src = os.path.join(HERE, "templates")
    tpl_dst = os.path.join(seed, "templates")
    os.makedirs(tpl_dst, exist_ok=True)
    if os.path.isdir(tpl_src):
        for fn in os.listdir(tpl_src):
            if fn.endswith(".json"):
                shutil.copy2(os.path.join(tpl_src, fn),
                             os.path.join(tpl_dst, fn))

    assets_src = os.path.join(HERE, "sample_assets")
    assets_dst = os.path.join(seed, "sample_assets")
    os.makedirs(assets_dst, exist_ok=True)
    if os.path.isdir(assets_src):
        for fn in os.listdir(assets_src):
            if os.path.isfile(os.path.join(assets_src, fn)):
                shutil.copy2(os.path.join(assets_src, fn),
                             os.path.join(assets_dst, fn))

    records = [{"name": n, "score": str(s), "text": t, "image": f,
                "extratext": ""} for n, s, t, f in SAMPLE_ROWS]
    with open(os.path.join(seed, "sample_data.json"), "w",
              encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=1)
    return seed


def build_installer():
    """Package the shippable exe into the branded per-user setup wizard."""
    import PyInstaller.__main__ as pyi
    pyi.run([
        os.path.join(HERE, "installer", "LRBar-RankGen-Setup.spec"),
        "--noconfirm",
        "--distpath", os.path.join(HERE, "dist"),
        "--workpath", os.path.join(HERE, "build"),
    ])


def main():
    os.makedirs(PACK, exist_ok=True)
    make_icon(PACK)
    write_version_info(PACK)
    write_setup_version_info(PACK)
    stage_ffmpeg(PACK)
    stage_seed(PACK)
    print("Prepared icon, version info, bundled FFmpeg and sample seed in", PACK)
    import PyInstaller.__main__ as pyi
    pyi.run([
        os.path.join(HERE, "LRBar-RankGen.spec"),
        "--noconfirm", "--clean",
        "--distpath", os.path.join(HERE, "dist"),
        "--workpath", os.path.join(HERE, "build"),
    ])
    build_installer()
    print("Built dist/LRBar-RankGen.exe and dist/LRBar-RankGen-Setup.exe")


if __name__ == "__main__":
    sys.exit(main())