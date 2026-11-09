import os
import re

import cairo
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QColor, QIcon, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDoubleSpinBox,
    QFileDialog, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMenuBar, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QSlider, QSpinBox, QSplitter, QToolButton,
    QVBoxLayout, QWidget,
)

from core.export_worker import VideoExportThread
from core.render_engine import build_assets, render_frame
from data.data_loader import load_dataset
from data.demo_data import get_demo_data
from data import state_store as store
from data.state_store import get_theme, set_theme
from ui import styles
from ui.default_preset import curated_template
from ui.license_dialog import LicenseDialog
from ui.preview_viewport import PreviewViewport
from utils import license as license_service
from utils.app_paths import logo_path
from utils.config import (
    BASE_DURATION, compute_duration, ENCODE_PRESETS, FPS_OPTIONS, QUALITY_PRESETS, RESOLUTIONS,
    TOP_N, RenderConfig,
)

EASING_OPTIONS = {
    "Smooth Deceleration (Cubic)": "cubic",
    "Elastic / Bounce": "elastic",
    "Exponential Dramatic": "exponential",
    "Linear Steady": "linear",
}
SCALE_MODES = {
    "Auto (recommended)": "auto",
    "Linear": "linear",
    "Square root": "sqrt",
    "Logarithmic (huge gaps)": "log",
    "Rank order (equal steps)": "rank",
}
COMPACT_MODES = {"Auto": "auto", "Always (200M)": "on",
                 "Never (200,000,000)": "off"}
BG_MODES = {"Sky Gradient": "sky", "Custom Image": "image"}
TITLE_ALIGNS = {"Left": "left", "Center": "center", "Right": "right"}
BADGE_SHAPES = {"Pill": "pill", "Circle": "circle", "Plain Text": "text"}
AVATAR_SHAPES = {"Circle": "circle", "Rounded Square": "rounded",
                 "Square": "square"}


class ColorButton(QPushButton):
    """Button that shows its current color and opens a picker on click."""

    colorChanged = pyqtSignal()

    def __init__(self, rgb, parent=None):
        super().__init__(parent)
        self.rgb = tuple(rgb)
        self.setObjectName("colorBtn")
        self.setFixedHeight(32)
        self.setMinimumWidth(76)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._pick)
        self._repaint()

    def _repaint(self):
        r, g, b = [int(c * 255) for c in self.rgb]
        border = styles.current_palette()["border_input"]
        self.setStyleSheet(
            f"background-color: rgb({r},{g},{b});"
            f"border: 1px solid {border}; border-radius: 8px;")

    def _pick(self):
        r, g, b = [int(c * 255) for c in self.rgb]
        col = QColorDialog.getColor(QColor(r, g, b), self, "Pick color")
        if col.isValid():
            self.rgb = (col.redF(), col.greenF(), col.blueF())
            self._repaint()
            self.colorChanged.emit()


def _group_layout(g):
    lay = QVBoxLayout(g)
    lay.setContentsMargins(4, 10, 4, 6)
    lay.setSpacing(10)
    return lay


def _row(*widgets, stretch_last=True):
    lay = QHBoxLayout()
    lay.setSpacing(10)
    for w in widgets:
        lay.addWidget(w)
    if stretch_last:
        lay.addStretch(1)
    return lay


def _field_row(label, *controls):
    """A settings row with a fixed-width caption so controls line up."""
    lay = QHBoxLayout()
    lay.setSpacing(10)
    cap = QLabel(label)
    cap.setObjectName("fieldLabel")
    cap.setFixedWidth(124)
    lay.addWidget(cap)
    expands = bool(controls) and isinstance(
        controls[0], (QComboBox, QLineEdit, QPlainTextEdit, QSlider))
    for i, w in enumerate(controls):
        lay.addWidget(w, 1 if (expands and i == 0) else 0)
    if not expands:
        lay.addStretch(1)
    return lay


def _mini_label(text):
    lbl = QLabel(text)
    lbl.setObjectName("miniLabel")
    return lbl


def _value_label(text, width=172):
    lbl = QLabel(text)
    lbl.setObjectName("valueLabel")
    lbl.setMinimumWidth(width)
    return lbl


def _slider_row(label, slider):
    lay = QHBoxLayout()
    lay.setContentsMargins(0, 7, 0, 7)
    lay.setSpacing(12)
    slider.setMinimumHeight(24)
    lay.addWidget(label)
    lay.addWidget(slider, 1)
    return lay


