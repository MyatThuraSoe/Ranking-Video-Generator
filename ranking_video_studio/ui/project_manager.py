"""Searchable project manager: create, open, rename and delete projects."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from data import state_store as store
from ui import styles


def _blank_row():
    return {"name": "", "score": "0", "text": "", "image": "", "extratext": ""}


def _fmt_time(iso):
    return str(iso).replace("T", " ")[:16]


class ProjectManager(QDialog):
    """Find projects by name and manage them (CRUD).

    After exec(), `chosen` is ("open"|"new", name) when the user picked an
    action that returns to the editor; rename/delete stay inside the dialog.
    `renamed_from` / `renamed_to` report a rename of the caller's project.
    """

    def __init__(self, current_name=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Project Manager")
        self.resize(780, 540)
        self.current_name = current_name
        self.chosen = None
        self.renamed_from = None
        self.renamed_to = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("Projects")
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

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Find projects by name…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(lambda _t: self._refresh())
        search_row.addWidget(self.search_edit, 1)
        self.match_label = QLabel()
        self.match_label.setObjectName("hintLabel")
        search_row.addWidget(self.match_label)
        root.addLayout(search_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Project", "Rows", "Last saved"])
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
        self.table.setColumnWidth(2, 170)
        self.table.doubleClicked.connect(lambda _i: self._open())
        self.table.itemSelectionChanged.connect(self._sync_buttons)
        root.addWidget(self.table, 1)

        self.status_label = QLabel("Double-click a project to open it")
        self.status_label.setObjectName("statusLabel")
        styles.set_prop(self.status_label, "error", "false")
        root.addWidget(self.status_label)

        btns = QHBoxLayout()
        self.new_btn = QPushButton("+ New Project")
        self.rename_btn = QPushButton("Rename")
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("dangerBtn")
        btns.addWidget(self.new_btn)
        btns.addWidget(self.rename_btn)
        btns.addWidget(self.delete_btn)
        btns.addStretch(1)
        self.open_btn = QPushButton("Open Project")
        self.open_btn.setObjectName("exportBtn")
        self.close_btn = QPushButton("Close")
        btns.addWidget(self.open_btn)
        btns.addWidget(self.close_btn)
        root.addLayout(btns)

        self.new_btn.clicked.connect(self._new)
        self.rename_btn.clicked.connect(self._rename)
        self.delete_btn.clicked.connect(self._delete)
        self.open_btn.clicked.connect(self._open)
        self.close_btn.clicked.connect(self.reject)

        self._refresh()

    # ----------------------------------------------------------------- list
    def _refresh(self):
        metas = store.list_projects()
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
            if m["name"] == self.current_name:
                name_item.setText(m["name"] + "   (open in editor)")
                name_item.setData(Qt.ItemDataRole.UserRole, m["name"])
                fnt = name_item.font()
                fnt.setBold(True)
                name_item.setFont(fnt)
            else:
                name_item.setData(Qt.ItemDataRole.UserRole, m["name"])
            self.table.setItem(r, 0, name_item)
            rows_item = QTableWidgetItem(str(m["row_count"]))
            rows_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 1, rows_item)
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
        self.open_btn.setEnabled(has)
        self.rename_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    def _set_status(self, text, error=False):
        self.status_label.setText(text)
        styles.set_prop(self.status_label, "error", "true" if error else "false")

    # ----------------------------------------------------------------- CRUD
    def _open(self):
        name = self._selected_name()
        if not name:
            self._set_status("Select a project to open", error=True)
            return
        self.chosen = ("open", name)
        self.accept()

    def _new(self):
        name, ok = QInputDialog.getText(
            self, "New project", "Project name:", text="")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name.startswith("_"):
            name = "proj" + name
        if store.project_exists(name):
            self._set_status(f"A project named '{name}' already exists", error=True)
            return
        store.save_project(name, [_blank_row()])
        self.chosen = ("new", name)
        self.accept()

    def _rename(self):
        old = self._selected_name()
        if not old:
            return
        new, ok = QInputDialog.getText(
            self, "Rename project", f"New name for '{old}':", text=old)
        if not ok or not new.strip() or new.strip() == old:
            return
        new = new.strip()
        if new.startswith("_"):
            new = "proj" + new
        if not store.rename_project(old, new):
            self._set_status(f"A project named '{new}' already exists", error=True)
            return
        if old == self.current_name:
            self.renamed_from = old
            self.renamed_to = new
            self.current_name = new
        self._refresh()
        self._set_status(f"Renamed '{old}' to '{new}'")

    def _delete(self):
        name = self._selected_name()
        if not name:
            return
        ans = QMessageBox.question(
            self, "Delete project",
            f"Delete project '{name}' permanently?\nIts saved table cannot be recovered.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans != QMessageBox.StandardButton.Yes:
            return
        store.delete_project(name)
        self._refresh()
        self._set_status(f"Deleted project '{name}'")