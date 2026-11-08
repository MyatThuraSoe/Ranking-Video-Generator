"""Palette-driven application themes: Dark, Bright, Blue, Green.

The design language is a soft "card" UI: a tinted app background, raised
surface cards, generous radii and a single strong accent per theme.  Every
colour used by the stylesheet lives in a palette dict so the four themes stay
visually consistent and the render engine remains unaffected.
"""
from string import Template
import os

THEME_NAMES = ["Dark", "Bright", "Blue", "Green"]

THEMES = {
    "Dark": dict(
        bg="#0f1117", surface="#161a23", surface2="#1c2130",
        surface3="#232a3a", border="#2a3142", border_input="#38415a",
        text="#eef2f8", text_soft="#c8d0df", dim="#8a94a8",
        accent="#4d8dff", accent_hover="#6aa0ff", accent_soft="#1b2c4d",
        accent_text="#ffffff",
        title="#a9c8ff", selection="#284a85", sel_text="#ffffff",
        ok="#22c55e", ok_hover="#34d399", ok_text="#7ee2a8",
        err_text="#fda4af", danger="#dc3d4b", danger_hover="#ef5260",
        warn="#f0c05a", chip_bg="#1b2c4d", chip_warn_bg="#3a3018",
        head_bg="#202737", grid="#242b3b", alt_row="#191e2a",
        scroll_thumb="#3a4560", preview_bg="#0a0c12",
        disabled_text="#5f687b", menu_bg="#171b25",
    ),
    "Bright": dict(
        bg="#eef2f8", surface="#ffffff", surface2="#f6f8fc",
        surface3="#eaf0f8", border="#dfe6ef", border_input="#c7d2e1",
        text="#0f172a", text_soft="#334155", dim="#6b7a90",
        accent="#2563eb", accent_hover="#1d4ed8", accent_soft="#dbeafe",
        accent_text="#ffffff",
        title="#1d4ed8", selection="#bfdbfe", sel_text="#0f172a",
        ok="#16a34a", ok_hover="#15803d", ok_text="#166534",
        err_text="#b91c1c", danger="#dc2626", danger_hover="#b91c1c",
        warn="#b45309", chip_bg="#e0e7ff", chip_warn_bg="#fef3c7",
        head_bg="#edf2f9", grid="#e6ebf3", alt_row="#f8fafc",
        scroll_thumb="#c2cddd", preview_bg="#dfe7f2",
        disabled_text="#9aa8bb", menu_bg="#ffffff",
    ),
    "Blue": dict(
        bg="#07111f", surface="#0d1c30", surface2="#11253d",
        surface3="#16304c", border="#1e3a59", border_input="#2a4c70",
        text="#e8f3ff", text_soft="#c3d7ea", dim="#7e97b2",
        accent="#38bdf8", accent_hover="#67d3fb", accent_soft="#0d3654",
        accent_text="#04121f",
        title="#7dd3fc", selection="#154a78", sel_text="#ffffff",
        ok="#10b981", ok_hover="#34d399", ok_text="#6ee7b7",
        err_text="#f87171", danger="#b93c4e", danger_hover="#d04a5e",
        warn="#fbbf24", chip_bg="#0f3350", chip_warn_bg="#3a3018",
        head_bg="#112b46", grid="#173653", alt_row="#0b1d31",
        scroll_thumb="#2a4c70", preview_bg="#04101c",
        disabled_text="#5b7490", menu_bg="#0c1a2c",
    ),
    "Green": dict(
        bg="#08130d", surface="#0f2016", surface2="#13291c",
        surface3="#183523", border="#21452e", border_input="#2f5a3d",
        text="#eaf7ee", text_soft="#c8e2d1", dim="#86a892",
        accent="#34d399", accent_hover="#5ee7b0", accent_soft="#123a27",
        accent_text="#04150c",
        title="#86efac", selection="#1e5b38", sel_text="#ffffff",
        ok="#22c55e", ok_hover="#4ade80", ok_text="#86efac",
        err_text="#f87171", danger="#a83a48", danger_hover="#c24a59",
        warn="#fbbf24", chip_bg="#123a27", chip_warn_bg="#3a3018",
        head_bg="#173322", grid="#1c3d28", alt_row="#0d1c13",
        scroll_thumb="#2f5a3d", preview_bg="#050f09",
        disabled_text="#5f7d69", menu_bg="#0e1e14",
    ),
}


