"""Activation / license-status dialog shown before the main window opens."""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from ui import styles
from utils import license as license_service
from utils.app_paths import logo_path

_STEPS = (
    "1.  Copy your Machine ID and send it to the seller on social media.\n"
    "2.  Paste the license key you receive into the box below.\n"
    "3.  Click Activate. A 1-Day key allows 2 video exports within 24 hours "
    "of issue; a Lifetime key never expires."
)


class LicenseDialog(QDialog):
    """Activation window.

    With ``allow_close=False`` (first launch) rejecting the dialog means the
    application must exit.  With ``allow_close=True`` it doubles as the
    in-app License status window and the user can simply close it.
    """

    def __init__(self, status=None, parent=None, allow_close=False):
        super().__init__(parent)
        self._status = status or license_service.status()
        self._allow_close = allow_close
        self.activated_status = None

        self.setWindowTitle("LRBar-RankGen License")
        self.setModal(True)
        self.setMinimumWidth(660)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        logo = logo_path()
        if logo:
            self.setWindowIcon(QIcon(logo))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(26, 22, 26, 20)
        outer.setSpacing(14)

        outer.addLayout(self._build_header(logo))
        outer.addWidget(self._build_summary())
        outer.addWidget(self._build_machine_row())

        steps = QLabel(_STEPS)
        steps.setObjectName("hintLabel")
        steps.setWordWrap(True)
        steps.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(steps)

        outer.addWidget(self._build_key_field())
        outer.addWidget(self._build_message())
        outer.addLayout(self._build_buttons())

        self._copy_timer = QTimer(self)
        self._copy_timer.setSingleShot(True)
        self._copy_timer.timeout.connect(
            lambda: self.machine_copy_btn.setText("Copy ID"))

        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        shortcut.activated.connect(self._activate)
        self.key_edit.setFocus()

    # ------------------------------------------------------------- building
    def _build_header(self, logo):
        row = QHBoxLayout()
        row.setSpacing(14)
        mark = QLabel()
        mark.setObjectName("logoMark")
        mark.setFixedSize(46, 46)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if logo:
            pixmap = QIcon(logo).pixmap(46, 46)
            if not pixmap.isNull():
                mark.setPixmap(pixmap)
            else:
                mark.setText("LR")
        else:
            mark.setText("LR")
        row.addWidget(mark)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("Activate LRBar-RankGen")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "This copy is licensed to one computer. Activation is offline "
            "and takes a few seconds.")
        subtitle.setObjectName("hintLabel")
        subtitle.setWordWrap(True)
        titles.addWidget(title)
        titles.addWidget(subtitle)
        row.addLayout(titles, 1)
        return row

    def _build_summary(self):
        label = QLabel(self._status.summary())
        label.setObjectName("licenseSummary")
        label.setWordWrap(True)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        styles.set_prop(label, "active", "true" if self._status.active else "false")
        self.summary_label = label
        return label

    def _build_machine_row(self):
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        caption = QLabel("Your Machine ID")
        caption.setObjectName("fieldLabel")
        caption.setFixedWidth(124)

        self.machine_edit = QLineEdit(self._status.machine_id)
        self.machine_edit.setReadOnly(True)
        self.machine_edit.setCursorPosition(0)
        self.machine_edit.setFont(styles.mono_font(11))
        self.machine_edit.setToolTip(
            "Send this ID to the seller exactly as shown.")

        self.machine_copy_btn = QPushButton("Copy ID")
        self.machine_copy_btn.setToolTip("Copy the Machine ID to the clipboard")
        self.machine_copy_btn.clicked.connect(self._copy_machine_id)

        layout.addWidget(caption)
        layout.addWidget(self.machine_edit, 1)
        layout.addWidget(self.machine_copy_btn)
        return box

    def _build_key_field(self):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        head = QHBoxLayout()
        caption = QLabel("License key")
        caption.setObjectName("fieldLabel")
        head.addWidget(caption)
        head.addStretch(1)
        paste_btn = QPushButton("Paste from clipboard")
        paste_btn.setToolTip("Paste the key you received from the seller")
        paste_btn.clicked.connect(self._paste_key)
        head.addWidget(paste_btn)
        layout.addLayout(head)

        self.key_edit = QPlainTextEdit()
        self.key_edit.setPlaceholderText(
            "Paste the complete license key here (it starts with LRBG1.)")
        self.key_edit.setFixedHeight(96)
        self.key_edit.setFont(styles.mono_font(9))
        self.key_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.key_edit.textChanged.connect(self._on_key_changed)
        layout.addWidget(self.key_edit)
        return box

    def _build_message(self):
        self.message_label = QLabel("")
        self.message_label.setObjectName("statusLabel")
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        styles.set_prop(self.message_label, "error", "true")
        self.message_label.setVisible(False)
        return self.message_label

    def _build_buttons(self):
        row = QHBoxLayout()
        row.setSpacing(10)
        self.cancel_btn = QPushButton(
            "Close" if self._allow_close else "Exit")
        self.cancel_btn.clicked.connect(self.reject)
        row.addWidget(self.cancel_btn)
        row.addStretch(1)

        self.activate_btn = QPushButton(
            "Activate New Key" if self._allow_close else "Activate License")
        self.activate_btn.setObjectName("exportBtn")
        self.activate_btn.setDefault(True)
        self.activate_btn.setEnabled(False)
        self.activate_btn.clicked.connect(self._activate)
        row.addWidget(self.activate_btn)
        return row

    # -------------------------------------------------------------- actions
    def _copy_machine_id(self):
        QApplication.clipboard().setText(self._status.machine_id)
        self.machine_copy_btn.setText("Copied ✓")
        self._copy_timer.start(1600)

    def _paste_key(self):
        text = QApplication.clipboard().text()
        if text:
            self.key_edit.setPlainText(text)

    def _on_key_changed(self):
        has_key = bool(license_service.normalize_key(
            self.key_edit.toPlainText()))
        self.activate_btn.setEnabled(has_key)

    def _set_message(self, text, error=True):
        self.message_label.setText(text)
        styles.set_prop(self.message_label, "error", "true" if error else "false")
        self.message_label.setVisible(bool(text))

    def _activate(self):
        raw = self.key_edit.toPlainText()
        if not license_service.normalize_key(raw):
            self._set_message("Paste your license key first.", True)
            return
        try:
            self._status = license_service.activate(raw)
        except license_service.LicenseError as exc:
            self._set_message(str(exc), True)
            return
        except Exception as exc:  # never crash on activation
            self._set_message(
                f"License activation failed unexpectedly:\n{exc}", True)
            return

        self.activated_status = self._status
        self._set_message("License activated. Thank you!", False)
        self.accept()
