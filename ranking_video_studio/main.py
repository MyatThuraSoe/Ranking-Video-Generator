import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMessageBox

from ui.main_window import MainWindow
from ui.styles import DARK_QSS
from utils.ffmpeg_check import ffmpeg_available


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Ranking Video Studio")
    app.setStyleSheet(DARK_QSS)

    window = MainWindow()
    if not ffmpeg_available():
        QMessageBox.warning(
            window, "FFmpeg not found",
            "FFmpeg was not detected on your system PATH.\n"
            "Live preview works, but video export is disabled.\n"
            "Install FFmpeg 5.x/6.x and restart the app.")
        window.set_export_enabled(False)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
