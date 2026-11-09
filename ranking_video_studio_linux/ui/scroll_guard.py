"""Stop the mouse wheel from silently editing hovered value controls.

Wheeling over a combo box, spin box or slider should scroll the surrounding
panel, never change a setting by accident. The guard consumes the wheel on
those controls and forwards the scroll to the nearest scrollable ancestor.
"""
from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import (
    QAbstractScrollArea, QAbstractSpinBox, QComboBox, QSlider,
)

_GUARDED = (QComboBox, QAbstractSpinBox, QSlider)


class _WheelGuard(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and isinstance(obj, _GUARDED):
            bar = None
            node = obj.parentWidget()
            while node is not None:
                if isinstance(node, QAbstractScrollArea):
                    bar = node.verticalScrollBar()
                    break
                node = node.parentWidget()
            if bar is not None:
                notches = event.angleDelta().y() / 120.0
                bar.setValue(bar.value() - int(notches * bar.singleStep() * 3))
            event.accept()
            return True
        return False


def install(app):
    guard = _WheelGuard(app)
    app.installEventFilter(guard)
    return guard