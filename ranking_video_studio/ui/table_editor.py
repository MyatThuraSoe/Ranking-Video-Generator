"""Editable dataset table with autosave and named project states."""
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from data import state_store as store
from data.data_loader import load_dataset
from ui import styles
from utils.config import MAX_ROWS

HEADERS = ["#", "Name", "Score", "Text", "Image", "Extra Text"]
COL_RANK, COL_NAME, COL_SCORE, COL_TEXT, COL_IMAGE, COL_EXTRA = range(6)


class DatasetTableEditor(QDialog):
    """Edit name / score / text / image / extraText rows.

    Every change is auto-saved; named states let the user keep separate
    projects. Image pickers reopen in the last folder an image came from.
    """

    def __init__(self, df, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dataset Table Editor")
        self.resize(1080, 660)
        self._records = store.df_to_records(df)
        self._loading = False
        self._result_df = None
        self._project_name = None

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(350)
        self._save_timer.timeout.connect(self._flush_autosave)

        self._build_ui()
        self._populate()
        self._update_project_chip()
        ts = store.autosave_time()
        if ts:
            self._set_status(f"Last session auto-saved {ts} — use Restore Last Session")

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("Dataset Table Editor")
        title.setObjectName("pageTitle")
        head.addWidget(title)
        self.project_chip = QLabel()
        self.project_chip.setObjectName("projectChip")
        head.addWidget(self.project_chip)
        head.addStretch(1)
        self.count_label = QLabel()
        self.count_label.setObjectName("countLabel")
        head.addWidget(self.count_label)
        root.addLayout(head)

        bar = QHBoxLayout()
        self.import_btn = QPushButton("Import CSV / Excel")
        self.import_btn.setToolTip("Replace the table with a .csv / .xlsx file "
                                   f"(max {MAX_ROWS} rows; row order = ranking)")
        self.export_btn = QPushButton("Export CSV")
        self.export_btn.setToolTip("Save the current table as a .csv file")
        self.add_btn = QPushButton("+ Add Row")
        self.del_btn = QPushButton("Delete Selected")
        self.up_btn = QPushButton("Move Up")
        self.down_btn = QPushButton("Move Down")
        for b in (self.import_btn, self.export_btn, self.add_btn,
                  self.del_btn, self.up_btn, self.down_btn):
            bar.addWidget(b)
        bar.addStretch(1)
        root.addLayout(bar)

        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(COL_RANK, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COL_RANK, 44)
        hh.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(COL_NAME, 170)
        hh.setSectionResizeMode(COL_SCORE, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COL_SCORE, 120)
        hh.setSectionResizeMode(COL_TEXT, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(COL_IMAGE, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COL_IMAGE, 250)
        hh.setSectionResizeMode(COL_EXTRA, QHeaderView.ResizeMode.Stretch)
        self.table.cellChanged.connect(self._cell_changed)
        root.addWidget(self.table, 1)

        state_bar = QHBoxLayout()
        self.status_label = QLabel("Edits auto-save as you type")
        self.status_label.setObjectName("statusLabel")
        styles.set_prop(self.status_label, "error", "false")
        state_bar.addWidget(self.status_label)
        state_bar.addStretch(1)
        self.restore_btn = QPushButton("Restore Last Session")
        self.restore_btn.setToolTip("Reload the most recent auto-saved table")
        self.save_btn = QPushButton("Save")
        self.save_btn.setToolTip("Save the table into the current project (Ctrl+S)")
        self.saveas_btn = QPushButton("Save As…")
        self.saveas_btn.setToolTip("Save the table as a new named project")
        self.projects_btn = QPushButton("Projects…")
        self.projects_btn.setToolTip("Find, open, create, rename or delete projects")
        for w in (self.restore_btn, self.save_btn, self.saveas_btn,
                  self.projects_btn):
            state_bar.addWidget(w)
        root.addLayout(state_bar)

        foot = QHBoxLayout()
        hint = QLabel("Row order is the ranking — first row is #1. Scores can be any text.")
        hint.setObjectName("hintLabel")
        foot.addWidget(hint)
        foot.addStretch(1)
        self.apply_btn = QPushButton("Apply to Studio")
        self.apply_btn.setObjectName("exportBtn")
        self.apply_btn.setToolTip("Use this table as the video dataset")
        self.close_btn = QPushButton("Close")
        foot.addWidget(self.apply_btn)
        foot.addWidget(self.close_btn)
        root.addLayout(foot)

        self.import_btn.clicked.connect(self._import)
        self.export_btn.clicked.connect(self._export)
        self.add_btn.clicked.connect(self._add_row)
        self.del_btn.clicked.connect(self._delete_rows)
        self.up_btn.clicked.connect(lambda: self._move_row(-1))
        self.down_btn.clicked.connect(lambda: self._move_row(1))
        self.restore_btn.clicked.connect(self._restore_autosave)
        self.save_btn.clicked.connect(self._save_current)
        self.saveas_btn.clicked.connect(self._save_as)
        self.projects_btn.clicked.connect(self._open_projects)
        self.apply_btn.clicked.connect(self._apply)
        self.close_btn.clicked.connect(self.reject)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._save_current)

    # ------------------------------------------------------------- table ops
    def _populate(self):
        self._loading = True
        self.table.setRowCount(len(self._records))
        for r, rec in enumerate(self._records):
            self.table.setRowHeight(r, 42)
            rank = QTableWidgetItem(str(r + 1))
            rank.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            rank.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            rank.setForeground(QColor(styles.current_palette()["title"]))
            self.table.setItem(r, COL_RANK, rank)
            for col, key in ((COL_NAME, "name"), (COL_SCORE, "score"),
                             (COL_TEXT, "text"), (COL_EXTRA, "extratext")):
                item = QTableWidgetItem(str(rec.get(key, "")))
                if col == COL_SCORE:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                          | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(r, col, item)
            self.table.setCellWidget(r, COL_IMAGE, self._image_widget(r))
        self._loading = False
        self.count_label.setText(f"{len(self._records)} / {MAX_ROWS} rows")
        self.add_btn.setEnabled(len(self._records) < MAX_ROWS)

    def _image_widget(self, row):
        rec = self._records[row]
        path = str(rec.get("image", "")).strip()
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(4)

        thumb = QLabel()
        thumb.setObjectName("thumbLabel")
        thumb.setFixedSize(32, 32)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if path and os.path.isfile(path):
            pix = QPixmap(path)
            if not pix.isNull():
                thumb.setPixmap(pix.scaled(
                    30, 30, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
            else:
                thumb.setText("?")
        elif path:
            thumb.setText("!")
            thumb.setToolTip(f"Image file not found:\n{path}")
        else:
            thumb.setText("—")
        lay.addWidget(thumb)

        name = QLabel()
        name.setObjectName("cellName")
        if path:
            base = os.path.basename(path)
            name.setText(name.fontMetrics().elidedText(
                base, Qt.TextElideMode.ElideMiddle, 110))
            name.setToolTip(path)
            styles.set_prop(name, "empty", "false")
        else:
            name.setText("no image")
            styles.set_prop(name, "empty", "true")
        lay.addWidget(name, 1)

        browse = QPushButton("…")
        browse.setObjectName("cellBtn")
        browse.setFixedSize(30, 28)
        browse.setToolTip("Add / change image for this row")
        browse.clicked.connect(lambda _=False, r=row: self._pick_image(r))
        lay.addWidget(browse)

        remove = QPushButton("✕")
        remove.setObjectName("cellBtn")
        remove.setFixedSize(30, 28)
        remove.setToolTip("Remove this row's image")
        remove.setEnabled(bool(path))
        remove.clicked.connect(lambda _=False, r=row: self._clear_image(r))
        lay.addWidget(remove)
        return w

    def _cell_changed(self, row, col):
        if self._loading or row >= len(self._records):
            return
        item = self.table.item(row, col)
        if item is None:
            return
        text = item.text()
        if col == COL_SCORE:
            self._records[row]["score"] = text
        elif col == COL_NAME:
            self._records[row]["name"] = text
        elif col == COL_TEXT:
            self._records[row]["text"] = text
        elif col == COL_EXTRA:
            self._records[row]["extratext"] = text
        else:
            return
        self._touch()

    def _add_row(self):
        if len(self._records) >= MAX_ROWS:
            self._set_status(f"Maximum of {MAX_ROWS} rows reached", error=True)
            return
        self._records.append({"name": "", "score": "", "text": "",
                              "image": "", "extratext": ""})
        self._populate()
        last = len(self._records) - 1
        self.table.selectRow(last)
        item = self.table.item(last, COL_NAME)
        if item is not None:
            self.table.editItem(item)
        self._touch()

    def _delete_rows(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            self._set_status("Select one or more rows to delete", error=True)
            return
        ans = QMessageBox.question(
            self, "Delete rows",
            f"Delete {len(rows)} selected row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans != QMessageBox.StandardButton.Yes:
            return
        for r in rows:
            del self._records[r]
        if not self._records:
            self._records.append({"name": "", "score": "", "text": "",
                                  "image": "", "extratext": ""})
        self._populate()
        self._touch()

    def _move_row(self, delta):
        row = self.table.currentRow()
        new = row + delta
        if row < 0 or not (0 <= new < len(self._records)):
            return
        self._records[row], self._records[new] = \
            self._records[new], self._records[row]
        self._populate()
        self.table.selectRow(new)
        self._touch()

    # -------------------------------------------------------------- images
    def _pick_image(self, row):
        start = store.get_last_image_dir()
        path, _ = QFileDialog.getOpenFileName(
            self, "Pick row image", start,
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*)")
        if not path:
            return
        store.set_last_image_dir(path)
        self._records[row]["image"] = path
        self.table.setCellWidget(row, COL_IMAGE, self._image_widget(row))
        self._touch()

    def _clear_image(self, row):
        self._records[row]["image"] = ""
        self.table.setCellWidget(row, COL_IMAGE, self._image_widget(row))
        self._touch()

    # ---------------------------------------------------------- import/export
    def _import(self):
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
        self._records = store.df_to_records(df)
        self._populate()
        self._touch()
        self._set_status(f"Imported {len(self._records)} rows from "
                         f"{os.path.basename(path)} (max {MAX_ROWS})")

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export dataset", "dataset.csv", "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        df = self._ordered_df()
        df.to_csv(path, index=False)
        self._set_status(f"Exported {len(df)} rows to {os.path.basename(path)}")

    # ------------------------------------------------------------- projects
    def _update_project_chip(self):
        if self._project_name:
            self.project_chip.setText(f"Project: {self._project_name}")
            styles.set_prop(self.project_chip, "saved", "true")
            self.save_btn.setText("Save")
        else:
            self.project_chip.setText("Unsaved project")
            styles.set_prop(self.project_chip, "saved", "false")
            self.save_btn.setText("Save Project…")

    def _save_current(self):
        if not self._project_name:
            self._save_as()
            return
        store.save_project(self._project_name, self._records)
        self._set_status(f"Saved project '{self._project_name}' "
                         f"({len(self._records)} rows)")

    def _save_as(self):
        name, ok = QInputDialog.getText(
            self, "Save project as", "Project name:",
            text=self._project_name or "My Project")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name.startswith("_"):
            name = "proj" + name
        if store.project_exists(name) and name != self._project_name:
            ans = QMessageBox.question(
                self, "Overwrite project?",
                f"A project named '{name}' already exists. Overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                return
        self._project_name = name
        store.save_project(name, self._records)
        self._update_project_chip()
        self._set_status(f"Saved project '{name}' ({len(self._records)} rows)")

    def _open_projects(self):
        from ui.project_manager import ProjectManager
        mgr = ProjectManager(self._project_name, self)
        if mgr.exec() != QDialog.DialogCode.Accepted or not mgr.chosen:
            if mgr.renamed_to and self._project_name == mgr.renamed_from:
                self._project_name = mgr.renamed_to
                self._update_project_chip()
            elif self._project_name and not store.project_exists(self._project_name):
                self._project_name = None
                self._update_project_chip()
            return
        action, name = mgr.chosen
        if mgr.renamed_to and self._project_name == mgr.renamed_from:
            self._project_name = mgr.renamed_to
        if action == "new":
            self._project_name = name
            self._records = [{"name": "", "score": "", "text": "",
                              "image": "", "extratext": ""}]
            self._populate()
            self._update_project_chip()
            self._flush_autosave()
            self._set_status(f"Created project '{name}' — start editing")
            return
        self._open_project(name)

    def _open_project(self, name):
        if not self._project_name:
            ans = QMessageBox.question(
                self, "Save before opening?",
                "The current table is not saved as a project.\n"
                "Save it as a project before opening another?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel)
            if ans == QMessageBox.StandardButton.Cancel:
                return
            if ans == QMessageBox.StandardButton.Yes:
                self._save_as()
                if not self._project_name:
                    return
        try:
            self._records = store.load_project(name)
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "Open failed", str(e))
            return
        if not self._records:
            self._records = [{"name": "", "score": "", "text": "",
                              "image": "", "extratext": ""}]
        self._project_name = name
        self._populate()
        self._update_project_chip()
        self._flush_autosave()
        self._set_status(f"Opened project '{name}' ({len(self._records)} rows)")

    def _restore_autosave(self):
        recs = store.load_autosave()
        if recs is None:
            self._set_status("No auto-saved session found yet", error=True)
            return
        self._records = recs
        self._populate()
        self._set_status("Restored the last auto-saved session")

    # -------------------------------------------------------------- autosave
    def _touch(self):
        self._save_timer.start()

    def _flush_autosave(self):
        self._save_timer.stop()
        store.save_autosave(self._records)
        from datetime import datetime
        stamp = datetime.now().strftime("%H:%M:%S")
        if self._project_name:
            store.save_project(self._project_name, self._records)
            self._set_status(f"Auto-saved to '{self._project_name}' at {stamp}")
        else:
            self._set_status(f"Auto-saved session at {stamp} — "
                             "use Save Project to keep it")

    def _set_status(self, text, error=False):
        self.status_label.setText(text)
        styles.set_prop(self.status_label, "error", "true" if error else "false")

    # ---------------------------------------------------------------- apply
    def _ordered_df(self):
        return store.records_to_df(self._records)

    def _apply(self):
        if not any(str(r.get("name", "")).strip() for r in self._records):
            self._set_status("Give at least one row a name before applying",
                             error=True)
            return
        self._flush_autosave()
        self._result_df = self._ordered_df()
        self.accept()

    def result_df(self):
        return self._result_df

    def closeEvent(self, event):
        self._flush_autosave()
        super().closeEvent(event)