def _asset(name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", name)
    return path.replace("\\", "/")


def _hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _luminance(value):
    r, g, b = _hex_rgb(value)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


for _palette in THEMES.values():
    _light = _luminance(_palette["bg"]) > 0.45
    _palette["icon_chevron_down"] = _asset(
        "chevron_down_light.svg" if _light else "chevron_down_dark.svg")
    _palette["icon_chevron_up"] = _asset(
        "chevron_up_light.svg" if _light else "chevron_up_dark.svg")
    _palette["icon_check"] = _asset(
        "check_dark.svg" if _luminance(_palette["accent"]) > 0.60
        else "check_light.svg")

_QSS_TEMPLATE = Template("""
/* ---------------------------------------------------------------- base */
QWidget {
    color: $text;
    background: transparent;
    font-family: "Segoe UI";
    font-size: 13px;
}
QMainWindow, QDialog { background-color: $bg; }
QWidget#appBody { background-color: $bg; }
QToolTip {
    background-color: $surface3; color: $text;
    border: 1px solid $border_input; border-radius: 6px;
    padding: 6px 9px;
}

/* ------------------------------------------------------------ menu bar */
QMenuBar {
    background-color: $surface; color: $text_soft;
    border-bottom: 1px solid $border; padding: 3px 8px;
}
QMenuBar::item {
    background: transparent; padding: 6px 12px; border-radius: 6px;
}
QMenuBar::item:selected { background-color: $surface3; color: $text; }
QMenuBar::item:pressed { background-color: $accent; color: $accent_text; }
QMenu {
    background-color: $menu_bg; color: $text_soft;
    border: 1px solid $border_input; border-radius: 10px; padding: 6px;
}
QMenu::item { padding: 7px 28px 7px 14px; border-radius: 6px; }
QMenu::item:selected { background-color: $accent; color: $accent_text; }
QMenu::item:disabled { color: $disabled_text; }
QMenu::separator { height: 1px; background: $border; margin: 6px 8px; }
QMenu::indicator { width: 14px; height: 14px; margin-left: 6px; }
QMenu::indicator:checked {
    background-color: $accent; border: 1px solid $accent_hover; border-radius: 4px;
    image: url("$icon_check");
}
QMenu::indicator:unchecked {
    background-color: $surface2; border: 1px solid $border_input; border-radius: 4px;
}

/* -------------------------------------------------------------- header */
QWidget#appHeader {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 $surface, stop:1 $surface2);
    border-top: 3px solid $accent;
    border-bottom: 1px solid $border;
}
QLabel#logoMark {
    background: transparent; border: none; border-radius: 10px;
    color: $accent; font-size: 20px; font-weight: 800;
}
QLabel#appTitle { color: $text; font-size: 19px; font-weight: 700; }
QLabel#appSubtitle { color: $dim; font-size: 12px; }
QPushButton#headerAction {
    background-color: transparent; border: 1px solid $border_input;
    border-radius: 8px; padding: 7px 13px;
    color: $text_soft; font-weight: 600;
}
QPushButton#headerAction:hover {
    background-color: $surface3; border-color: $accent; color: $text;
}
QPushButton#headerAction:pressed { background-color: $accent_soft; }

/* --------------------------------------------------------------- cards */
QGroupBox {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 12px;
    margin-top: 17px;
    padding: 18px 14px 14px 14px;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 7px;
    background-color: $surface;
    color: $title;
    font-size: 12px;
    font-weight: 700;
}
QGroupBox#exportCard {
    margin-top: 15px;
    padding: 14px 12px 12px 12px;
}
QWidget#previewCard, QWidget#timelineCard {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 12px;
}
QLabel#panelTitle { color: $text; font-size: 14px; font-weight: 700; }
QLabel#previewChip, QLabel#timeChip {
    background-color: $surface2; color: $text_soft;
    border: 1px solid $border; border-radius: 9px;
    padding: 3px 9px; font-size: 11px; font-weight: 600;
}
QLabel#pageTitle { color: $text; font-size: 20px; font-weight: 700; }
QLabel#countLabel {
    color: $title; font-size: 11px; font-weight: 700;
    background-color: $accent_soft; border: 1px solid $accent;
    border-radius: 9px; padding: 2px 9px;
}

/* ---------------------------------------------------------- collapsible */
QToolButton#sectionHeader {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 11px;
    padding: 10px 14px;
    color: $title;
    font-weight: 700;
    text-align: left;
}
QToolButton#sectionHeader:hover {
    background-color: $surface3; border-color: $border_input;
}
QToolButton#sectionHeader:checked {
    background-color: $surface3; border-color: $accent;
}
QWidget#sectionBody {
    background-color: $surface; border: 1px solid $border; border-radius: 11px;
}

/* --------------------------------------------------------------- text */
QLabel { color: $text_soft; }
QLabel#fieldLabel { color: $dim; font-weight: 600; }
QLabel#miniLabel { color: $dim; font-size: 12px; }
QLabel#valueLabel { color: $text_soft; font-size: 12px; }
QLabel#hintLabel { color: $dim; font-size: 12px; }
QLabel#statusLabel[error="false"] { color: $ok_text; font-size: 12px; }
QLabel#statusLabel[error="true"] { color: $err_text; font-size: 12px; }
QLabel#projectChip[saved="true"] {
    color: $title; background-color: $chip_bg;
    border: 1px solid $accent; border-radius: 10px; padding: 3px 10px;
    font-size: 11px; font-weight: 600;
}
QLabel#projectChip[saved="false"] {
    color: $warn; background-color: $chip_warn_bg;
    border: 1px solid $warn; border-radius: 10px; padding: 3px 10px;
    font-size: 11px; font-weight: 600;
}

/* ------------------------------------------------- tower image manager */
QLabel#towerThumb {
    background-color: $surface2; border: 1px solid $border_input;
    border-radius: 7px; color: $dim; font-size: 12px;
}
QPushButton#towerImgRemove {
    padding: 3px 8px; font-size: 12px; border-radius: 7px;
    color: $err_text;
}
QPushButton#towerImgRemove:hover { border-color: $danger; }
QPushButton#towerImgRemove:disabled { color: $disabled_text; }

/* ---------------------------------------------------------- code editor */
QPlainTextEdit#codeEditor {
    background-color: $surface2; border: 1px solid $border_input;
    border-radius: 10px; padding: 10px 12px; color: $text;
    font-family: "Cascadia Mono", "Consolas", monospace; font-size: 12px;
    selection-background-color: $accent; selection-color: $accent_text;
}
QPlainTextEdit#codeEditor:focus { border-color: $accent; }
QPlainTextEdit#codeEditor:disabled {
    color: $disabled_text; background-color: $surface2; border-color: $border;
}
QPushButton#codeSaveBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 $accent, stop:1 $accent_hover);
    border: 1px solid $accent_hover; color: $accent_text; padding: 6px 12px;
}
QPushButton#codeSaveBtn:hover { background: $accent_hover; }
QPushButton#codeSaveBtn:disabled {
    background: $surface2; border-color: $border; color: $disabled_text;
}
QLabel#thumbLabel {
    border: 1px solid $border_input; border-radius: 7px;
    background-color: $surface2; color: $dim;
}
QLabel#cellName { color: $text_soft; border: none; font-size: 12px; }
QLabel#cellName[empty="true"] { color: $dim; }

/* ------------------------------------------------------------- inputs */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: $surface2;
    border: 1px solid $border_input;
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 20px;
    color: $text;
    selection-background-color: $accent;
    selection-color: $accent_text;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: $dim;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid $accent;
    background-color: $surface3;
}
QLineEdit:disabled, QComboBox:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled {
    color: $disabled_text; background-color: $surface2;
    border-color: $border;
}
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow {
    image: url("$icon_chevron_down"); width: 12px; height: 12px;
}
QComboBox QAbstractItemView {
    background-color: $surface2; color: $text;
    border: 1px solid $border_input; border-radius: 8px;
    padding: 4px; outline: none;
    selection-background-color: $accent; selection-color: $accent_text;
}
QComboBox QAbstractItemView::item { padding: 6px 10px; border-radius: 5px; }
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border; subcontrol-position: top right;
    width: 20px; border: none; background: transparent;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 20px; border: none; background: transparent;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url("$icon_chevron_up"); width: 9px; height: 9px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url("$icon_chevron_down"); width: 9px; height: 9px;
}

/* ------------------------------------------------------------- buttons */
QPushButton {
    background-color: $surface2;
    border: 1px solid $border_input;
    border-radius: 8px;
    padding: 7px 14px;
    color: $text;
    font-weight: 600;
}
QPushButton:hover {
    background-color: $surface3; border-color: $accent;
}
QPushButton:pressed { background-color: $accent_soft; border-color: $accent; }
QPushButton:disabled {
    color: $disabled_text; background-color: $surface2;
    border-color: $border;
}
QPushButton#colorBtn { border-radius: 8px; padding: 0; }
QPushButton#exportBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 $accent, stop:1 $accent_hover);
    border: 1px solid $accent_hover;
    color: $accent_text;
    font-size: 14px; font-weight: 700; padding: 10px;
    border-radius: 10px;
}
QPushButton#exportBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 $accent_hover, stop:1 $accent_hover);
    border-color: $accent_hover;
}
QPushButton#exportBtn:pressed { background: $accent; }
QPushButton#exportBtn:disabled {
    background: $surface2; border-color: $border; color: $disabled_text;
}
QPushButton#playBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 $accent, stop:1 $accent_hover);
    border: none; color: $accent_text;
    font-weight: 700; padding: 8px 18px; border-radius: 9px;
}
QPushButton#playBtn:hover { background: $accent_hover; }
QPushButton#playBtn:disabled { background: $surface2; color: $disabled_text; }
QPushButton#cellBtn {
    padding: 0; font-weight: 700; font-size: 12px;
    background-color: $surface2; border: 1px solid $border_input;
    border-radius: 7px;
}
QPushButton#cellBtn:hover { background-color: $surface3; border-color: $accent; }
QPushButton#cellBtn:disabled {
    color: $disabled_text; background-color: $surface2; border-color: $border;
}
QPushButton#dangerBtn {
    background-color: $danger; border: 1px solid $danger_hover;
    color: #ffffff;
}
QPushButton#dangerBtn:hover { background-color: $danger_hover; }
QPushButton#dangerBtn:disabled {
    color: $disabled_text; background-color: $surface2; border-color: $border;
}

/* ------------------------------------------------------------- sliders */
QSlider::groove:horizontal {
    height: 4px; background: $surface3; border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: $accent; border-radius: 2px;
}
QSlider::handle:horizontal {
    background: $text; width: 14px; height: 14px;
    margin: -6px 0; border-radius: 8px;
    border: 2px solid $accent;
}
QSlider::handle:horizontal:hover { background: $accent; border-color: $text; }
QSlider::handle:horizontal:disabled { background: $disabled_text; }

/* ------------------------------------------------------------ progress */
QProgressBar {
    background-color: $surface2; border: 1px solid $border_input;
    border-radius: 7px; text-align: center; color: $text;
    height: 18px; font-size: 11px; font-weight: 600;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 $accent, stop:1 $accent_hover);
    border-radius: 6px;
}

/* ----------------------------------------------------------- checks */
QCheckBox, QRadioButton { spacing: 9px; color: $text_soft; }
QCheckBox::indicator, QRadioButton::indicator { width: 17px; height: 17px; }
QCheckBox::indicator:unchecked, QRadioButton::indicator:unchecked {
    border: 1px solid $border_input; border-radius: 5px;
    background: $surface2;
}
QCheckBox::indicator:unchecked:hover,
QRadioButton::indicator:unchecked:hover { border-color: $accent; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    border: 1px solid $accent; border-radius: 5px;
    background: $accent; image: url("$icon_check");
}
QRadioButton::indicator:checked { border-radius: 9px; }

/* -------------------------------------------------------------- tables */
QTableWidget {
    background-color: $surface;
    alternate-background-color: $alt_row;
    border: 1px solid $border;
    border-radius: 10px;
    gridline-color: transparent;
    selection-background-color: $selection;
    selection-color: $sel_text;
    color: $text_soft;
}
QTableWidget::item {
    padding: 4px 8px;
    border-bottom: 1px solid $border;
}
QTableWidget::item:hover { background-color: $surface3; }
QTableWidget::item:selected {
    background-color: $selection; color: $sel_text;
}
QHeaderView::section {
    background-color: $head_bg;
    color: $text_soft;
    border: none;
    border-right: 1px solid $border;
    border-bottom: 1px solid $border;
    padding: 8px 10px;
    font-weight: 700;
}
QTableCornerButton::section { background-color: $head_bg; border: none; }

/* ----------------------------------------------------------- scrolling */
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: transparent; width: 10px; margin: 3px 1px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: $scroll_thumb; min-height: 30px;
    border-radius: 4px; margin: 0 2px;
}
QScrollBar::handle:vertical:hover { background: $accent; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: transparent; height: 10px; margin: 1px 3px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: $scroll_thumb; min-width: 30px;
    border-radius: 4px; margin: 2px 0;
}
QScrollBar::handle:horizontal:hover { background: $accent; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

/* ------------------------------------------------------------ splitter */
QSplitter::handle { background: transparent; }
QSplitter::handle:horizontal { width: 12px; }
QSplitter::handle:hover {
    background: $accent_soft; border-radius: 5px;
}

/* ------------------------------------------------------------- preview */
QWidget#previewViewport { background-color: $preview_bg; border-radius: 12px; }
""")

_CURRENT = "Bright"


def build_qss(palette):
    return _QSS_TEMPLATE.substitute(palette)


def current_palette():
    return THEMES[_CURRENT]


def _apply_palette(app, palette):
    """Keep native widgets (dialogs, tooltips) in sync with the QSS theme."""
    from PyQt6.QtGui import QColor, QPalette

    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: palette["bg"],
        QPalette.ColorRole.WindowText: palette["text"],
        QPalette.ColorRole.Base: palette["surface"],
        QPalette.ColorRole.AlternateBase: palette["alt_row"],
        QPalette.ColorRole.ToolTipBase: palette["surface3"],
        QPalette.ColorRole.ToolTipText: palette["text"],
        QPalette.ColorRole.Text: palette["text"],
        QPalette.ColorRole.Button: palette["surface2"],
        QPalette.ColorRole.ButtonText: palette["text"],
        QPalette.ColorRole.BrightText: palette["err_text"],
        QPalette.ColorRole.Highlight: palette["accent"],
        QPalette.ColorRole.HighlightedText: palette["accent_text"],
        QPalette.ColorRole.PlaceholderText: palette["dim"],
    }
    for role, value in roles.items():
        p.setColor(role, QColor(value))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(palette["disabled_text"]))
    app.setPalette(p)


def apply_theme(app, name):
    global _CURRENT
    _CURRENT = name if name in THEMES else "Bright"
    palette = THEMES[_CURRENT]
    app.setStyleSheet(build_qss(palette))
    _apply_palette(app, palette)
    return _CURRENT


def set_prop(widget, name, value):
    """Set a dynamic property and restyle so QSS selectors re-evaluate."""
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


DARK_QSS = build_qss(THEMES["Dark"])
