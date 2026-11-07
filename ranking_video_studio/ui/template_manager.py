"""Searchable template manager: save the current look, then find and re-apply
saved templates without re-selecting every control. Rename/delete stay here;
applying returns the chosen name to the caller."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from data import state_store as store
from ui import styles


def _fmt_time(iso):
    return str(iso).replace("T", " ")[:16]


def _clean_name(name):
    name = str(name).strip()
    return "tpl" + name if name.startswith("_") else name


class TemplateManager(QDialog):
    """Find templates by name and manage them (CRUD + apply).

    After exec(), `chosen` is ("apply", name) when the user applied one.
    `capture_fn` (optional) returns the caller's current settings dict so the
    dialog can save the live look as a new template.
    """

    def __init__(self, parent=None, capture_fn=None):
        super().__init__(parent)
        self.setWindowTitle("Template Manager")
        self.resize(780, 540)
        self.capture_fn = capture_fn
        self.chosen = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("Templates")
        f = QFont()
        f.setPointSize(13)
        f.setBold(True)
        title.setFont(f)
        head.addWidget(title)
        head.addStretch(1)
        self.total_label = QLabel()
        self.total_label.setObjectName("countLabel")
        head.addWidget(self.total_label)
        root.addLayout(head)

        hint = QLabel("A template remembers every setting — camera, colors, "
                      "fonts, badges, images, title and background — so you can "
                      "reuse the same look on any dataset.")
        hint.setWordWrap(True)
        hint.setObjectName("hintLabel")
        root.addWidget(hint)

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Find templates by name…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(lambda _t: self._refresh())
        search_row.addWidget(self.search_edit, 1)
        self.match_label = QLabel()
        self.match_label.setObjectName("hintLabel")
        search_row.addWidget(self.match_label)
        root.addLayout(search_row)

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
        self.table.setColumnWidth(1, 80)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 170)
        self.table.doubleClicked.connect(lambda _i: self._apply())
        self.table.itemSelectionChanged.connect(self._sync_buttons)
        root.addWidget(self.table, 1)

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

    # ----------------------------------------------------------------- list
    def _refresh(self):
        metas = store.list_templates()
        self.total_label.setText(f"{len(metas)} saved")
        query = self.search_edit.text().strip().lower()
        shown = [m for m in metas if query in m["name"].lower()] if query else metas
        self.match_label.setText(f"{len(shown)} match" if query else "")
        selected = self._selected_name()
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
        if selected:
            for r in range(self.table.rowCount()):
                if self._name_at(r) == selected:
                    self.table.selectRow(r)
                    break
        self._sync_buttons()

    def _name_at(self, row):
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _selected_name(self):
        rows = self.table.selectionModel().selectedRows()
        return self._name_at(rows[0].row()) if rows else None

    def _sync_buttons(self):
        has = self._selected_name() is not None
        self.apply_btn.setEnabled(has)
        self.rename_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    def _set_status(self, text, error=False):
        self.status_label.setText(text)
        styles.set_prop(self.status_label, "error", "true" if error else "false")

    # ----------------------------------------------------------------- CRUD
    def _apply(self):
        name = self._selected_name()
        if not name:
            self._set_status("Select a template to apply", error=True)
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
        for r in range(self.table.rowCount()):
            if self._name_at(r) == name:
                self.table.selectRow(r)
                break
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
        store.delete_template(name)
        self._refresh()
        self._set_status(f"Deleted template '{name}'")