"""Runtime path resolution for source runs and frozen (PyInstaller) builds.

A onefile build extracts to a temporary, read-only ``_MEIPASS`` folder that is
discarded on exit, so user data must live in a writable per-user directory and
bundled resources (FFmpeg, icons) are read from the bundle directory.
"""
import os
import shutil
import sys


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def bundle_dir():
    """Read-only directory holding bundled resources."""
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(name):
    return os.path.join(bundle_dir(), name)


def user_data_dir():
    """Writable directory for projects, templates and settings."""
    if is_frozen():
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = os.path.join(base, "LRBar-RankGen")
    else:
        path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(path, exist_ok=True)
    return path


def ffmpeg_path():
    """Prefer the bundled ffmpeg.exe, then fall back to the system PATH."""
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    bundled = os.path.join(bundle_dir(), name)
    if os.path.isfile(bundled):
        return bundled
    return shutil.which("ffmpeg") or "ffmpeg"