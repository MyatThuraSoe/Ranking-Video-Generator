"""Palette-driven application themes: Dark, Bright, Blue, Green."""
from string import Template

THEME_NAMES = ["Dark", "Bright", "Blue", "Green"]

THEMES = {
    "Dark": dict(
        bg="#1e1e2e", surface="#2a2a3a", surface2="#232334",
        border="#3a3a4e", border_input="#44445c",
        text="#ffffff", text_soft="#e6e6f0", dim="#8888a0",
        accent="#2b78e4", accent_hover="#3d89f0", accent_text="#ffffff",
        title="#9ecbff", selection="#2b5a9e", sel_text="#ffffff",
        ok="#0b8043", ok_hover="#0d9950", ok_text="#8fd18f",
        err_text="#ff8f8f", danger="#7e2f3a", danger_hover="#963846",
        warn="#e8c15a", chip_bg="#23304a", chip_warn_bg="#3a3423",
        head_bg="#2f2f44", grid="#33334a", alt_row="#262638",
        scroll_thumb="#4a4a66", preview_bg="#14141f",
        disabled_text="#777788", menu_bg="#232334",
    ),
    "Bright": dict(
        bg="#eef0f4", surface="#ffffff", surface2="#f7f8fa",
        border="#d5d9e2", border_input="#c3c9d6",
        text="#1f2430", text_soft="#2a3040", dim="#6b7280",
        accent="#2563eb", accent_hover="#1d4ed8", accent_text="#ffffff",
        title="#1d4ed8", selection="#bfdbfe", sel_text="#1f2430",
        ok="#15803d", ok_hover="#166534", ok_text="#15803d",
        err_text="#b91c1c", danger="#b91c1c", danger_hover="#991b1b",
        warn="#b45309", chip_bg="#e0e7ff", chip_warn_bg="#fef3c7",
        head_bg="#e8ebf1", grid="#e3e6ec", alt_row="#f2f4f8",
        scroll_thumb="#c3c8d4", preview_bg="#dfe3ea",
        disabled_text="#9ca3af", menu_bg="#ffffff",
    ),
    "Blue": dict(
        bg="#0b1526", surface="#12233c", surface2="#0e1b30",
        border="#23405f", border_input="#2c4a6e",
        text="#e6f0fa", text_soft="#dceaf7", dim="#8aa2bd",
        accent="#38bdf8", accent_hover="#67d3fb", accent_text="#062033",
        title="#7dd3fc", selection="#1d4ed8", sel_text="#ffffff",
        ok="#059669", ok_hover="#10b981", ok_text="#34d399",
        err_text="#f87171", danger="#9f3548", danger_hover="#b8455c",
        warn="#fbbf24", chip_bg="#12365c", chip_warn_bg="#3c3315",
        head_bg="#16304e", grid="#1c3552", alt_row="#102036",
        scroll_thumb="#2c4a6e", preview_bg="#0a1220",
        disabled_text="#5f7893", menu_bg="#0e1b30",
    ),
    "Green": dict(
        bg="#0c1a12", surface="#14291c", surface2="#102117",
        border="#29543a", border_input="#336448",
        text="#e8f5ec", text_soft="#dff0e4", dim="#93b39d",
        accent="#4ade80", accent_hover="#6ee7a0", accent_text="#06281a",
        title="#86efac", selection="#166534", sel_text="#ffffff",
        ok="#16a34a", ok_hover="#22c55e", ok_text="#4ade80",
        err_text="#f87171", danger="#9f3548", danger_hover="#b8455c",
        warn="#fbbf24", chip_bg="#143626", chip_warn_bg="#3c3315",
        head_bg="#1a3626", grid="#20402c", alt_row="#12251a",
        scroll_thumb="#336448", preview_bg="#0a150e",
        disabled_text="#6d8a77", menu_bg="#102117",
    ),
}

