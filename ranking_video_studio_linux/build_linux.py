"""Reproducible build for the shippable Linux LRBar-RankGen binary.

Run this **on Linux** with the project virtualenv::

    python build_linux.py

It stages a static/compatible FFmpeg binary and the first-run seed content,
then runs PyInstaller from ``LRBar-RankGen.spec``. PyInstaller cannot
cross-compile, so a Windows or macOS host cannot produce this artifact.
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.join(HERE, "packaging")
APP_NAME = "LRBar-RankGen"


def _require_linux():
    if not sys.platform.startswith("linux"):
        raise SystemExit(
            "This build must run on Linux (PyInstaller cannot cross-compile).\n"
            "Use the matching Windows folder for the Windows build.")


def stage_ffmpeg(out_dir):
    """Bundle a real ffmpeg binary with the encoders the exporter needs."""
    src = shutil.which("ffmpeg")
    if not src:
        raise SystemExit(
            "FFmpeg not found on PATH. Install it (for example "
            "'sudo apt install ffmpeg') or point PATH at a static build.")
    encoders = subprocess.run(
        [src, "-hide_banner", "-encoders"], capture_output=True, text=True,
        check=False)
    if "libx264" not in (encoders.stdout + encoders.stderr):
        raise SystemExit(
            "The ffmpeg on PATH has no libx264 encoder; video export would "
            "fail. Install an ffmpeg build with H.264 support.")
    dst = os.path.join(out_dir, "ffmpeg")
    if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
        shutil.copy2(src, dst)
    os.chmod(dst, 0o755)
    return dst


def stage_seed(out_dir):
    """Bundle templates, sample logos and a portable sample dataset."""
    from data.demo_data import SAMPLE_ROWS

    seed = os.path.join(out_dir, "seed")
    os.makedirs(seed, exist_ok=True)

    # Factory templates are checked in under seed/ so a fresh clone builds a
    # usable installer even when the developer has no user templates yet.
    tpl_dst = os.path.join(seed, "templates")
    os.makedirs(tpl_dst, exist_ok=True)
    for base in (os.path.join(HERE, "seed", "templates"),
                 os.path.join(HERE, "templates")):
        if not os.path.isdir(base):
            continue
        for fn in os.listdir(base):
            if fn.endswith(".json"):
                shutil.copy2(os.path.join(base, fn),
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


def main():
    _require_linux()
    os.makedirs(PACK, exist_ok=True)
    stage_ffmpeg(PACK)
    stage_seed(PACK)
    print("Prepared bundled FFmpeg and sample seed in", PACK)

    import PyInstaller.__main__ as pyi
    pyi.run([
        os.path.join(HERE, "LRBar-RankGen.spec"),
        "--noconfirm", "--clean",
        "--distpath", os.path.join(HERE, "dist"),
        "--workpath", os.path.join(HERE, "build"),
    ])

    binary = os.path.join(HERE, "dist", APP_NAME)
    if not os.path.isfile(binary):
        raise SystemExit("PyInstaller finished but dist/LRBar-RankGen is missing")
    os.chmod(binary, 0o755)
    print("Built dist/LRBar-RankGen")
    print("Install it for the current user with:  bash linux/install.sh")
    print("Self-test it headlessly with:           ./dist/LRBar-RankGen --selftest")


if __name__ == "__main__":
    sys.exit(main())
