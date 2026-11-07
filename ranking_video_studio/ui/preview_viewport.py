"""Preview surface: a rounded, softly shadowed video frame canvas."""
from PyQt6.QtCore import QRectF, QSizeF, Qt
from PyQt6.QtGui import (
    QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
)
from PyQt6.QtWidgets import QSizePolicy, QWidget

from ui import styles


class PreviewViewport(QWidget):
    """Displays the rendered frame scaled to fit, preserving aspect ratio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("previewViewport")
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 320)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self._image = None
        self._placeholder = "Your preview will appear here"

    def set_frame(self, qimage: QImage):
        self._image = qimage
        self.update()

    def clear_frame(self):
        self._image = None
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        pal = styles.current_palette()

        outer = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        shell = QPainterPath()
        shell.addRoundedRect(outer, 12, 12)

        grad = QLinearGradient(outer.topLeft(), outer.bottomRight())
        grad.setColorAt(0.0, QColor(pal["preview_bg"]))
        grad.setColorAt(1.0, QColor(pal["bg"]))
        painter.fillPath(shell, QBrush(grad))

        if self._image is not None and not self._image.isNull():
            avail = self.rect().adjusted(16, 16, -16, -16)
            target = QRectF(self._image.rect())
            target.setSize(QSizeF(self._image.size().scaled(
                avail.size(), Qt.AspectRatioMode.KeepAspectRatio)))
            target.moveCenter(QRectF(avail).center())

            # Floating shadow beneath the video frame.
            shadow = QRectF(target).translated(0, 6)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 80))
            painter.drawRoundedRect(shadow, 6, 6)

            scaled = self._image.scaled(
                target.size().toSize(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)

            painter.save()
            clip = QPainterPath()
            clip.addRoundedRect(target, 5, 5)
            painter.setClipPath(clip)
            painter.drawImage(target.topLeft(), scaled)
            painter.restore()

            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(pal["border_input"]), 1))
            painter.drawRoundedRect(target, 5, 5)
        else:
            font = painter.font()
            font.setPointSize(11)
            painter.setFont(font)
            painter.setPen(QColor(pal["dim"]))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             self._placeholder)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(pal["border"]), 1))
        painter.drawPath(shell)
