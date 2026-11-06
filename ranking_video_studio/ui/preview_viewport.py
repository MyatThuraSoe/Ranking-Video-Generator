from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QSizePolicy


class PreviewViewport(QLabel):
    """Displays the rendered frame scaled to fit, preserving aspect ratio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 320)
        self._image = None
        self.setText("Preview")
        self.setStyleSheet("background-color: #14141f; border-radius: 8px;")

    def set_frame(self, qimage: QImage):
        self._image = qimage
        self._rescale()

    def clear_frame(self):
        self._image = None
        self.setPixmap(QPixmap())
        self.setText("Preview")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self):
        if self._image is None:
            return
        pix = QPixmap.fromImage(self._image)
        scaled = pix.scaled(self.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
        self.setPixmap(scaled)
