DARK_QSS = """
QMainWindow, QWidget { background-color: #1e1e2e; color: #ffffff; }
QGroupBox {
    background-color: #2a2a3a;
    border: 1px solid #3a3a4e;
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #9ecbff;
}
QLabel { color: #e6e6f0; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #232334;
    border: 1px solid #44445c;
    border-radius: 6px;
    padding: 5px 8px;
    color: #ffffff;
    selection-background-color: #2b78e4;
}
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background-color: #232334; color: #ffffff;
    border: 1px solid #44445c; selection-background-color: #2b78e4;
}
QPushButton {
    background-color: #34344a;
    border: 1px solid #4a4a66;
    border-radius: 6px;
    padding: 7px 12px;
    color: #ffffff;
}
QPushButton:hover { background-color: #3e3e58; }
QPushButton:disabled { color: #777788; background-color: #2a2a3a; }
QPushButton#exportBtn {
    background-color: #0b8043; border: none;
    font-size: 15px; font-weight: bold; padding: 11px;
}
QPushButton#exportBtn:hover { background-color: #0d9950; }
QPushButton#exportBtn:disabled { background-color: #2a2a3a; color: #777788; }
QPushButton#playBtn { background-color: #2b78e4; border: none; font-weight: bold; }
QPushButton#playBtn:hover { background-color: #3d89f0; }
QSlider::groove:horizontal {
    height: 6px; background: #3a3a4e; border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #2b78e4; width: 16px; height: 16px;
    margin: -6px 0; border-radius: 8px;
}
QProgressBar {
    background-color: #232334; border: 1px solid #44445c;
    border-radius: 6px; text-align: center; color: #ffffff; height: 18px;
}
QProgressBar::chunk { background-color: #0b8043; border-radius: 5px; }
QScrollArea { border: none; }
QCheckBox, QRadioButton { spacing: 8px; }
QCheckBox::indicator, QRadioButton::indicator { width: 16px; height: 16px; }
QCheckBox::indicator:unchecked {
    border: 1px solid #666680; border-radius: 4px; background: #232334;
}
QCheckBox::indicator:checked {
    border: 1px solid #2b78e4; border-radius: 4px; background: #2b78e4;
}
QToolTip { background-color: #232334; color: #ffffff; border: 1px solid #44445c; }
"""
