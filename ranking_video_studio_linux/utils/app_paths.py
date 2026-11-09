"""Runtime path resolution for source runs and frozen (PyInstaller) builds.

A onefile build extracts to a temporary, read-only ``_MEIPASS`` folder that is
discarded on exit, so user data must live in a writable per-user directory and
bundled resources (FFmpeg, icons) are read from the bundle directory.

This is the Linux build: per-user data follows the XDG Base Directory spec
(``$XDG_DATA_HOME``, normally ``~/.local/share``) instead of ``%APPDATA%``.
"""
import os
import shutil
import sys

APP_DIRNAME = "LRBar-RankGen"


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def bundle_dir():
    """Read-only directory holding bundled resources."""
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(name):
    return os.path.join(bundle_dir(), name)


LOGO_FILE = os.path.join("assets", "app-icon.ico")


def logo_path():
    """Best available app-logo image for source runs and frozen builds.

    Linux prefers PNG; the master ``.ico`` is kept only as a fallback source
    for the build script that regenerates the PNG icon set.
    """
    candidates = (
        resource_path(os.path.join("icons", "lrbar-rankgen.png")),
        resource_path("app_icon.png"),
        resource_path(LOGO_FILE),
        resource_path("app_icon.ico"),
        os.path.join(bundle_dir(), "packaging", "app_icon.png"),
    )
    for path in candidates:
        if os.path.isfile(path):
            return path
    return ""


def _xdg_home(env_name, fallback):
    return os.environ.get(env_name) or os.path.expanduser(fallback)


def user_data_dir():
    """Writable directory for projects, templates and the license state.

    Frozen (installed) builds use ``$XDG_DATA_HOME/LRBar-RankGen``; source
    runs keep data next to the code so development stays self-contained.
    """
    if is_frozen():
        path = os.path.join(_xdg_home("XDG_DATA_HOME", "~/.local/share"),
                            APP_DIRNAME)
    else:
        path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(path, exist_ok=True)
    return path


def config_dir():
    """Per-user config directory used for the sealed license mirror.

    Kept separate from :func:`user_data_dir` so deleting the data folder (or
    the visible ``license.json``) does not reset a 1-Day quota.
    """
    return os.path.join(_xdg_home("XDG_CONFIG_HOME", "~/.config"), APP_DIRNAME)


def ffmpeg_path():
    """Prefer the bundled static ffmpeg, then fall back to the system PATH."""
    bundled = os.path.join(bundle_dir(), "ffmpeg")
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
