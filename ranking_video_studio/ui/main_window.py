import os

import cairo
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFileDialog,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSlider, QSpinBox, QSplitter, QVBoxLayout,
    QWidget,
)

from core.export_worker import VideoExportThread
from core.render_engine import build_assets, render_frame
from data.data_loader import load_dataset
from data.demo_data import get_demo_data
from ui.preview_viewport import PreviewViewport
from utils.config import (
    ENCODE_PRESETS, FPS_OPTIONS, QUALITY_PRESETS, RESOLUTIONS, RenderConfig,
)

EASING_OPTIONS = {
    "Smooth Deceleration (Cubic)": "cubic",
    "Elastic / Bounce": "elastic",
    "Exponential Dramatic": "exponential",
    "Linear Steady": "linear",
}
BG_MODES = {"Solid Color": "solid", "Gradient": "gradient", "Image": "image"}
BADGE_SHAPES = {"Pill": "pill", "Circle": "circle", "Plain Text": "text"}
AVATAR_SHAPES = {"Circle": "circle", "Rounded Square": "rounded",
                 "Square": "square"}


class ColorButton(QPushButton):
    """Button that shows its current color and opens a picker on click."""

    colorChanged = pyqtSignal()

    def __init__(self, rgb, parent=None):
        super().__init__(parent)
        self.rgb = tuple(rgb)
        self.setFixedHeight(30)
        self.setMinimumWidth(70)
        self.clicked.connect(self._pick)
        self._repaint()

    def _repaint(self):
        r, g, b = [int(c * 255) for c in self.rgb]
        self.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); border: 1px solid #666680;"
            f" border-radius: 6px;")

    def _pick(self):
        r, g, b = [int(c * 255) for c in self.rgb]
        col = QColorDialog.getColor(QColor(r, g, b), self, "Pick color")
        if col.isValid():
            self.rgb = (col.redF(), col.greenF(), col.blueF())
            self._repaint()
            self.colorChanged.emit()