_QSS_TEMPLATE = Template("""
QMainWindow, QWidget { background-color: $bg; color: $text; }
QMenuBar {
    background-color: $surface; color: $text_soft;
    border-bottom: 1px solid $border; padding: 2px 6px;
}
QMenuBar::item {
    background: transparent; padding: 5px 12px; border-radius: 5px;
}
QMenuBar::item:selected { background-color: $accent; color: $accent_text; }
QMenuBar::item:pressed { background-color: $accent_hover; color: $accent_text; }
QMenu {
    background-color: $menu_bg; color: $text_soft;
    border: 1px solid $border_input; border-radius: 6px; padding: 5px;
}
QMenu::item { padding: 6px 26px 6px 14px; border-radius: 5px; }
QMenu::item:selected { background-color: $accent; color: $accent_text; }
QMenu::item:disabled { color: $disabled_text; }
QMenu::separator { height: 1px; background: $border; margin: 5px 8px; }
QMenu::indicator { width: 14px; height: 14px; margin-left: 6px; }
QMenu::indicator:checked {
    background-color: $accent; border: 1px solid $accent_hover; border-radius: 4px;
}
QMenu::indicator:unchecked {
    background-color: $surface2; border: 1px solid $border_input; border-radius: 4px;
}
QGroupBox {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: $title;
}
QLabel { color: $text_soft; }
QLabel#countLabel { color: $title; font-weight: bold; }
QLabel#hintLabel { color: $dim; }
QLabel#statusLabel[error="false"] { color: $ok_text; }
QLabel#statusLabel[error="true"] { color: $err_text; }
QLabel#projectChip[saved="true"] {
    color: $title; background-color: $chip_bg;
    border: 1px solid $accent; border-radius: 10px; padding: 3px 10px;
}
QLabel#projectChip[saved="false"] {
    color: $warn; background-color: $chip_warn_bg;
    border: 1px solid $warn; border-radius: 10px; padding: 3px 10px;
}
QLabel#thumbLabel {
    border: 1px solid $border_input; border-radius: 5px;
    background-color: $surface2; color: $dim;
}
QLabel#cellName { color: $text_soft; border: none; }
QLabel#cellName[empty="true"] { color: $dim; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: $surface2;
    border: 1px solid $border_input;
    border-radius: 6px;
    padding: 5px 8px;
    color: $text;
    selection-background-color: $accent;
    selection-color: $accent_text;
}
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background-color: $surface2; color: $text;
    border: 1px solid $border_input; selection-background-color: $accent;
    selection-color: $accent_text;
}
QPushButton {
    background-color: $surface;
    border: 1px solid $border_input;
    border-radius: 6px;
    padding: 7px 12px;
    color: $text;
}
QPushButton:hover { background-color: $head_bg; }
QPushButton:disabled { color: $disabled_text; background-color: $surface2; }
QPushButton#colorBtn { border: 1px solid $border_input; border-radius: 6px; }
QPushButton#exportBtn {
    background-color: $ok; border: none; color: #ffffff;
    font-size: 15px; font-weight: bold; padding: 11px;
}
QPushButton#exportBtn:hover { background-color: $ok_hover; }
QPushButton#exportBtn:disabled { background-color: $surface2; color: $disabled_text; }
QPushButton#playBtn {
    background-color: $accent; border: none;
    font-weight: bold; color: $accent_text;
}
QPushButton#playBtn:hover { background-color: $accent_hover; }
QPushButton#cellBtn {
    padding: 0px; font-weight: bold;
    background-color: $surface; border: 1px solid $border_input; border-radius: 5px;
}
QPushButton#cellBtn:hover { background-color: $head_bg; }
QPushButton#cellBtn:disabled { color: $disabled_text; background-color: $surface2; }
QPushButton#dangerBtn { background-color: $danger; border: 1px solid $danger_hover;
    color: #ffffff; }
QPushButton#dangerBtn:hover { background-color: $danger_hover; }
QPushButton#dangerBtn:disabled { color: $disabled_text; background-color: $surface2;
    border: 1px solid $border; }
QSlider::groove:horizontal {
    height: 6px; background: $border; border-radius: 3px;
}
QSlider::handle:horizontal {
    background: $accent; width: 16px; height: 16px;
    margin: -6px 0; border-radius: 8px;
}
QProgressBar {
    background-color: $surface2; border: 1px solid $border_input;
    border-radius: 6px; text-align: center; color: $text; height: 18px;
}
QProgressBar::chunk { background-color: $ok; border-radius: 5px; }
QScrollArea { border: none; }
QCheckBox, QRadioButton { spacing: 8px; color: $text_soft; }
QCheckBox::indicator, QRadioButton::indicator { width: 16px; height: 16px; }
QCheckBox::indicator:unchecked, QRadioButton::indicator:unchecked {
    border: 1px solid $border_input; border-radius: 4px; background: $surface2;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    border: 1px solid $accent; border-radius: 4px; background: $accent;
}
QToolTip { background-color: $surface2; color: $text; border: 1px solid $border_input; }
QTableWidget {
    background-color: $surface2;
    alternate-background-color: $alt_row;
    border: 1px solid $border;
    border-radius: 8px;
    gridline-color: $grid;
    selection-background-color: $selection;
    selection-color: $sel_text;
    color: $text_soft;
}
QTableWidget::item { padding: 3px 6px; }
QTableWidget::item:selected { background-color: $selection; color: $sel_text; }
QHeaderView::section {
    background-color: $head_bg;
    color: $title;
    border: none;
    border-right: 1px solid $border;
    border-bottom: 1px solid $border;
    padding: 7px 8px;
    font-weight: bold;
}
QTableCornerButton::section { background-color: $head_bg; border: none; }
QScrollBar:vertical {
    background: $surface2; width: 12px; margin: 2px; border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: $scroll_thumb; min-height: 28px; border-radius: 5px;
}
QScrollBar::handle:vertical:hover { background: $accent; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal {
    background: $surface2; height: 12px; margin: 2px; border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: $scroll_thumb; min-width: 28px; border-radius: 5px;
}
QScrollBar::handle:horizontal:hover { background: $accent; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QWidget#previewViewport { background-color: $preview_bg; border-radius: 8px; }
""")

_CURRENT = "Dark"


def build_qss(palette):
    return _QSS_TEMPLATE.substitute(palette)


def current_palette():
    return THEMES[_CURRENT]


def apply_theme(app, name):
    global _CURRENT
    _CURRENT = name if name in THEMES else "Dark"
    app.setStyleSheet(build_qss(THEMES[_CURRENT]))
    return _CURRENT


def set_prop(widget, name, value):
    """Set a dynamic property and restyle so QSS selectors re-evaluate."""
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


DARK_QSS = build_qss(THEMES["Dark"])