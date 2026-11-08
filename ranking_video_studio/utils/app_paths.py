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


LOGO_FILE = "LRBar RankGen_ Ranking Video Magic.ico"


def logo_path():
    """Best available app-logo image for source runs and frozen builds.

    Frozen builds bundle a PNG derived from the master .ico at the bundle
    root; source runs fall back to the master .ico itself.
    """
    candidates = (
        resource_path("app_icon.png"),
        os.path.join(bundle_dir(), LOGO_FILE),
        resource_path("app_icon.ico"),
        os.path.join(bundle_dir(), "packaging", "app_icon.png"),
    )
    for path in candidates:
        if os.path.isfile(path):
            return path
    return ""


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


DEFAULT_TEMPLATE = "Sample Template 1"


def default_template_path():
    """The packaged factory-default template shipped in the build seed."""
    for base in (os.path.join(bundle_dir(), "seed", "templates"),
                 os.path.join(bundle_dir(), "packaging", "seed", "templates")):
        path = os.path.join(base, DEFAULT_TEMPLATE + ".json")
        if os.path.isfile(path):
            return path
    return ""


def sample_assets_dir():
    """Folder holding the bundled sample logo images.

    Prefer the writable seeded copy, then the frozen bundle's seed, then the
    source tree's sample_assets. Returns "" when none is present.
    """
    writable = os.path.join(user_data_dir(), "sample_assets")
    if os.path.isdir(writable):
        return writable
    for candidate in (os.path.join(bundle_dir(), "seed", "sample_assets"),
                      os.path.join(bundle_dir(), "sample_assets")):
        if os.path.isdir(candidate):
            return candidate
    return ""