import os
import shutil

from utils.app_paths import ffmpeg_path


def ffmpeg_available():
    path = ffmpeg_path()
    return os.path.isfile(path) or shutil.which("ffmpeg") is not None