def _font_spin(value, tip):
    sp = QDoubleSpinBox()
    sp.setRange(0.08, 1.20)
    sp.setSingleStep(0.02)
    sp.setDecimals(2)
    sp.setValue(value)
    sp.setToolTip(tip)
    return sp


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LRBar-RankGen")
        self.resize(1400, 900)
        self.setAcceptDrops(True)
        logo = logo_path()
        if logo:
            self.setWindowIcon(QIcon(logo))

        self.df = get_demo_data()
        self.assets = None
        self.assets_sig = None
        self.export_thread = None
        self._scrub_lock = False

        self.play_timer = QTimer(self)
        self.play_timer.setInterval(33)
        self.play_timer.timeout.connect(self._play_tick)

        self._build_ui()
        self._connect_signals()
        # Start on the curated "hook" look so the first thing a new user sees
        # is a finished, upload-ready style rather than neutral defaults.
        self.apply_template(curated_template(len(self.df)))
        self._refresh_license_ui()

    # ------------------------------------------------------------- menu bar
    def _build_menu_bar(self):
        self.menu_bar = QMenuBar(self)
        file_menu = self.menu_bar.addMenu("File")
        act = file_menu.addAction("Import CSV / Excel…")
        act.triggered.connect(self._import_dataset)
        act = file_menu.addAction("Edit Data Table…")
        act.triggered.connect(self._edit_data_table)
        file_menu.addSeparator()
        act = file_menu.addAction("Save Current Frame as PNG…")
        act.triggered.connect(self._save_frame_png)
        act = file_menu.addAction("Export Video…")
        act.triggered.connect(self._start_export)
        file_menu.addSeparator()
        act = file_menu.addAction("License…")
        act.triggered.connect(self._show_license)
        file_menu.addSeparator()
        act = file_menu.addAction("Quit")
        act.triggered.connect(self.close)

        tpl_menu = self.menu_bar.addMenu("Templates")
        act = tpl_menu.addAction("Save Current Settings as Template…")
        act.triggered.connect(self._save_template)
        act = tpl_menu.addAction("Browse / Apply Templates…")
        act.triggered.connect(self._browse_templates)
        tpl_menu.addSeparator()
        act = tpl_menu.addAction("Reset to Recommended Look")
        act.triggered.connect(self._reset_to_defaults)

        theme_menu = self.menu_bar.addMenu("Theme")
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        self._theme_actions = {}
        current = get_theme()
        if current not in styles.THEME_NAMES:
            current = "Bright"
        for name in styles.THEME_NAMES:
            act = theme_menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(name == current)
            act.triggered.connect(
                lambda _checked=False, n=name: self._apply_theme(n))
            self._theme_group.addAction(act)
            self._theme_actions[name] = act

    def _apply_theme(self, name):
        app = QApplication.instance()
        if app is not None:
            styles.apply_theme(app, name)
        set_theme(name)
        self._theme_actions[name].setChecked(True)
        # Color swatches paint their own inline style; refresh their borders.
        for btn in self.findChildren(ColorButton):
            btn._repaint()
        self.viewport.update()

    # ------------------------------------------------------------- app header
    def _build_app_header(self):
        header = QWidget()
        header.setObjectName("appHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(18, 10, 18, 10)
        hl.setSpacing(12)

        mark = QLabel()
        mark.setObjectName("logoMark")
        mark.setFixedSize(40, 40)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo = logo_path()
        pm = QIcon(logo).pixmap(40, 40) if logo else QPixmap()
        if not pm.isNull():
            mark.setPixmap(pm)
        else:
            mark.setText("LR")
        hl.addWidget(mark)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = QLabel("LRBar-RankGen")
        title.setObjectName("appTitle")
        subtitle = QLabel("Cinematic 3D ranking videos  ·  live preview  ·  2K export")
        subtitle.setObjectName("appSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        hl.addLayout(titles)
        hl.addStretch(1)

        self.license_btn = QPushButton("License")
        self.license_btn.setObjectName("headerAction")
        self.license_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.license_btn.setToolTip("View license status or enter a new key")
        self.header_import_btn = QPushButton("Import data")
        self.header_import_btn.setObjectName("headerAction")
        self.header_import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_import_btn.setToolTip("Load a CSV / Excel dataset")
        self.header_tpl_btn = QPushButton("Templates")
        self.header_tpl_btn.setObjectName("headerAction")
        self.header_tpl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_tpl_btn.setToolTip("Save or re-apply a complete visual look")
        hl.addWidget(self.license_btn)
        hl.addWidget(self.header_import_btn)
        hl.addWidget(self.header_tpl_btn)
        return header

    def _collapsible_group(self, form, title, expanded=False):
        """Add a click-to-expand section header + body; return the body layout.

        Advanced settings stay collapsed by default so the first view is calm,
        while every control remains one click away (progressive disclosure).
        """
        header = QToolButton()
        header.setText("  " + title)
        header.setObjectName("sectionHeader")
        header.setCheckable(True)
        header.setChecked(expanded)
        header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        header.setArrowType(Qt.ArrowType.DownArrow if expanded
                            else Qt.ArrowType.RightArrow)
        header.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Fixed)
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        body = QWidget()
        body.setObjectName("sectionBody")
        body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(12, 14, 10, 12)
        lay.setSpacing(10)
        body.setVisible(expanded)

        def _toggled(on):
            body.setVisible(on)
            header.setArrowType(Qt.ArrowType.DownArrow if on
                                else Qt.ArrowType.RightArrow)

        header.toggled.connect(_toggled)
        form.addWidget(header)
        form.addWidget(body)
        return lay

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._build_menu_bar()
        root.addWidget(self.menu_bar)
        root.addWidget(self._build_app_header())
        body = QWidget()
        body.setObjectName("appBody")
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(14, 12, 14, 14)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        body_lay.addWidget(splitter)
        root.addWidget(body, 1)

        # ---------------- left panel ----------------
        left_holder = QWidget()
        left = QVBoxLayout(left_holder)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setMinimumWidth(420)
        form = QVBoxLayout(inner)
        form.setContentsMargins(0, 0, 6, 0)
        form.setSpacing(14)

        # 1. Dataset
        g = QGroupBox("1. Dataset")
        self.file_label = QLabel("Demo dataset (6 items)")
        self.file_label.setWordWrap(True)
        self.import_btn = QPushButton("Import CSV / Excel")
        self.import_btn.setToolTip("Load a .csv / .xlsx / .xls file with "
                                   "'name' and 'score' columns")
        gl = _group_layout(g)
        gl.addWidget(self.file_label)
        gl.addWidget(self.import_btn)
        self.table_btn = QPushButton("Edit Data Table…")
        self.table_btn.setToolTip("Open the editable data table: change names, "
                                  "scores, text and images, auto-save and "
                                  "save named project states")
        gl.addWidget(self.table_btn)
        self.topn_spin = QSpinBox()
        self.topn_spin.setRange(1, max(1, len(self.df)))
        self.topn_spin.setValue(min(TOP_N, len(self.df)))
        self.topn_spin.setToolTip("How many ranked items to render "
                                  "(defaults to the full dataset; lower it to show fewer)")
        gl.addLayout(_field_row("Items to show", self.topn_spin))
        form.addWidget(g)

        # Tower / Bar Image — one image applied to every tower graphic
        gl = self._collapsible_group(form, "Tower && Bar Image", expanded=True)
        self._tower_img_path = ""
        self.tower_image_thumb = QLabel("–")
        self.tower_image_thumb.setObjectName("towerThumb")
        self.tower_image_thumb.setFixedSize(44, 44)
        self.tower_image_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tower_image_label = QLabel("none")
        self.tower_image_label.setWordWrap(True)
        thumb_row = QHBoxLayout()
        thumb_row.setSpacing(10)
        thumb_row.addWidget(self.tower_image_thumb)
        thumb_row.addWidget(self.tower_image_label, 1)
        gl.addLayout(thumb_row)
        self.tower_image_btn = QPushButton("Add / Change image…")
        self.tower_image_btn.setToolTip(
            "Pick one image to replace every tower / bar")
        self.tower_image_btn.clicked.connect(self._pick_tower_image)
        self.tower_image_remove_btn = QPushButton("Remove")
        self.tower_image_remove_btn.setObjectName("towerImgRemove")
        self.tower_image_remove_btn.setFixedWidth(86)
        self.tower_image_remove_btn.setEnabled(False)
        self.tower_image_remove_btn.setToolTip(
            "Remove the image and restore the solid 3D towers")
        self.tower_image_remove_btn.clicked.connect(self._remove_tower_image)
        gl.addLayout(_row(self.tower_image_btn, self.tower_image_remove_btn))
        gl.addWidget(_mini_label("Replaces every tower / bar with this image"))

        # 2. Resolution & Quality
        g = QGroupBox("2. Resolution && Quality")
        gl = _group_layout(g)
        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems(RESOLUTIONS.keys())
        self.aspect_combo.setCurrentIndex(2)
        self.aspect_combo.setToolTip("Output resolution (capped at 2K)")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(QUALITY_PRESETS.keys())
        self.quality_combo.setCurrentIndex(1)
        self.quality_combo.setToolTip("Lower CRF = better quality, bigger file")
        self.fps_combo = QComboBox()
        self.fps_combo.addItems([str(f) for f in FPS_OPTIONS])
        self.fps_combo.setCurrentIndex(1)
        self.fps_combo.setToolTip("Frames per second")
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(ENCODE_PRESETS)
        self.preset_combo.setCurrentIndex(1)
        self.preset_combo.setToolTip("FFmpeg encode speed (faster = bigger file)")
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.025, 4.0)
        self.speed_spin.setSingleStep(0.025)
        self.speed_spin.setDecimals(3)
        self.speed_spin.setValue(1.0)
        self.speed_spin.setSuffix("x")
        self.speed_spin.setToolTip(
            "Camera pan speed; slower camera = longer video. Length scales "
            "with the number of items (see SECONDS_PER_ITEM in utils/config.py), "
            "divided by this speed. "
            "0.025x–4x in 0.025 steps; type any value for fine control.")
        self.duration_label = QLabel(f"{BASE_DURATION:.1f} s")
        self.duration_label.setToolTip("Resulting video duration")
        gl.addLayout(_field_row("Aspect / Resolution", self.aspect_combo))
        gl.addLayout(_field_row("Quality", self.quality_combo))
        gl.addLayout(_field_row("Frame rate", self.fps_combo))
        gl.addLayout(_field_row("Encode preset", self.preset_combo))
        gl.addLayout(_field_row("Camera speed", self.speed_spin,
                                self.duration_label))
        form.addWidget(g)

        # 3. Background & Canvas
        g = QGroupBox("3. Background && Canvas")
        gl = _group_layout(g)
        self.title_edit = QPlainTextEdit("TOP RANKINGS")
        self.title_edit.setToolTip("Video title shown at the top; press Enter for a line break")
        self.title_edit.setFixedHeight(58)
        self.title_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.title_align_combo = QComboBox()
        self.title_align_combo.addItems(TITLE_ALIGNS.keys())
        self.title_align_combo.setToolTip("Horizontal alignment of the title")
        self.title_size_spin = QSpinBox()
        self.title_size_spin.setRange(12, 120)
        self.title_size_spin.setValue(40)
        self.title_size_spin.setSuffix(" px")
        self.title_size_spin.setToolTip("Title font size")
        self.title_color_btn = ColorButton((1.0, 1.0, 1.0))
        self.title_color_btn.setToolTip("Title text color")
        self.title_margin_spin = QSpinBox()
        self.title_margin_spin.setRange(0, 400)
        self.title_margin_spin.setValue(24)
        self.title_margin_spin.setSuffix(" px")
        self.title_margin_spin.setToolTip("Gap from the top edge to the title")
        self.bg_mode_combo = QComboBox()
        self.bg_mode_combo.addItems(BG_MODES.keys())
        self.bg_mode_combo.setCurrentIndex(0)
        self.bg_mode_combo.setToolTip("Sky gradient or a custom backdrop image")
        self.bg_image_btn = QPushButton("Background image...")
        self.bg_image_btn.setToolTip("PNG/JPG used when mode = Custom Image")
        self.bg_remove_btn = QPushButton("Remove")
        self.bg_remove_btn.setFixedWidth(86)
        self.bg_remove_btn.setEnabled(False)
        self.bg_remove_btn.setToolTip("Clear the loaded background image")
        self.bg_image_label = QLabel("none")
        self.bg_image_label.setWordWrap(True)
        self.blur_slider = QSlider(Qt.Orientation.Horizontal)
        self.blur_slider.setRange(0, 30)
        self.blur_slider.setValue(10)
        self.blur_slider.setToolTip("Gaussian blur applied to background image")
        self.blur_label = _value_label("Blur: 10")
        self.dim_slider = QSlider(Qt.Orientation.Horizontal)
        self.dim_slider.setRange(0, 80)
        self.dim_slider.setValue(40)
        self.dim_slider.setToolTip("Darken background image (0-80%)")
        self.dim_label = _value_label("Dim: 40%")
        gl.addLayout(_field_row("Title", self.title_edit))
        gl.addLayout(_field_row("Alignment", self.title_align_combo,
                                _mini_label("Size"), self.title_size_spin,
                                self.title_color_btn))
        gl.addLayout(_field_row("Top margin", self.title_margin_spin))
        gl.addLayout(_field_row("Mode", self.bg_mode_combo))
        gl.addLayout(_field_row("Backdrop", self.bg_image_btn,
                                self.bg_remove_btn, self.bg_image_label))
        gl.addLayout(_slider_row(self.blur_label, self.blur_slider))
        gl.addLayout(_slider_row(self.dim_label, self.dim_slider))
        self._canvas_img_path = ""
        self.canvas_image_thumb = QLabel("–")
        self.canvas_image_thumb.setObjectName("towerThumb")
        self.canvas_image_thumb.setFixedSize(44, 44)
        self.canvas_image_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas_image_label = QLabel("none")
        self.canvas_image_label.setWordWrap(True)
        canvas_thumb_row = QHBoxLayout()
        canvas_thumb_row.setSpacing(10)
        canvas_thumb_row.addWidget(self.canvas_image_thumb)
        canvas_thumb_row.addWidget(self.canvas_image_label, 1)
        gl.addLayout(canvas_thumb_row)
        self.canvas_image_btn = QPushButton("Add / Change canvas image…")
        self.canvas_image_btn.setToolTip(
            "One image covers the whole backdrop — sky, skyline and ground")
        self.canvas_image_btn.clicked.connect(self._pick_canvas_image)
        self.canvas_image_remove_btn = QPushButton("Remove")
        self.canvas_image_remove_btn.setObjectName("towerImgRemove")
        self.canvas_image_remove_btn.setFixedWidth(86)
        self.canvas_image_remove_btn.setEnabled(False)
        self.canvas_image_remove_btn.setToolTip(
            "Remove the canvas image and restore the scene background")
        self.canvas_image_remove_btn.clicked.connect(self._remove_canvas_image)
        gl.addLayout(_row(self.canvas_image_btn, self.canvas_image_remove_btn))
        gl.addWidget(_mini_label("Full-canvas image — covers sky, skyline and ground"))
        form.addWidget(g)

        # 4. Ranking Badges
        gl = self._collapsible_group(form, "Ranking Badges", expanded=False)
        self.badge_check = QCheckBox("Show rank numbers")
        self.badge_check.setChecked(True)
        self.badge_shape_combo = QComboBox()
        self.badge_shape_combo.addItems(BADGE_SHAPES.keys())
        self.badge_shape_combo.setToolTip("Shape behind the rank number")
        self.badge_color_btn = ColorButton((1.0, 0.76, 0.16))
        self.badge_color_btn.setToolTip("Badge background color")
        self.badge_size_spin = QDoubleSpinBox()
        self.badge_size_spin.setRange(0.5, 3.0)
        self.badge_size_spin.setSingleStep(0.1)
        self.badge_size_spin.setDecimals(1)
        self.badge_size_spin.setValue(1.0)
        self.badge_size_spin.setSuffix("x")
        self.badge_size_spin.setToolTip("Scale of the badge background shape")
        gl.addWidget(self.badge_check)
        gl.addLayout(_field_row("Shape", self.badge_shape_combo))
        gl.addLayout(_field_row("Badge color", self.badge_color_btn))
        gl.addLayout(_field_row("Badge size", self.badge_size_spin))

        # 5. Avatars & Audio
        gl = self._collapsible_group(form, "Avatars && Audio", expanded=False)
        self.shadow_check = QCheckBox("Drop shadow")
        self.shadow_check.setChecked(True)
        self.avatar_combo = QComboBox()
        self.avatar_combo.addItems(AVATAR_SHAPES.keys())
        self.avatar_combo.setToolTip("Avatar/logo crop shape")
        self.avatar_size_spin = QDoubleSpinBox()
        self.avatar_size_spin.setRange(0.5, 3.0)
        self.avatar_size_spin.setSingleStep(0.1)
        self.avatar_size_spin.setDecimals(1)
        self.avatar_size_spin.setValue(1.0)
        self.avatar_size_spin.setSuffix("x")
        self.avatar_size_spin.setToolTip("Scale of the image on each tower")
        self.avatar_radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.avatar_radius_slider.setRange(0, 100)
        self.avatar_radius_slider.setValue(0)
        self.avatar_radius_slider.setToolTip(
            "Corner rounding for square images (0% sharp, 100% circle)")
        self.avatar_radius_label = _value_label("Radius: 0%")
        self.avatar_border_color_btn = ColorButton((1.0, 1.0, 1.0))
        self.avatar_border_color_btn.setToolTip("Color of the image border")
        self.avatar_border_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.avatar_border_size_slider.setRange(0, 30)
        self.avatar_border_size_slider.setValue(0)
        self.avatar_border_size_slider.setToolTip("Image border thickness (0 = none)")
        self.avatar_border_size_label = _value_label("Border: 0%")
        self.audio_btn = QPushButton("Background music...")
        self.audio_btn.setToolTip("MP3/WAV/AAC/M4A, looped and faded out")
        self.audio_remove_btn = QPushButton("Remove")
        self.audio_remove_btn.setFixedWidth(86)
        self.audio_remove_btn.setEnabled(False)
        self.audio_remove_btn.setToolTip("Clear the loaded background music")
        self.audio_label = QLabel("none")
        self.audio_label.setWordWrap(True)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(10, 150)
        self.volume_slider.setValue(100)
        self.volume_slider.setToolTip("Music volume (10-150%)")
        self.volume_label = _value_label("Volume: 100%")
        self.audio_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.audio_speed_slider.setRange(50, 200)
        self.audio_speed_slider.setValue(100)
        self.audio_speed_slider.setToolTip(
            "Music playback speed (50-200%). Pitch stays the same, "
            "so the track keeps its original key.")
        self.audio_speed_label = _value_label("Music speed: 100%")
        self.easing_combo = QComboBox()
        self.easing_combo.addItems(EASING_OPTIONS.keys())
        self.easing_combo.setToolTip("Animation easing curve")
        gl.addWidget(self.shadow_check)
        gl.addLayout(_field_row("Avatar shape", self.avatar_combo))
        gl.addLayout(_field_row("Image size", self.avatar_size_spin))
        gl.addLayout(_slider_row(self.avatar_radius_label,
                                 self.avatar_radius_slider))
        gl.addLayout(_field_row("Border color",
                                self.avatar_border_color_btn))
        gl.addLayout(_slider_row(self.avatar_border_size_label,
                                 self.avatar_border_size_slider))
        gl.addLayout(_field_row("Music", self.audio_btn,
                                self.audio_remove_btn, self.audio_label))
        gl.addLayout(_slider_row(self.volume_label, self.volume_slider))
        gl.addLayout(_slider_row(self.audio_speed_label,
                                 self.audio_speed_slider))
        gl.addLayout(_field_row("Easing", self.easing_combo))

        # 6. Camera & Scene (Incline 3D Towers)
        gl = self._collapsible_group(
            form, "Camera && Scene (Incline 3D Towers)", expanded=False)
        self.cam_elev_slider = QSlider(Qt.Orientation.Horizontal)
        self.cam_elev_slider.setRange(0, 150)
        self.cam_elev_slider.setValue(35)
        self.cam_elev_slider.setToolTip(
            "How high the camera flies ABOVE the tracked tower top (0.0-15.0)")
        self.cam_elev_label = _value_label("Camera Elevation: 3.5")
        self.cam_dist_slider = QSlider(Qt.Orientation.Horizontal)
        self.cam_dist_slider.setRange(50, 1000)
        self.cam_dist_slider.setValue(260)
        self.cam_dist_slider.setToolTip(
            "How far back the camera sits from the row (5.0-100.0)")
        self.cam_dist_label = _value_label("Camera Distance: 26.0")
        self.cam_ahead_slider = QSlider(Qt.Orientation.Horizontal)
        self.cam_ahead_slider.setRange(0, 200)
        self.cam_ahead_slider.setValue(12)
        self.cam_ahead_slider.setToolTip(
            "Aim ahead toward incoming towers; 0 looks back along the row (0.0-20.0)")
        self.cam_ahead_label = _value_label("Look-Ahead: 1.2")
        self.cam_focus_slider = QSlider(Qt.Orientation.Horizontal)
        self.cam_focus_slider.setRange(-50, 100)
        self.cam_focus_slider.setValue(5)
        self.cam_focus_slider.setToolTip(
            "Look-at height above the tower top; raise to frame logos (-5.0-10.0)")
        self.cam_focus_label = _value_label("Focus Offset: 0.5")
        self.cams_slider = QSlider(Qt.Orientation.Horizontal)
        self.cams_slider.setRange(0, 240)
        self.cams_slider.setValue(19)
        self.cams_slider.setToolTip("Lateral offset = incline angle (0.0-24.0)")
        self.cams_label = _value_label("Incline Angle: 1.9")
        self.fov_slider = QSlider(Qt.Orientation.Horizontal)
        self.fov_slider.setRange(30, 300)
        self.fov_slider.setValue(105)
        self.fov_slider.setToolTip("Zoom / field of view (0.3-3.0)")
        self.fov_label = _value_label("Zoom / FOV: 1.05")
        self.tower_color_btn = ColorButton((0.80, 0.76, 0.64))
        self.tower_color_btn.setToolTip("Tower face color")
        self.plate_color_btn = ColorButton((0.24, 0.13, 0.12))
        self.plate_color_btn.setToolTip("Name plate color")
        self.skytop_color_btn = ColorButton((0.29, 0.49, 0.71))
        self.skytop_color_btn.setToolTip("Sky gradient top color")
        self.skybot_color_btn = ColorButton((0.74, 0.80, 0.84))
        self.skybot_color_btn.setToolTip("Sky gradient bottom color")
        self.ground_color_btn = ColorButton((0.44, 0.44, 0.46))
        self.ground_color_btn.setToolTip("Ground plane color — the area below the horizon")
        self.skyline_color_btn = ColorButton((0.30, 0.31, 0.33))
        self.skyline_color_btn.setToolTip("City skyline color — the silhouette band on the horizon")
        self.vpre_edit = QLineEdit("$ ")
        self.vpre_edit.setToolTip("Text before the tower value")
        self.vsu_edit = QLineEdit(" B")
        self.vsu_edit.setToolTip("Text after the tower value")
        self.vdec_spin = QSpinBox()
        self.vdec_spin.setRange(0, 3)
        self.vdec_spin.setValue(1)
        self.vdec_spin.setToolTip("Decimal places of the tower value")
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(SCALE_MODES.keys())
        self.scale_combo.setToolTip(
            "How score maps to tower height. Auto picks Logarithmic when the "
            "biggest value is far larger than the smallest (e.g. 30K vs 200M) "
            "so every tower stays visible and readable.")
        self.compact_combo = QComboBox()
        self.compact_combo.addItems(COMPACT_MODES.keys())
        self.compact_combo.setToolTip(
            "Shorten big numbers on towers: 200,000,000 -> 200M. Auto only "
            "does this when the Suffix field is empty.")
        self.autoframe_check = QCheckBox("Auto camera framing")
        self.autoframe_check.setChecked(True)
        self.autoframe_check.setToolTip(
            "Dolly in/out so the tower being revealed always fills the "
            "screen. Camera Distance then acts as a zoom trim (19.5 = neutral).")
        self.spot_check = QCheckBox("Spotlight focused tower")
        self.spot_check.setChecked(True)
        self.spot_check.setToolTip("Gently dim towers away from the one on stage")
        gl.addLayout(_slider_row(self.cam_elev_label, self.cam_elev_slider))
        gl.addLayout(_slider_row(self.cam_dist_label, self.cam_dist_slider))
        gl.addLayout(_slider_row(self.cam_ahead_label, self.cam_ahead_slider))
        gl.addLayout(_slider_row(self.cam_focus_label, self.cam_focus_slider))
        gl.addLayout(_slider_row(self.cams_label, self.cams_slider))
        gl.addLayout(_slider_row(self.fov_label, self.fov_slider))
        gl.addLayout(_field_row("Tower", self.tower_color_btn,
                                _mini_label("Plate"), self.plate_color_btn))
        gl.addLayout(_field_row("Sky top", self.skytop_color_btn,
                                _mini_label("Sky bottom"),
                                self.skybot_color_btn))
        gl.addLayout(_field_row("Ground", self.ground_color_btn,
                                _mini_label("Skyline"), self.skyline_color_btn))
        gl.addLayout(_field_row("Value Prefix", self.vpre_edit,
                                _mini_label("Suffix"), self.vsu_edit))
        gl.addLayout(_field_row("Value Decimals", self.vdec_spin))
        gl.addLayout(_field_row("Bar scale", self.scale_combo))
        gl.addLayout(_field_row("Big numbers", self.compact_combo))
        gl.addWidget(self.autoframe_check)
        gl.addWidget(self.spot_check)

        # 7. Typography & Colors
        gl = self._collapsible_group(form, "Typography && Colors", expanded=False)
        self.rank_size_spin = QSpinBox()
        self.rank_size_spin.setRange(16, 48)
        self.rank_size_spin.setValue(28)
        self.rank_size_spin.setToolTip("Rank number font size (px)")
        self.rank_color_btn = ColorButton((0.05, 0.05, 0.10))
        self.rank_color_btn.setToolTip("Rank number text color")
        self.name_size_spin = _font_spin(0.34, "Name font size (world units)")
        self.name_color_btn = ColorButton((1.0, 1.0, 1.0))
        self.name_color_btn.setToolTip("Name text color")
        self.value_size_spin = _font_spin(0.30, "Value font size (world units)")
        self.value_color_btn = ColorButton((0.48, 0.06, 0.10))
        self.value_color_btn.setToolTip("Value text color")
        self.text_size_spin = _font_spin(0.20, "Text (subtitle) font size (world units)")
        self.text_color_btn = ColorButton((0.85, 0.85, 0.88))
        self.text_color_btn.setToolTip("Text (subtitle) color")
        self.extra_size_spin = _font_spin(0.18, "Extra text font size (world units)")
        self.extra_color_btn = ColorButton((0.80, 0.82, 0.85))
        self.extra_color_btn.setToolTip("Extra text color")
        gl.addLayout(_field_row("Rank number", self.rank_size_spin,
                                self.rank_color_btn))
        gl.addLayout(_field_row("Name", self.name_size_spin,
                                self.name_color_btn))
        gl.addLayout(_field_row("Value", self.value_size_spin,
                                self.value_color_btn))
        gl.addLayout(_field_row("Text", self.text_size_spin,
                                self.text_color_btn))
        gl.addLayout(_field_row("Extra text", self.extra_size_spin,
                                self.extra_color_btn))

        # Export
        g = QGroupBox("Export")
        g.setObjectName("exportCard")
        gl = _group_layout(g)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximumHeight(16)
        self.export_btn = QPushButton("Export Video to MP4")
        self.export_btn.setObjectName("exportBtn")
        self.frame_btn = QPushButton("Save Frame as PNG")
        self.frame_btn.setToolTip("Export the previewed frame as a still image")
        self.frame_btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                                     QSizePolicy.Policy.Fixed)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("dangerBtn")
        self.cancel_btn.setVisible(False)
        self.eco_check = QCheckBox("Eco Mode · 2 threads")
        self.eco_check.setChecked(True)
        self.eco_check.setToolTip(
            "Limit FFmpeg to 2 threads so your PC stays quiet and responsive. "
            "Uncheck for Turbo (all cores, faster export).")
        saved = store.get_video_save_path()
        if saved:
            self._video_folder = os.path.dirname(saved)
            base = os.path.splitext(os.path.basename(saved))[0]
        else:
            self._video_folder = self._default_video_folder()
            base = "ranking_video"
        self.video_name_edit = QLineEdit(base)
        self.video_name_edit.setToolTip(
            "File name for the exported video; .mp4 is added automatically")
        self.video_name_edit.textChanged.connect(self._on_video_name_changed)
        self.video_name_edit.editingFinished.connect(self._persist_video_path)
        self._video_path = os.path.join(self._video_folder, base + ".mp4")
        self.video_path_edit = QLineEdit(self._video_path)
        self.video_path_edit.setReadOnly(True)
        self.video_path_edit.setToolTip(self._video_path)
        self.video_path_edit.setCursorPosition(len(self._video_path))
        self.video_browse_btn = QPushButton("Browse…")
        self.video_browse_btn.setToolTip("Choose where the exported video is saved")
        self.video_browse_btn.clicked.connect(self._browse_video_path)
        gl.addWidget(self.progress_bar)
        gl.addWidget(self.eco_check)
        gl.addLayout(_field_row("File name", self.video_name_edit))
        gl.addLayout(_field_row("Save to", self.video_path_edit,
                                self.video_browse_btn))
        gl.addWidget(self.export_btn)
        gl.addLayout(_row(self.frame_btn, self.cancel_btn,
                          stretch_last=False))
        form.addStretch(1)

        scroll.setWidget(inner)
        left.addWidget(scroll, 1)
        # Export stays pinned below the scrolling settings so the primary
        # action is always one click away.
        left.addWidget(g)
        splitter.addWidget(left_holder)

        # ---------------- right panel ----------------
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(12)

        preview_card = QWidget()
        preview_card.setObjectName("previewCard")
        pc = QVBoxLayout(preview_card)
        pc.setContentsMargins(14, 12, 14, 14)
        pc.setSpacing(10)
        preview_head = QHBoxLayout()
        preview_head.setSpacing(8)
        preview_title = QLabel("Live preview")
        preview_title.setObjectName("panelTitle")
        self.preview_chip = QLabel("—")
        self.preview_chip.setObjectName("previewChip")
        preview_head.addWidget(preview_title)
        preview_head.addStretch(1)
        preview_head.addWidget(self.preview_chip)
        pc.addLayout(preview_head)
        self.viewport = PreviewViewport()
        pc.addWidget(self.viewport, 1)
        rl.addWidget(preview_card, 1)

        timeline = QWidget()
        timeline.setObjectName("timelineCard")
        tl = QVBoxLayout(timeline)
        tl.setContentsMargins(14, 12, 14, 12)
        tl.setSpacing(10)

        self.scrubber = QSlider(Qt.Orientation.Horizontal)
        self.scrubber.setRange(0, 1000)
        self.scrubber.setValue(1000)
        self.scrubber.setToolTip("Timeline scrubber (0-100% of animation)")

        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)
        self.play_btn = QPushButton("▶  Play")
        self.play_btn.setObjectName("playBtn")
        self.play_btn.setToolTip("Play the animation in the preview")
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setToolTip("Pause the preview playback")
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setToolTip("Jump to the beginning of the animation")
        self.end_btn = QPushButton("End")
        self.end_btn.setToolTip("Jump to the final frame")
        self.time_label = QLabel("100%")
        self.time_label.setObjectName("timeChip")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setMinimumWidth(56)
        ctrl.addWidget(self.play_btn)
        ctrl.addWidget(self.pause_btn)
        ctrl.addWidget(self.reset_btn)
        ctrl.addWidget(self.end_btn)
        ctrl.addStretch(1)
        ctrl.addWidget(self.time_label)
        tl.addLayout(ctrl)
        tl.addWidget(self.scrubber)
        rl.addWidget(timeline)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([500, 880])

    # ------------------------------------------------------------- signals
    def _connect_signals(self):
        self.import_btn.clicked.connect(self._import_dataset)
        self.header_import_btn.clicked.connect(self._import_dataset)
        self.license_btn.clicked.connect(self._show_license)
        self.table_btn.clicked.connect(self._edit_data_table)
        self.header_tpl_btn.clicked.connect(self._browse_templates)
        self.bg_image_btn.clicked.connect(self._pick_bg_image)
        self.bg_remove_btn.clicked.connect(self._remove_bg_image)
        self.audio_btn.clicked.connect(self._pick_audio)
        self.audio_remove_btn.clicked.connect(self._remove_audio)

        simple = [
            self.title_edit.textChanged,
            self.title_align_combo.currentIndexChanged,
            self.title_size_spin.valueChanged,
            self.title_margin_spin.valueChanged,
            self.topn_spin.valueChanged,
            self.aspect_combo.currentIndexChanged,
            self.quality_combo.currentIndexChanged,
            self.fps_combo.currentIndexChanged,
            self.preset_combo.currentIndexChanged,
            self.bg_mode_combo.currentIndexChanged,
            self.blur_slider.valueChanged,
            self.dim_slider.valueChanged,
            self.badge_check.toggled,
            self.badge_shape_combo.currentIndexChanged,
            self.badge_size_spin.valueChanged,
            self.rank_size_spin.valueChanged,
            self.name_size_spin.valueChanged,
            self.value_size_spin.valueChanged,
            self.text_size_spin.valueChanged,
            self.extra_size_spin.valueChanged,
            self.shadow_check.toggled,
            self.avatar_combo.currentIndexChanged,
            self.avatar_size_spin.valueChanged,
            self.avatar_radius_slider.valueChanged,
            self.avatar_border_size_slider.valueChanged,
            self.volume_slider.valueChanged,
            self.speed_spin.valueChanged,
            self.easing_combo.currentIndexChanged,
            self.cam_elev_slider.valueChanged,
            self.cam_dist_slider.valueChanged,
            self.cam_ahead_slider.valueChanged,
            self.cam_focus_slider.valueChanged,
            self.cams_slider.valueChanged,
            self.fov_slider.valueChanged,
            self.vpre_edit.textChanged,
            self.vsu_edit.textChanged,
            self.vdec_spin.valueChanged,
            self.scale_combo.currentIndexChanged,
            self.compact_combo.currentIndexChanged,
            self.autoframe_check.toggled,
            self.spot_check.toggled,
        ]
        for sig in simple:
            sig.connect(self._on_setting_changed)
        for btn in (self.badge_color_btn, self.rank_color_btn,
                    self.tower_color_btn, self.plate_color_btn,
                    self.value_color_btn, self.skytop_color_btn,
                    self.skybot_color_btn, self.ground_color_btn,
                    self.skyline_color_btn, self.name_color_btn,
                    self.text_color_btn, self.extra_color_btn,
                    self.title_color_btn, self.avatar_border_color_btn):
            btn.colorChanged.connect(self._on_setting_changed)

        self.blur_slider.valueChanged.connect(
            lambda v: self.blur_label.setText(f"Blur: {v}"))
        self.dim_slider.valueChanged.connect(
            lambda v: self.dim_label.setText(f"Dim: {v}%"))
        self.avatar_radius_slider.valueChanged.connect(
            lambda v: self.avatar_radius_label.setText(f"Radius: {v}%"))
        self.avatar_border_size_slider.valueChanged.connect(
            lambda v: self.avatar_border_size_label.setText(f"Border: {v}%"))
        self.volume_slider.valueChanged.connect(
            lambda v: self.volume_label.setText(f"Volume: {v}%"))
        self.audio_speed_slider.valueChanged.connect(
            self._update_audio_speed_label)
        self.speed_spin.valueChanged.connect(
            lambda _v: self.duration_label.setText(
                f"{self._video_duration():.1f} s"))
        self.topn_spin.valueChanged.connect(
            lambda _v: self.duration_label.setText(
                f"{self._video_duration():.1f} s"))
        self.cam_elev_slider.valueChanged.connect(
            lambda v: self.cam_elev_label.setText(f"Camera Elevation: {v / 10:.1f}"))
        self.cam_dist_slider.valueChanged.connect(
            lambda v: self.cam_dist_label.setText(f"Camera Distance: {v / 10:.1f}"))
        self.cam_ahead_slider.valueChanged.connect(
            lambda v: self.cam_ahead_label.setText(f"Look-Ahead: {v / 10:.1f}"))
        self.cam_focus_slider.valueChanged.connect(
            lambda v: self.cam_focus_label.setText(f"Focus Offset: {v / 10:.1f}"))
        self.cams_slider.valueChanged.connect(
            lambda v: self.cams_label.setText(f"Incline Angle: {v / 10:.1f}"))
        self.fov_slider.valueChanged.connect(
            lambda v: self.fov_label.setText(f"Zoom / FOV: {v / 100:.2f}"))

        self.scrubber.valueChanged.connect(self._on_scrub)
        self.play_btn.clicked.connect(self._play_start)
        self.pause_btn.clicked.connect(self.play_timer.stop)
        self.reset_btn.clicked.connect(lambda: self.scrubber.setValue(0))
        self.end_btn.clicked.connect(lambda: self.scrubber.setValue(1000))

        self.export_btn.clicked.connect(self._start_export)
        self.frame_btn.clicked.connect(self._save_frame_png)
        self.cancel_btn.clicked.connect(self._cancel_export)

    # -------------------------------------------------------------- config
    def _video_duration(self):
        return compute_duration(self.topn_spin.value(), self.speed_spin.value())

    def collect_config(self):
        cfg = RenderConfig()
        cfg.width, cfg.height = RESOLUTIONS[self.aspect_combo.currentText()]
        cfg.top_n = self.topn_spin.value()
        cfg.crf = QUALITY_PRESETS[self.quality_combo.currentText()]
        cfg.fps = FPS_OPTIONS[self.fps_combo.currentIndex()]
        cfg.duration = self._video_duration()
        cfg.title = self.title_edit.toPlainText()
        cfg.title_align = TITLE_ALIGNS[self.title_align_combo.currentText()]
        cfg.title_font_size = self.title_size_spin.value()
        cfg.title_color = self.title_color_btn.rgb
        cfg.title_top_margin = self.title_margin_spin.value()
        cfg.bg_mode = BG_MODES[self.bg_mode_combo.currentText()]
        cfg.bg_image = getattr(self, "_bg_image_path", "")
        cfg.bg_blur = self.blur_slider.value()
        cfg.bg_dim = self.dim_slider.value()
        cfg.canvas_image = getattr(self, "_canvas_img_path", "")
        cfg.shadow_enabled = self.shadow_check.isChecked()
        cfg.tower_image = getattr(self, "_tower_img_path", "")
        cfg.avatar_shape = AVATAR_SHAPES[self.avatar_combo.currentText()]
        cfg.avatar_size = self.avatar_size_spin.value()
        cfg.avatar_border_radius = self.avatar_radius_slider.value() / 100.0
        cfg.avatar_border_color = self.avatar_border_color_btn.rgb
        cfg.avatar_border_size = self.avatar_border_size_slider.value() / 100.0
        cfg.show_badges = self.badge_check.isChecked()
        cfg.badge_shape = BADGE_SHAPES[self.badge_shape_combo.currentText()]
        cfg.badge_color = self.badge_color_btn.rgb
        cfg.badge_size = self.badge_size_spin.value()
        cfg.rank_color = self.rank_color_btn.rgb
        cfg.rank_font_size = self.rank_size_spin.value()
        cfg.name_font_size = self.name_size_spin.value()
        cfg.name_color = self.name_color_btn.rgb
        cfg.value_font_size = self.value_size_spin.value()
        cfg.text_font_size = self.text_size_spin.value()
        cfg.text_color = self.text_color_btn.rgb
        cfg.extra_font_size = self.extra_size_spin.value()
        cfg.extra_color = self.extra_color_btn.rgb
        cfg.audio_file = getattr(self, "_audio_path", "")
        cfg.audio_volume = self.volume_slider.value()
        cfg.audio_speed = self.audio_speed_slider.value()
        cfg.speed = self.speed_spin.value()
        cfg.easing = EASING_OPTIONS[self.easing_combo.currentText()]
        cfg.cam_elevation = self.cam_elev_slider.value() / 10.0
        cfg.cam_distance = self.cam_dist_slider.value() / 10.0
        cfg.cam_look_ahead = self.cam_ahead_slider.value() / 10.0
        cfg.cam_focus_offset = self.cam_focus_slider.value() / 10.0
        cfg.cam_side = self.cams_slider.value() / 10.0
        cfg.cam_fov = self.fov_slider.value() / 100.0
        cfg.value_prefix = self.vpre_edit.text()
        cfg.value_suffix = self.vsu_edit.text()
        cfg.value_decimals = self.vdec_spin.value()
        cfg.scale_mode = SCALE_MODES[self.scale_combo.currentText()]
        cfg.value_compact = COMPACT_MODES[self.compact_combo.currentText()]
        cfg.cam_auto_frame = self.autoframe_check.isChecked()
        cfg.spotlight = 0.28 if self.spot_check.isChecked() else 0.0
        cfg.tower_color = self.tower_color_btn.rgb
        cfg.plate_color = self.plate_color_btn.rgb
        cfg.value_color = self.value_color_btn.rgb
        cfg.sky_top = self.skytop_color_btn.rgb
        cfg.sky_bottom = self.skybot_color_btn.rgb
        cfg.ground_color = self.ground_color_btn.rgb
        cfg.skyline_color = self.skyline_color_btn.rgb
        cfg.encode_preset = ENCODE_PRESETS[self.preset_combo.currentIndex()]
        cfg.low_resource = self.eco_check.isChecked()
        return cfg

    # ------------------------------------------------------------ templates
    def capture_template(self):
        """Snapshot every customization control (everything but the data table)."""
        return {
            "top_n": self.topn_spin.value(),
            "aspect": self.aspect_combo.currentText(),
            "quality": self.quality_combo.currentText(),
            "fps": self.fps_combo.currentText(),
            "preset": self.preset_combo.currentText(),
            "low_resource": self.eco_check.isChecked(),
            "speed": self.speed_spin.value(),
            "title": self.title_edit.toPlainText(),
            "title_align": self.title_align_combo.currentText(),
            "title_size": self.title_size_spin.value(),
            "title_color": list(self.title_color_btn.rgb),
            "title_margin": self.title_margin_spin.value(),
            "bg_mode": self.bg_mode_combo.currentText(),
            "bg_blur": self.blur_slider.value(),
            "bg_dim": self.dim_slider.value(),
            "bg_image": getattr(self, "_bg_image_path", ""),
            "canvas_image": getattr(self, "_canvas_img_path", ""),
            "show_badges": self.badge_check.isChecked(),
            "badge_shape": self.badge_shape_combo.currentText(),
            "badge_color": list(self.badge_color_btn.rgb),
            "badge_size": self.badge_size_spin.value(),
            "shadow": self.shadow_check.isChecked(),
            "tower_image": getattr(self, "_tower_img_path", ""),
            "avatar_shape": self.avatar_combo.currentText(),
            "avatar_size": self.avatar_size_spin.value(),
            "avatar_radius": self.avatar_radius_slider.value(),
            "avatar_border_color": list(self.avatar_border_color_btn.rgb),
            "avatar_border_size": self.avatar_border_size_slider.value(),
            "audio_file": getattr(self, "_audio_path", ""),
            "audio_volume": self.volume_slider.value(),
            "audio_speed": self.audio_speed_slider.value(),
            "easing": self.easing_combo.currentText(),
            "cam_elev": self.cam_elev_slider.value(),
            "cam_dist": self.cam_dist_slider.value(),
            "cam_side": self.cams_slider.value(),
            "cam_ahead": self.cam_ahead_slider.value(),
            "cam_focus": self.cam_focus_slider.value(),
            "fov": self.fov_slider.value(),
            "tower_color": list(self.tower_color_btn.rgb),
            "plate_color": list(self.plate_color_btn.rgb),
            "value_prefix": self.vpre_edit.text(),
            "value_suffix": self.vsu_edit.text(),
            "value_decimals": self.vdec_spin.value(),
            "scale_mode": self.scale_combo.currentText(),
            "value_compact": self.compact_combo.currentText(),
            "auto_frame": self.autoframe_check.isChecked(),
            "spotlight": self.spot_check.isChecked(),
            "sky_top": list(self.skytop_color_btn.rgb),
            "sky_bottom": list(self.skybot_color_btn.rgb),
            "ground_color": list(self.ground_color_btn.rgb),
            "skyline_color": list(self.skyline_color_btn.rgb),
            "rank_size": self.rank_size_spin.value(),
            "rank_color": list(self.rank_color_btn.rgb),
            "name_size": self.name_size_spin.value(),
            "name_color": list(self.name_color_btn.rgb),
            "value_size": self.value_size_spin.value(),
            "value_color": list(self.value_color_btn.rgb),
            "text_size": self.text_size_spin.value(),
            "text_color": list(self.text_color_btn.rgb),
            "extra_size": self.extra_size_spin.value(),
            "extra_color": list(self.extra_color_btn.rgb),
        }

    def apply_template(self, data):
        """Restore a captured template onto the controls, then refresh once."""
        d = data or {}
        self._applying_template = True
        try:
            def combo(c, key):
                if key in d:
                    i = c.findText(str(d[key]))
                    if i >= 0:
                        c.setCurrentIndex(i)

            def num(w, key):
                if key in d:
                    v = float(d[key])
                    w.setValue(v if isinstance(w, QDoubleSpinBox)
                               else int(round(v)))

            def text(w, key):
                if key in d:
                    if hasattr(w, "setPlainText"):
                        w.setPlainText(str(d[key]))
                    else:
                        w.setText(str(d[key]))

            def check(w, key):
                if key in d:
                    w.setChecked(bool(d[key]))

            def color(btn, key):
                if key in d and isinstance(d[key], (list, tuple)) \
                        and len(d[key]) == 3:
                    btn.rgb = tuple(float(x) for x in d[key])
                    btn._repaint()

            num(self.topn_spin, "top_n")
            combo(self.aspect_combo, "aspect")
            combo(self.quality_combo, "quality")
            combo(self.fps_combo, "fps")
            combo(self.preset_combo, "preset")
            check(self.eco_check, "low_resource")
            num(self.speed_spin, "speed")
            text(self.title_edit, "title")
            combo(self.title_align_combo, "title_align")
            num(self.title_size_spin, "title_size")
            color(self.title_color_btn, "title_color")
            num(self.title_margin_spin, "title_margin")
            combo(self.bg_mode_combo, "bg_mode")
            num(self.blur_slider, "bg_blur")
            num(self.dim_slider, "bg_dim")
            check(self.badge_check, "show_badges")
            combo(self.badge_shape_combo, "badge_shape")
            color(self.badge_color_btn, "badge_color")
            num(self.badge_size_spin, "badge_size")
            check(self.shadow_check, "shadow")
            combo(self.avatar_combo, "avatar_shape")
            num(self.avatar_size_spin, "avatar_size")
            num(self.avatar_radius_slider, "avatar_radius")
            color(self.avatar_border_color_btn, "avatar_border_color")
            num(self.avatar_border_size_slider, "avatar_border_size")
            num(self.volume_slider, "audio_volume")
            num(self.audio_speed_slider, "audio_speed")
            combo(self.easing_combo, "easing")
            num(self.cam_elev_slider, "cam_elev")
            num(self.cam_dist_slider, "cam_dist")
            num(self.cams_slider, "cam_side")
            num(self.cam_ahead_slider, "cam_ahead")
            num(self.cam_focus_slider, "cam_focus")
            num(self.fov_slider, "fov")
            color(self.tower_color_btn, "tower_color")
            color(self.plate_color_btn, "plate_color")
            text(self.vpre_edit, "value_prefix")
            text(self.vsu_edit, "value_suffix")
            num(self.vdec_spin, "value_decimals")
            combo(self.scale_combo, "scale_mode")
            combo(self.compact_combo, "value_compact")
            check(self.autoframe_check, "auto_frame")
            check(self.spot_check, "spotlight")
            color(self.skytop_color_btn, "sky_top")
            color(self.skybot_color_btn, "sky_bottom")
            color(self.ground_color_btn, "ground_color")
            color(self.skyline_color_btn, "skyline_color")
            num(self.rank_size_spin, "rank_size")
            color(self.rank_color_btn, "rank_color")
            num(self.name_size_spin, "name_size")
            color(self.name_color_btn, "name_color")
            num(self.value_size_spin, "value_size")
            color(self.value_color_btn, "value_color")
            num(self.text_size_spin, "text_size")
            color(self.text_color_btn, "text_color")
            num(self.extra_size_spin, "extra_size")
            color(self.extra_color_btn, "extra_color")

            if "bg_image" in d:
                self._bg_image_path = str(d["bg_image"])
                has = bool(self._bg_image_path)
                self.bg_image_label.setText(
                    os.path.basename(self._bg_image_path) if has else "none")
                self.bg_remove_btn.setEnabled(has)
            if "tower_image" in d:
                self._tower_img_path = str(d["tower_image"])
                self._refresh_tower_image_ui()
            if "canvas_image" in d:
                self._canvas_img_path = str(d["canvas_image"])
                self._refresh_canvas_image_ui()
            if "audio_file" in d:
                self._audio_path = str(d["audio_file"])
                has = bool(self._audio_path)
                self.audio_label.setText(
                    os.path.basename(self._audio_path) if has else "none")
                self.audio_remove_btn.setEnabled(has)
        finally:
            self._applying_template = False
        self.assets_sig = None
        self.update_preview()

    def _reset_to_defaults(self):
        """Return every visual control to the recommended starting look."""
        self.apply_template(curated_template(len(self.df)))

    def _save_template(self):
        name, ok = QInputDialog.getText(
            self, "Save Template", "Template name:", text="")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name.startswith("_"):
            name = "tpl" + name
        if store.template_exists(name):
            ans = QMessageBox.question(
                self, "Overwrite template",
                f"A template named '{name}' already exists.\nOverwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                return
        store.save_template(name, self.capture_template())
        QMessageBox.information(
            self, "Template saved",
            f"Saved template '{name}'.\nFind it any time under Templates → "
            "Browse / Apply Templates.")

    def _browse_templates(self):
        from ui.template_manager import TemplateManager
        dlg = TemplateManager(self, capture_fn=self.capture_template)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.chosen:
            action, name = dlg.chosen
            if action == "apply":
                self.apply_template(store.load_template(name))

    def _update_audio_speed_label(self, value):
        hint = ("slower" if value < 100 else
                "faster" if value > 100 else "normal")
        self.audio_speed_label.setText(f"Music speed: {value}%  ({hint})")

    # -------------------------------------------------------------- preview
    def _on_setting_changed(self, *_args):
        if getattr(self, "_applying_template", False):
            return
        self.update_preview()

    def _on_scrub(self, value):
        self.time_label.setText(f"{value // 10}%")
        self.update_preview()

    def update_preview(self):
        try:
            cfg = self.collect_config()
            self.preview_chip.setText(
                f"{cfg.width} × {cfg.height}   ·   {cfg.fps} fps")
            sig = cfg.asset_signature()
            if self.assets is None or sig != self.assets_sig:
                self.assets = build_assets(cfg, self.df)
                self.assets_sig = sig
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                         cfg.width, cfg.height)
            ctx = cairo.Context(surface)
            ctx.set_operator(cairo.OPERATOR_SOURCE)
            render_frame(ctx, cfg, self.df, self.assets,
                         self.scrubber.value() / 1000.0)
            surface.flush()
            img = QImage(surface.get_data(), cfg.width, cfg.height,
                         surface.get_stride(),
                         QImage.Format.Format_ARGB32_Premultiplied).copy()
            self.viewport.set_frame(img)
        except Exception as e:
            print(f"[preview error] {e}")
            self.preview_chip.setText("Preview unavailable")
            self.viewport.clear_frame()

    # ----------------------------------------------------------- playback
    def _play_start(self):
        if self.scrubber.value() >= 1000:
            self.scrubber.setValue(0)
        self.play_timer.start()

    def _play_tick(self):
        cfg_duration = max(1.0, self._video_duration())
        step = 1000.0 * 0.033 / cfg_duration
        val = self.scrubber.value() + step
        if val >= 1000:
            self.scrubber.setValue(1000)
            self.play_timer.stop()
        else:
            self._scrub_lock = True
            self.scrubber.setValue(int(val))
            self._scrub_lock = False

    # ------------------------------------------------------------- dialogs
    def _import_dataset(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import dataset", "",
            "Data files (*.csv *.xlsx *.xls);;All files (*)")
        if path:
            self._load_dataset_path(path)

    def _load_dataset_path(self, path):
        try:
            df = load_dataset(path)
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e))
            return
        self.df = df
        self.assets_sig = None
        self.file_label.setText(f"{os.path.basename(path)} ({len(df)} items)")
        self.topn_spin.setMaximum(max(1, len(df)))
        self.topn_spin.setValue(min(TOP_N, len(df)))
        self.update_preview()

    def _edit_data_table(self):
        from ui.table_editor import DatasetTableEditor
        dlg = DatasetTableEditor(self.df, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            df = dlg.result_df()
            if df is None or len(df) == 0:
                return
            self.df = df
            self.assets_sig = None
            self.file_label.setText(f"Edited dataset ({len(df)} items)")
            self.topn_spin.setMaximum(max(1, len(df)))
            self.topn_spin.setValue(min(TOP_N, len(df)))
            self.update_preview()

    # ------------------------------------------------------- tower image
    def _refresh_tower_image_ui(self):
        path = getattr(self, "_tower_img_path", "")
        has = bool(path)
        self.tower_image_label.setText(os.path.basename(path) if has else "none")
        self.tower_image_remove_btn.setEnabled(has)
        pm = QPixmap(path) if has and os.path.isfile(path) else QPixmap()
        if not pm.isNull():
            self.tower_image_thumb.setPixmap(pm.scaled(
                42, 42, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            self.tower_image_thumb.setText("")
            self.tower_image_thumb.setToolTip(path)
        else:
            self.tower_image_thumb.setPixmap(QPixmap())
            self.tower_image_thumb.setText("–")
            self.tower_image_thumb.setToolTip("No shared tower image")

    def _pick_tower_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Tower / bar image (replaces every tower)",
            store.get_last_image_dir(),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        store.set_last_image_dir(path)
        self._tower_img_path = path
        self._refresh_tower_image_ui()
        self.assets_sig = None
        self.update_preview()

    def _remove_tower_image(self):
        self._tower_img_path = ""
        self._refresh_tower_image_ui()
        self.assets_sig = None
        self.update_preview()

    # ------------------------------------------------------- canvas image
    def _refresh_canvas_image_ui(self):
        path = getattr(self, "_canvas_img_path", "")
        has = bool(path)
        self.canvas_image_label.setText(os.path.basename(path) if has else "none")
        self.canvas_image_remove_btn.setEnabled(has)
        pm = QPixmap(path) if has and os.path.isfile(path) else QPixmap()
        if not pm.isNull():
            self.canvas_image_thumb.setPixmap(pm.scaled(
                42, 42, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            self.canvas_image_thumb.setText("")
            self.canvas_image_thumb.setToolTip(path)
        else:
            self.canvas_image_thumb.setPixmap(QPixmap())
            self.canvas_image_thumb.setText("–")
            self.canvas_image_thumb.setToolTip("No full-canvas image")

    def _pick_canvas_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Canvas image (covers sky, skyline and ground)",
            store.get_last_image_dir(),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        store.set_last_image_dir(path)
        self._canvas_img_path = path
        self._refresh_canvas_image_ui()
        self.assets_sig = None
        self.update_preview()

    def _remove_canvas_image(self):
        self._canvas_img_path = ""
        self._refresh_canvas_image_ui()
        self.assets_sig = None
        self.update_preview()

    def _pick_bg_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Background image", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self._bg_image_path = path
            self.bg_image_label.setText(os.path.basename(path))
            self.bg_remove_btn.setEnabled(True)
            self.bg_mode_combo.setCurrentIndex(1)
            self.update_preview()

    def _remove_bg_image(self):
        self._bg_image_path = ""
        self.bg_image_label.setText("none")
        self.bg_remove_btn.setEnabled(False)
        self.bg_mode_combo.setCurrentIndex(0)
        self.update_preview()

    def _pick_audio(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Background music", "",
            "Audio (*.mp3 *.wav *.aac *.m4a);;All files (*)")
        if path:
            self._audio_path = path
            self.audio_label.setText(os.path.basename(path))
            self.audio_remove_btn.setEnabled(True)

    def _remove_audio(self):
        self._audio_path = ""
        self.audio_label.setText("none")
        self.audio_remove_btn.setEnabled(False)

    # ----------------------------------------------------------- drag/drop
    def _drop_urls(self, event):
        urls = []
        if event.mimeData().hasUrls():
            urls = [u.toLocalFile() for u in event.mimeData().urls()
                    if u.toLocalFile()]
        return urls

    def dragEnterEvent(self, event):
        if self._drop_urls(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        for path in self._drop_urls(event):
            ext = os.path.splitext(path)[1].lower()
            if ext in (".csv", ".xlsx", ".xls"):
                self._load_dataset_path(path)
            elif ext in (".png", ".jpg", ".jpeg"):
                self._bg_image_path = path
                self.bg_image_label.setText(os.path.basename(path))
                self.bg_remove_btn.setEnabled(True)
                self.bg_mode_combo.setCurrentIndex(1)
                self.update_preview()
            elif ext in (".mp3", ".wav", ".aac", ".m4a"):
                self._audio_path = path
                self.audio_label.setText(os.path.basename(path))
                self.audio_remove_btn.setEnabled(True)
            else:
                QMessageBox.warning(
                    self, "Unsupported file",
                    f"Cannot use '{os.path.basename(path)}'.\nDrop a CSV/Excel "
                    "dataset, a PNG/JPG background, or an audio file.")
        event.acceptProposedAction()

    # -------------------------------------------------------------- license
    def _refresh_license_ui(self):
        status = license_service.status()
        if not status.active:
            text = "License: inactive"
        elif status.info is not None and status.info.is_lifetime:
            text = "Lifetime license"
        else:
            left = status.videos_left
            text = f"1-Day · {left}/{status.max_videos} left"
        self.license_btn.setText(text)
        self.license_btn.setToolTip(
            f"{status.summary()}\n\nMachine ID: {status.machine_id}\n\n"
            "Click to view license details or enter a new key.")

    def _show_license(self):
        dialog = LicenseDialog(
            license_service.status(), self, allow_close=True)
        dialog.exec()
        self._refresh_license_ui()
        return license_service.status()

    def _ensure_license(self):
        """Return an active status, or None after explaining why not."""
        status = license_service.status()
        if not status.active:
            LicenseDialog(status, self, allow_close=True).exec()
            status = license_service.status()
        if not status.active:
            QMessageBox.warning(
                self, "License required",
                status.error
                or "A valid license is required to export videos.")
            return None
        if status.videos_left == 0:
            QMessageBox.warning(
                self, "Video limit reached",
                "Your 1-Day License has already used its "
                f"{status.max_videos} video exports.\n\n"
                "Request a new license key from the seller to export more "
                "videos.")
            return None
        return status

    # -------------------------------------------------------------- export
    def set_export_enabled(self, enabled):
        self.export_btn.setEnabled(enabled)

    def _default_video_folder(self):
        home = os.path.expanduser("~")
        videos = os.path.join(home, "Videos")
        return videos if os.path.isdir(videos) else home

    def _clean_name(self, text):
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", text)
        name = " ".join(name.split()).strip(" .")
        return name[:80] or "ranking_video"

    def _recompute_video_path(self):
        self._video_path = os.path.join(
            self._video_folder,
            self._clean_name(self.video_name_edit.text()) + ".mp4")
        self._refresh_video_path_ui()

    def _on_video_name_changed(self, *_):
        self._recompute_video_path()

    def _persist_video_path(self):
        store.set_video_save_path(self._video_path)

    def _refresh_video_path_ui(self):
        self.video_path_edit.setText(self._video_path)
        self.video_path_edit.setToolTip(self._video_path)
        self.video_path_edit.setCursorPosition(len(self._video_path))

    def _browse_video_path(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Choose where to save the video", self._video_path,
            "MP4 (*.mp4)")
        if not path:
            return
        if not path.lower().endswith(".mp4"):
            path += ".mp4"
        self._video_folder = os.path.dirname(path)
        self.video_name_edit.setText(os.path.splitext(os.path.basename(path))[0])
        self._recompute_video_path()
        self._persist_video_path()

    def _save_frame_png(self):
        if self.df is None or len(self.df) == 0:
            QMessageBox.warning(self, "No data",
                                "Please import a dataset first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save frame as PNG", "ranking_frame.png", "PNG (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            cfg = self.collect_config()
            sig = cfg.asset_signature()
            if self.assets is None or sig != self.assets_sig:
                self.assets = build_assets(cfg, self.df)
                self.assets_sig = sig
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                         cfg.width, cfg.height)
            ctx = cairo.Context(surface)
            ctx.set_operator(cairo.OPERATOR_SOURCE)
            render_frame(ctx, cfg, self.df, self.assets,
                         self.scrubber.value() / 1000.0)
            surface.flush()
            surface.write_to_png(path)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return
        QMessageBox.information(self, "Frame saved",
                                f"Still image saved to:\n{path}")

    def _start_export(self):
        if self.df is None or len(self.df) == 0:
            QMessageBox.warning(self, "No data",
                                "Please import a dataset first.")
            return
        if self.export_thread is not None and self.export_thread.isRunning():
            return
        if self._ensure_license() is None:
            return
        path = self._video_path
        if not path.lower().endswith(".mp4"):
            path += ".mp4"
        if os.path.isfile(path):
            ans = QMessageBox.question(
                self, "Overwrite file?",
                f"This file already exists:\n{path}\n\nOverwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                return
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            try:
                os.makedirs(parent, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(
                    self, "Export failed",
                    f"Cannot create folder:\n{parent}\n{e}")
                return
        cfg = self.collect_config()
        try:
            license_service.reserve_video()
        except license_service.LicenseError as exc:
            QMessageBox.warning(self, "Video limit reached", str(exc))
            self._refresh_license_ui()
            return
        self._refresh_license_ui()
        self.play_timer.stop()
        self.progress_bar.setValue(0)
        self.export_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.export_thread = VideoExportThread(cfg, self.df, path, self)
        self.export_thread.progress.connect(self.progress_bar.setValue)
        self.export_thread.finished_ok.connect(self._export_done)
        self.export_thread.failed.connect(self._export_failed)
        self.export_thread.start()

    def _cancel_export(self):
        if self.export_thread is not None:
            self.export_thread.cancel()

    def _export_done(self, path):
        self.export_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.progress_bar.setValue(100)
        QMessageBox.information(self, "Export complete",
                                f"Video saved to:\n{path}")

    def _export_failed(self, message):
        self.export_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        QMessageBox.critical(self, "Export failed", message)
