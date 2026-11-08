"""Searchable template manager: save the current look, then find and re-apply
saved templates without re-selecting every control. Rename/delete stay here;
applying returns the chosen name to the caller.

Next to the list, an embedded-code panel shows the selected template as JSON.
The code can be read, edited and saved back, or imported/exported as .json or
.txt files."""
import json
import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QFileDialog, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from data import state_store as store
from ui import styles


def _fmt_time(iso):
    return str(iso).replace("T", " ")[:16]


def _clean_name(name):
    name = str(name).strip()
    return "tpl" + name if name.startswith("_") else name


class TemplateManager(QDialog):
    """Find templates by name and manage them (CRUD + apply + code editing).

    After exec(), `chosen` is ("apply", name) when the user applied one.
    `capture_fn` (optional) returns the caller's current settings dict so the
    dialog can save the live look as a new template.
    """

    def __init__(self, parent=None, capture_fn=None):
        super().__init__(parent)
        self.setWindowTitle("Template Manager")
        self.resize(1160, 620)
        self.setMinimumSize(920, 480)
        self.capture_fn = capture_fn
        self.chosen = None
        self._code_name = None
        self._code_dirty = False
        self._loading_code = False
        self._refreshing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("Templates")
        title.setObjectName("pageTitle")
        head.addWidget(title)
        head.addStretch(1)
        self.total_label = QLabel()
        self.total_label.setObjectName("countLabel")
        head.addWidget(self.total_label)
        root.addLayout(head)

        hint = QLabel("A template remembers every setting — camera, colors, "
                      "fonts, badges, images, title and background. Select one "
                      "to read or edit its embedded code on the right.")
        hint.setWordWrap(True)
        hint.setObjectName("hintLabel")
        root.addWidget(hint)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.addWidget(self._build_list_pane())
        split.addWidget(self._build_code_pane())
        split.setSizes([470, 650])
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        root.addWidget(split, 1)

        self.status_label = QLabel("Double-click a template to apply it")
        self.status_label.setObjectName("statusLabel")
        styles.set_prop(self.status_label, "error", "false")
        root.addWidget(self.status_label)

        btns = QHBoxLayout()
        self.save_btn = QPushButton("+ Save Current Look")
        self.save_btn.setToolTip("Save the settings currently in the editor as a template")
        self.rename_btn = QPushButton("Rename")
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("dangerBtn")
        btns.addWidget(self.save_btn)
        btns.addWidget(self.rename_btn)
        btns.addWidget(self.delete_btn)
        btns.addStretch(1)
        self.apply_btn = QPushButton("Apply Template")
        self.apply_btn.setObjectName("exportBtn")
        self.close_btn = QPushButton("Close")
        btns.addWidget(self.apply_btn)
        btns.addWidget(self.close_btn)
        root.addLayout(btns)

        self.save_btn.clicked.connect(self._save_current)
        self.rename_btn.clicked.connect(self._rename)
        self.delete_btn.clicked.connect(self._delete)
        self.apply_btn.clicked.connect(self._apply)
        self.close_btn.clicked.connect(self.reject)
        self.save_btn.setEnabled(capture_fn is not None)

        self._refresh()
        if self.table.rowCount():
            self.table.selectRow(0)

    # ------------------------------------------------------------- layout
    def _build_list_pane(self):
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Find templates by name…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(lambda _t: self._refresh())
        search_row.addWidget(self.search_edit, 1)
        self.match_label = QLabel()
        self.match_label.setObjectName("hintLabel")
        search_row.addWidget(self.match_label)
        lay.addLayout(search_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Template", "Settings", "Last saved"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 70)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 150)
        self.table.doubleClicked.connect(lambda _i: self._apply())
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        lay.addWidget(self.table, 1)
        return pane

    def _build_code_pane(self):
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        code_title = QLabel("Embedded Code")
        code_title.setObjectName("panelTitle")
        head.addWidget(code_title)
        self.code_for_label = QLabel("select a template")
        self.code_for_label.setObjectName("hintLabel")
        head.addWidget(self.code_for_label, 1)
        self.code_dirty_chip = QLabel("Saved")
        self.code_dirty_chip.setObjectName("projectChip")
        styles.set_prop(self.code_dirty_chip, "saved", "true")
        head.addWidget(self.code_dirty_chip)
        lay.addLayout(head)

        self.code_edit = QPlainTextEdit()
        self.code_edit.setObjectName("codeEditor")
        self.code_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.code_edit.setTabStopDistance(24)
        self.code_edit.setPlaceholderText(
            "Select a template to read its embedded code.\n"
            "The JSON object holds every setting — edit it here, then save.")
        self.code_edit.textChanged.connect(self._on_code_edited)
        lay.addWidget(self.code_edit, 1)

        self.code_status = QLabel()
        self.code_status.setObjectName("statusLabel")
        self.code_status.setWordWrap(True)
        styles.set_prop(self.code_status, "error", "false")
        self.code_status.setVisible(False)
        lay.addWidget(self.code_status)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        self.code_save_btn = QPushButton("Save Changes")
        self.code_save_btn.setObjectName("codeSaveBtn")
        self.code_save_btn.setToolTip("Validate the JSON and write it back to the template")
        self.code_revert_btn = QPushButton("Revert")
        self.code_revert_btn.setToolTip("Discard edits and reload the template from disk")
        self.code_copy_btn = QPushButton("Copy")
        self.code_copy_btn.setToolTip("Copy the code to the clipboard")
        self.code_import_btn = QPushButton("Import…")
        self.code_import_btn.setToolTip("Load code from a .json or .txt file into the editor")
        self.code_export_btn = QPushButton("Export…")
        self.code_export_btn.setToolTip("Write the code to a .json or .txt file")
        btns.addWidget(self.code_save_btn)
        btns.addWidget(self.code_revert_btn)
        btns.addWidget(self.code_copy_btn)
        btns.addStretch(1)
        btns.addWidget(self.code_import_btn)
        btns.addWidget(self.code_export_btn)
        lay.addLayout(btns)

        self.code_save_btn.clicked.connect(self._save_code)
        self.code_revert_btn.clicked.connect(self._revert_code)
        self.code_copy_btn.clicked.connect(self._copy_code)
        self.code_import_btn.clicked.connect(self._import_code)
        self.code_export_btn.clicked.connect(self._export_code)
        return pane

    # ----------------------------------------------------------------- list
    def _refresh(self):
        self._refreshing = True
        metas = store.list_templates()
        self.total_label.setText(f"{len(metas)} saved")
        query = self.search_edit.text().strip().lower()
        shown = [m for m in metas if query in m["name"].lower()] if query else metas
        self.match_label.setText(f"{len(shown)} match" if query else "")
        selected = self._selected_name()
        self.table.clearSelection()
        self.table.setRowCount(len(shown))
        for r, m in enumerate(shown):
            self.table.setRowHeight(r, 34)
            name_item = QTableWidgetItem(m["name"])
            name_item.setForeground(QColor(styles.current_palette()["title"]))
            name_item.setData(Qt.ItemDataRole.UserRole, m["name"])
            self.table.setItem(r, 0, name_item)
            count_item = QTableWidgetItem(str(m.get("field_count", 0)))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 1, count_item)
            self.table.setItem(r, 2, QTableWidgetItem(_fmt_time(m["updated_at"])))
        self.table.sortItems(2, Qt.SortOrder.DescendingOrder)
        prefer = self._code_name or selected
        if prefer:
            for r in range(self.table.rowCount()):
                if self._name_at(r) == prefer:
                    self.table.selectRow(r)
                    break
        self._refreshing = False
        self._sync_buttons()
        if self._code_name is None:
            if self._selected_name() is None and self.table.rowCount():
                self.table.selectRow(0)
            self._load_code(self._selected_name())

    def _name_at(self, row):
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _selected_name(self):
        rows = self.table.selectionModel().selectedRows()
        return self._name_at(rows[0].row()) if rows else None

    def _select_name(self, name):
        self.table.blockSignals(True)
        for r in range(self.table.rowCount()):
            if self._name_at(r) == name:
                self.table.selectRow(r)
                break
        self.table.blockSignals(False)
        self._sync_buttons()

    def _sync_buttons(self):
        has = self._selected_name() is not None
        self.apply_btn.setEnabled(has)
        self.rename_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    def _set_status(self, text, error=False):
        self.status_label.setText(text)
        styles.set_prop(self.status_label, "error", "true" if error else "false")

    # ---------------------------------------------------------- embedded code
    def _on_selection_changed(self):
        self._sync_buttons()
        if self._refreshing:
            return
        name = self._selected_name()
        if not self._switch_code(name):
            self._select_name(self._code_name)

    def _switch_code(self, name):
        """Bind the editor to `name`; returns False if the switch was cancelled."""
        if name == self._code_name:
            return True
        if self._code_dirty and self._code_name:
            old = self._code_name
            ans = QMessageBox.question(
                self, "Unsaved code changes",
                f"Save changes to '{old}' before switching templates?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)
            if ans == QMessageBox.StandardButton.Yes and not self._save_code():
                return False
        self._load_code(name)
        if name is not None and self._selected_name() != name:
            self._select_name(name)
        return True

    def _load_code(self, name):
        self._code_name = name
        self._loading_code = True
        if name is None:
            self.code_edit.clear()
            self.code_for_label.setText("select a template")
        else:
            settings = store.load_template(name)
            self.code_edit.setPlainText(
                json.dumps(settings, indent=2, ensure_ascii=False))
            self.code_for_label.setText(f"for '{name}'")
        self._loading_code = False
        self._code_dirty = False
        self.code_edit.setEnabled(name is not None)
        self.code_dirty_chip.setVisible(name is not None)
        self._set_code_status("")
        self._sync_code_buttons()

    def _on_code_edited(self):
        if self._loading_code or self._code_name is None:
            return
        self._code_dirty = True
        self._update_code_chip()
        self._sync_code_buttons()

    def _update_code_chip(self):
        self.code_dirty_chip.setText(
            "Unsaved changes" if self._code_dirty else "Saved")
        styles.set_prop(self.code_dirty_chip, "saved",
                        "false" if self._code_dirty else "true")

    def _sync_code_buttons(self):
        has = self._code_name is not None
        self.code_save_btn.setEnabled(has and self._code_dirty)
        self.code_revert_btn.setEnabled(has and self._code_dirty)
        self.code_copy_btn.setEnabled(has)
        self.code_import_btn.setEnabled(has)
        self.code_export_btn.setEnabled(has)

    def _set_code_status(self, text, error=False):
        self.code_status.setText(text)
        self.code_status.setVisible(bool(text))
        styles.set_prop(self.code_status, "error", "true" if error else "false")

    def _save_code(self):
        name = self._code_name
        if not name:
            return False
        try:
            data = json.loads(self.code_edit.toPlainText())
        except json.JSONDecodeError as e:
            self._set_code_status(
                f"Invalid JSON — line {e.lineno}, column {e.colno}: {e.msg}",
                error=True)
            return False
        if isinstance(data, dict) and isinstance(data.get("settings"), dict):
            data = data["settings"]
        if not isinstance(data, dict):
            self._set_code_status(
                "Template code must be a JSON object { … }", error=True)
            return False
        store.save_template(name, data)
        self._code_dirty = False
        self._update_code_chip()
        self._sync_code_buttons()
        self._set_code_status(f"Saved changes to '{name}'")
        self._refresh()
        return True

    def _revert_code(self):
        name = self._code_name
        if not name:
            return
        if self._code_dirty:
            ans = QMessageBox.question(
                self, "Revert code",
                f"Discard unsaved changes and reload '{name}' from disk?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                return
        self._load_code(name)
        self._set_code_status(f"Reloaded '{name}' from disk")

    def _copy_code(self):
        if self._code_name is None:
            return
        QApplication.clipboard().setText(self.code_edit.toPlainText())
        self._set_code_status("Code copied to clipboard")

    def _import_code(self):
        if self._code_name is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import template code", "",
            "Template code (*.json *.txt);;All files (*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                text = f.read()
        except OSError as e:
            self._set_code_status(f"Could not read file: {e}", error=True)
            return
        self.code_edit.setPlainText(text)
        self._set_code_status(
            f"Imported '{os.path.basename(path)}' — review, then Save Changes")

    def _export_code(self):
        name = self._code_name
        if not name:
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self, "Export template code", f"{name}.json",
            "JSON (*.json);;Text (*.txt)")
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += ".txt" if "Text" in selected_filter else ".json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.code_edit.toPlainText())
        except OSError as e:
            self._set_code_status(f"Could not write file: {e}", error=True)
            return
        self._set_code_status(f"Exported code to '{os.path.basename(path)}'")

    # ----------------------------------------------------------------- CRUD
    def _apply(self):
        name = self._selected_name()
        if not name:
            self._set_status("Select a template to apply", error=True)
            return
        if self._code_dirty and self._code_name == name:
            ans = QMessageBox.question(
                self, "Unsaved code changes",
                f"Save code changes to '{name}' before applying?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)
            if ans == QMessageBox.StandardButton.Yes and not self._save_code():
                return
        self.chosen = ("apply", name)
        self.accept()

    def _save_current(self):
        if self.capture_fn is None:
            return
        name, ok = QInputDialog.getText(
            self, "Save Template", "Template name:", text="")
        if not ok or not name.strip():
            return
        name = _clean_name(name)
        if store.template_exists(name):
            ans = QMessageBox.question(
                self, "Overwrite template",
                f"A template named '{name}' already exists.\nOverwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                return
        store.save_template(name, self.capture_fn())
        self._refresh()
        self._select_name(name)
        if not self._switch_code(name):
            self._select_name(self._code_name)
        self._set_status(f"Saved current look as '{name}'")

    def _rename(self):
        old = self._selected_name()
        if not old:
            return
        new, ok = QInputDialog.getText(
            self, "Rename template", f"New name for '{old}':", text=old)
        if not ok or not new.strip() or new.strip() == old:
            return
        new = _clean_name(new)
        if not store.rename_template(old, new):
            self._set_status(f"A template named '{new}' already exists", error=True)
            return
        if self._code_name == old:
            self._code_name = new
            self.code_for_label.setText(f"for '{new}'")
        self._refresh()
        self._set_status(f"Renamed '{old}' to '{new}'")

    def _delete(self):
        name = self._selected_name()
        if not name:
            return
        ans = QMessageBox.question(
            self, "Delete template",
            f"Delete template '{name}' permanently?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans != QMessageBox.StandardButton.Yes:
            return
        if self._code_name == name:
            self._code_name = None
            self._code_dirty = False
        store.delete_template(name)
        self._refresh()
        self._set_status(f"Deleted template '{name}'")

    def reject(self):
        if self._code_dirty and self._code_name:
            ans = QMessageBox.question(
                self, "Unsaved code changes",
                f"Save changes to '{self._code_name}' before closing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes)
            if ans == QMessageBox.StandardButton.Cancel:
                return
            if ans == QMessageBox.StandardButton.Yes and not self._save_code():
                return
        super().reject()