def _row(*widgets, stretch_last=True):
    lay = QHBoxLayout()
    lay.setSpacing(8)
    for w in widgets:
        lay.addWidget(w)
    if stretch_last:
        lay.addStretch(1)
    return lay


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ranking Video Studio (2K Max)")
        self.resize(1400, 900)

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
        self.update_preview()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # ---------------- left panel ----------------
        left_holder = QWidget()
        left = QVBoxLayout(left_holder)
        left.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setFixedWidth(470)
        form = QVBoxLayout(inner)
        form.setSpacing(10)

        # 1. Dataset
        g = QGroupBox("1. Dataset")
        self.file_label = QLabel("Demo dataset (6 items)")
        self.file_label.setWordWrap(True)
        self.import_btn = QPushButton("Import CSV / Excel")
        self.import_btn.setToolTip("Load a .csv / .xlsx / .xls file with "
                                   "'name' and 'score' columns")
        gl = QVBoxLayout(g)
        gl.addWidget(self.file_label)
        gl.addWidget(self.import_btn)
        form.addWidget(g)

        # 2. Resolution & Quality
        g = QGroupBox("2. Resolution & Quality")
        gl = QVBoxLayout(g)
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
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(3, 120)
        self.duration_spin.setValue(8)
        self.duration_spin.setSuffix(" s")
        self.duration_spin.setToolTip("Video duration in seconds")
        gl.addLayout(_row(QLabel("Aspect / Resolution:"), self.aspect_combo))
        gl.addLayout(_row(QLabel("Quality:"), self.quality_combo))
        gl.addLayout(_row(QLabel("Frame rate:"), self.fps_combo))
        gl.addLayout(_row(QLabel("Duration:"), self.duration_spin))
        form.addWidget(g)

        # 3. Background & Canvas
        g = QGroupBox("3. Background & Canvas")
        gl = QVBoxLayout(g)
        self.title_edit = QLineEdit("TOP RANKINGS")
        self.title_edit.setToolTip("Video title shown at the top")
        self.bg_mode_combo = QComboBox()
        self.bg_mode_combo.addItems(BG_MODES.keys())
        self.bg_mode_combo.setCurrentIndex(1)
        self.bg_mode_combo.setToolTip("Background rendering mode")
        self.bg_color_btn = ColorButton((0.07, 0.07, 0.14))
        self.bg_color_btn.setToolTip("Solid color / gradient bottom color")
        self.bg_color2_btn = ColorButton((0.17, 0.10, 0.32))
        self.bg_color2_btn.setToolTip("Gradient top color")
        self.bg_image_btn = QPushButton("Background image...")
        self.bg_image_btn.setToolTip("PNG/JPG used when mode = Image")
        self.bg_image_label = QLabel("none")
        self.bg_image_label.setWordWrap(True)
        self.blur_slider = QSlider(Qt.Orientation.Horizontal)
        self.blur_slider.setRange(0, 30)
        self.blur_slider.setValue(10)
        self.blur_slider.setToolTip("Gaussian blur applied to background image")
        self.blur_label = QLabel("Blur: 10")
        self.dim_slider = QSlider(Qt.Orientation.Horizontal)
        self.dim_slider.setRange(0, 80)
        self.dim_slider.setValue(40)
        self.dim_slider.setToolTip("Darken background image (0-80%)")
        self.dim_label = QLabel("Dim: 40%")
        gl.addLayout(_row(QLabel("Title:"), self.title_edit))
        gl.addLayout(_row(QLabel("Mode:"), self.bg_mode_combo))
        gl.addLayout(_row(QLabel("Color 1:"), self.bg_color_btn,
                          QLabel("Color 2:"), self.bg_color2_btn))
        gl.addLayout(_row(self.bg_image_btn, self.bg_image_label))
        gl.addLayout(_row(self.blur_label, self.blur_slider))
        gl.addLayout(_row(self.dim_label, self.dim_slider))
        form.addWidget(g)

        # 4. Ranking Badges
        g = QGroupBox("4. Ranking Badges")
        gl = QVBoxLayout(g)
        self.badge_check = QCheckBox("Show rank numbers")
        self.badge_check.setChecked(True)
        self.badge_shape_combo = QComboBox()
        self.badge_shape_combo.addItems(BADGE_SHAPES.keys())
        self.badge_shape_combo.setToolTip("Shape behind the rank number")
        self.badge_color_btn = ColorButton((1.0, 0.76, 0.16))
        self.badge_color_btn.setToolTip("Badge background color")
        self.rank_color_btn = ColorButton((0.05, 0.05, 0.10))
        self.rank_color_btn.setToolTip("Rank number text color")
        self.rank_size_spin = QSpinBox()
        self.rank_size_spin.setRange(16, 48)
        self.rank_size_spin.setValue(28)
        self.rank_size_spin.setToolTip("Rank number font size (px)")
        gl.addWidget(self.badge_check)
        gl.addLayout(_row(QLabel("Shape:"), self.badge_shape_combo))
        gl.addLayout(_row(QLabel("Badge color:"), self.badge_color_btn,
                          QLabel("Text color:"), self.rank_color_btn))
        gl.addLayout(_row(QLabel("Font size:"), self.rank_size_spin))
        form.addWidget(g)

        # 5. Tiles, Avatars & Audio
        g = QGroupBox("5. Tiles, Avatars & Audio")
        gl = QVBoxLayout(g)
        self.bar_color_btn = ColorButton((0.16, 0.47, 0.89))
        self.bar_color_btn.setToolTip("Vector bar color")
        self.tile_btn = QPushButton("Custom tile PNG...")
        self.tile_btn.setToolTip("Replace vector bars with a PNG texture")
        self.tile_label = QLabel("vector bars")
        self.tile_label.setWordWrap(True)
        self.radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.radius_slider.setRange(0, 40)
        self.radius_slider.setValue(16)
        self.radius_slider.setToolTip("Corner rounding in px")
        self.radius_label = QLabel("Radius: 16")
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(20, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setToolTip("Tile opacity (20-100%)")
        self.opacity_label = QLabel("Opacity: 100%")
        self.tint_check = QCheckBox("Color tint")
        self.tint_check.setToolTip("Overlay a translucent color on tiles")
        self.tint_color_btn = ColorButton((0.2, 0.5, 1.0))
        self.shadow_check = QCheckBox("Drop shadow")
        self.shadow_check.setChecked(True)
        self.avatar_combo = QComboBox()
        self.avatar_combo.addItems(AVATAR_SHAPES.keys())
        self.avatar_combo.setToolTip("Avatar/logo crop shape")
        self.audio_btn = QPushButton("Background music...")
        self.audio_btn.setToolTip("MP3/WAV/AAC/M4A, looped and faded out")
        self.audio_label = QLabel("none")
        self.audio_label.setWordWrap(True)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(10, 150)
        self.volume_slider.setValue(100)
        self.volume_slider.setToolTip("Music volume (10-150%)")
        self.volume_label = QLabel("Volume: 100%")
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.25, 3.0)
        self.speed_spin.setSingleStep(0.25)
        self.speed_spin.setValue(1.0)
        self.speed_spin.setSuffix("x")
        self.speed_spin.setToolTip("Animation speed multiplier")
        self.easing_combo = QComboBox()
        self.easing_combo.addItems(EASING_OPTIONS.keys())
        self.easing_combo.setToolTip("Animation easing curve")
        gl.addLayout(_row(QLabel("Bar color:"), self.bar_color_btn))
        gl.addLayout(_row(self.tile_btn, self.tile_label))
        gl.addLayout(_row(self.radius_label, self.radius_slider))
        gl.addLayout(_row(self.opacity_label, self.opacity_slider))
        gl.addLayout(_row(self.tint_check, self.tint_color_btn))
        gl.addWidget(self.shadow_check)
        gl.addLayout(_row(QLabel("Avatar shape:"), self.avatar_combo))
        gl.addLayout(_row(self.audio_btn, self.audio_label))
        gl.addLayout(_row(self.volume_label, self.volume_slider))
        gl.addLayout(_row(QLabel("Speed:"), self.speed_spin))
        gl.addLayout(_row(QLabel("Easing:"), self.easing_combo))
        form.addWidget(g)

        # 6. Camera & Scene (Incline 3D Towers)
        g = QGroupBox("6. Camera & Scene (Incline 3D Towers)")
        gl = QVBoxLayout(g)
        self.camera_combo = QComboBox()
        self.camera_combo.addItems(["Flat 2D Bars", "Incline 3D Towers"])
        self.camera_combo.setToolTip("Flat bars or pseudo-3D tower scene")
        self.cammove_combo = QComboBox()
        self.cammove_combo.addItems([
            "Pan Reveal (track along row)", "Static Incline",
            "Slow Push-In", "Follow Leader"])
        self.cammove_combo.setToolTip("Camera movement (incline mode only)")
        self.camh_slider = QSlider(Qt.Orientation.Horizontal)
        self.camh_slider.setRange(15, 60)
        self.camh_slider.setValue(35)
        self.camh_slider.setToolTip("Camera eye height (1.5-6.0)")
        self.camh_label = QLabel("Camera Height: 3.5")
        self.cams_slider = QSlider(Qt.Orientation.Horizontal)
        self.cams_slider.setRange(5, 50)
        self.cams_slider.setValue(19)
        self.cams_slider.setToolTip("Lateral offset = incline angle (0.5-5.0)")
        self.cams_label = QLabel("Incline Angle: 1.9")
        self.fov_slider = QSlider(Qt.Orientation.Horizontal)
        self.fov_slider.setRange(80, 160)
        self.fov_slider.setValue(105)
        self.fov_slider.setToolTip("Zoom / field of view (0.8-1.6)")
        self.fov_label = QLabel("Zoom / FOV: 1.05")
        self.vpre_edit = QLineEdit("$ ")
        self.vpre_edit.setToolTip("Text before the tower value")
        self.vsu_edit = QLineEdit(" B")
        self.vsu_edit.setToolTip("Text after the tower value")
        self.vdec_spin = QSpinBox()
        self.vdec_spin.setRange(0, 3)
        self.vdec_spin.setValue(1)
        self.vdec_spin.setToolTip("Decimal places of the tower value")
        gl.addLayout(_row(QLabel("Camera Mode:"), self.camera_combo))
        gl.addLayout(_row(QLabel("Movement:"), self.cammove_combo))
        gl.addLayout(_row(self.camh_label, self.camh_slider))
        gl.addLayout(_row(self.cams_label, self.cams_slider))
        gl.addLayout(_row(self.fov_label, self.fov_slider))
        gl.addLayout(_row(QLabel("Value Prefix:"), self.vpre_edit,
                          QLabel("Suffix:"), self.vsu_edit))
        gl.addLayout(_row(QLabel("Value Decimals:"), self.vdec_spin))
        form.addWidget(g)

        # Export
        g = QGroupBox("Export")
        gl = QVBoxLayout(g)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.export_btn = QPushButton("Export Video to MP4")
        self.export_btn.setObjectName("exportBtn")
        self.cancel_btn = QPushButton("Cancel Export")
        self.cancel_btn.setVisible(False)
        gl.addWidget(self.progress_bar)
        gl.addWidget(self.export_btn)
        gl.addWidget(self.cancel_btn)
        form.addWidget(g)
        form.addStretch(1)

        scroll.setWidget(inner)
        left.addWidget(scroll)
        splitter.addWidget(left_holder)

        # ---------------- right panel ----------------
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 0, 0, 0)
        self.viewport = PreviewViewport()
        rl.addWidget(self.viewport, 1)

        self.scrubber = QSlider(Qt.Orientation.Horizontal)
        self.scrubber.setRange(0, 1000)
        self.scrubber.setValue(1000)
        self.scrubber.setToolTip("Timeline scrubber (0-100% of animation)")
        self.time_label = QLabel("100%")
        ctrl = QHBoxLayout()
        self.play_btn = QPushButton("▶ Test Play")
        self.play_btn.setObjectName("playBtn")
        self.pause_btn = QPushButton("⏸ Pause")
        self.reset_btn = QPushButton("⏮ Reset")
        self.end_btn = QPushButton("⏭ End")
        ctrl.addWidget(self.play_btn)
        ctrl.addWidget(self.pause_btn)
        ctrl.addWidget(self.reset_btn)
        ctrl.addWidget(self.end_btn)
        ctrl.addWidget(self.scrubber, 1)
        ctrl.addWidget(self.time_label)
        rl.addLayout(ctrl)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([480, 900])

    # ------------------------------------------------------------- signals
    def _connect_signals(self):
        self.import_btn.clicked.connect(self._import_dataset)
        self.bg_image_btn.clicked.connect(self._pick_bg_image)
        self.tile_btn.clicked.connect(self._pick_tile)
        self.audio_btn.clicked.connect(self._pick_audio)

        simple = [
            self.title_edit.textChanged,
            self.aspect_combo.currentIndexChanged,
            self.quality_combo.currentIndexChanged,
            self.fps_combo.currentIndexChanged,
            self.duration_spin.valueChanged,
            self.bg_mode_combo.currentIndexChanged,
            self.blur_slider.valueChanged,
            self.dim_slider.valueChanged,
            self.badge_check.toggled,
            self.badge_shape_combo.currentIndexChanged,
            self.rank_size_spin.valueChanged,
            self.radius_slider.valueChanged,
            self.opacity_slider.valueChanged,
            self.tint_check.toggled,
            self.shadow_check.toggled,
            self.avatar_combo.currentIndexChanged,
            self.volume_slider.valueChanged,
            self.speed_spin.valueChanged,
            self.easing_combo.currentIndexChanged,
            self.camera_combo.currentIndexChanged,
            self.cammove_combo.currentIndexChanged,
            self.camh_slider.valueChanged,
            self.cams_slider.valueChanged,
            self.fov_slider.valueChanged,
            self.vpre_edit.textChanged,
            self.vsu_edit.textChanged,
            self.vdec_spin.valueChanged,
        ]
        for sig in simple:
            sig.connect(self._on_setting_changed)
        for btn in (self.bg_color_btn, self.bg_color2_btn, self.badge_color_btn,
                    self.rank_color_btn, self.bar_color_btn, self.tint_color_btn):
            btn.colorChanged.connect(self._on_setting_changed)

        self.blur_slider.valueChanged.connect(
            lambda v: self.blur_label.setText(f"Blur: {v}"))
        self.dim_slider.valueChanged.connect(
            lambda v: self.dim_label.setText(f"Dim: {v}%"))
        self.radius_slider.valueChanged.connect(
            lambda v: self.radius_label.setText(f"Radius: {v}"))
        self.opacity_slider.valueChanged.connect(
            lambda v: self.opacity_label.setText(f"Opacity: {v}%"))
        self.volume_slider.valueChanged.connect(
            lambda v: self.volume_label.setText(f"Volume: {v}%"))
        self.camh_slider.valueChanged.connect(
            lambda v: self.camh_label.setText(f"Camera Height: {v / 10:.1f}"))
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
        self.cancel_btn.clicked.connect(self._cancel_export)

    # -------------------------------------------------------------- config
    def collect_config(self):
        cfg = RenderConfig()
        cfg.width, cfg.height = RESOLUTIONS[self.aspect_combo.currentText()]
        cfg.crf = QUALITY_PRESETS[self.quality_combo.currentText()]
        cfg.fps = FPS_OPTIONS[self.fps_combo.currentIndex()]
        cfg.duration = float(self.duration_spin.value())
        cfg.title = self.title_edit.text()
        cfg.bg_mode = BG_MODES[self.bg_mode_combo.currentText()]
        cfg.bg_color = self.bg_color_btn.rgb
        cfg.bg_color2 = self.bg_color2_btn.rgb
        cfg.bg_image = getattr(self, "_bg_image_path", "")
        cfg.bg_blur = self.blur_slider.value()
        cfg.bg_dim = self.dim_slider.value()
        cfg.bar_color = self.bar_color_btn.rgb
        cfg.tile_image = getattr(self, "_tile_path", "")
        cfg.tile_radius = self.radius_slider.value()
        cfg.tile_opacity = self.opacity_slider.value()
        cfg.tint_enabled = self.tint_check.isChecked()
        cfg.tint_color = self.tint_color_btn.rgb
        cfg.shadow_enabled = self.shadow_check.isChecked()
        cfg.avatar_shape = AVATAR_SHAPES[self.avatar_combo.currentText()]
        cfg.show_badges = self.badge_check.isChecked()
        cfg.badge_shape = BADGE_SHAPES[self.badge_shape_combo.currentText()]
        cfg.badge_color = self.badge_color_btn.rgb
        cfg.rank_color = self.rank_color_btn.rgb
        cfg.rank_font_size = self.rank_size_spin.value()
        cfg.audio_file = getattr(self, "_audio_path", "")
        cfg.audio_volume = self.volume_slider.value()
        cfg.speed = self.speed_spin.value()
        cfg.easing = EASING_OPTIONS[self.easing_combo.currentText()]
        cfg.camera_mode = "incline" if self.camera_combo.currentIndex() == 1 else "flat"
        cfg.camera_move = ["pan", "static", "push", "follow"][
            self.cammove_combo.currentIndex()]
        cfg.cam_height = self.camh_slider.value() / 10.0
        cfg.cam_side = self.cams_slider.value() / 10.0
        cfg.cam_fov = self.fov_slider.value() / 100.0
        cfg.value_prefix = self.vpre_edit.text()
        cfg.value_suffix = self.vsu_edit.text()
        cfg.value_decimals = self.vdec_spin.value()
        return cfg

    # -------------------------------------------------------------- preview
    def _on_setting_changed(self, *_args):
        self.update_preview()

    def _on_scrub(self, value):
        self.time_label.setText(f"{value // 10}%")
        self.update_preview()

    def update_preview(self):
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
            img = QImage(surface.get_data(), cfg.width, cfg.height,
                         surface.get_stride(),
                         QImage.Format.Format_ARGB32_Premultiplied).copy()
            self.viewport.set_frame(img)
        except Exception as e:
            print(f"[preview error] {e}")
            self.viewport.clear_frame()

    # ----------------------------------------------------------- playback
    def _play_start(self):
        if self.scrubber.value() >= 1000:
            self.scrubber.setValue(0)
        self.play_timer.start()

    def _play_tick(self):
        cfg_duration = max(1.0, float(self.duration_spin.value()))
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
        if not path:
            return
        try:
            df = load_dataset(path)
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e))
            return
        self.df = df
        self.assets_sig = None
        self.file_label.setText(f"{os.path.basename(path)} ({len(df)} items)")
        self.update_preview()

    def _pick_bg_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Background image", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self._bg_image_path = path
            self.bg_image_label.setText(os.path.basename(path))
            self.bg_mode_combo.setCurrentIndex(2)
            self.update_preview()

    def _pick_tile(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Custom tile image", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self._tile_path = path
            self.tile_label.setText(os.path.basename(path))
            self.update_preview()

    def _pick_audio(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Background music", "",
            "Audio (*.mp3 *.wav *.aac *.m4a);;All files (*)")
        if path:
            self._audio_path = path
            self.audio_label.setText(os.path.basename(path))

    # -------------------------------------------------------------- export
    def set_export_enabled(self, enabled):
        self.export_btn.setEnabled(enabled)

    def _start_export(self):
        if self.df is None or len(self.df) == 0:
            QMessageBox.warning(self, "No data",
                                "Please import a dataset first.")
            return
        if self.export_thread is not None and self.export_thread.isRunning():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export video", "ranking_video.mp4", "MP4 (*.mp4)")
        if not path:
            return
        if not path.lower().endswith(".mp4"):
            path += ".mp4"
        cfg = self.collect_config()
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
