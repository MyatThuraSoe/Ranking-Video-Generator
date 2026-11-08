"""Branded per-user installer for LRBar-RankGen (no administrator required).

Installs to %LOCALAPPDATA%\\Programs, creates Start Menu / Desktop shortcuts,
registers an Add/Remove Programs entry and drops a real uninstaller. The same
executable acts as the uninstaller when copied to <install dir>\\uninstall.exe.
Supports --silent for unattended install/uninstall.
"""
import json
import os
import shutil
import subprocess
import sys
import winreg

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QProgressBar, QPushButton, QStackedWidget, QVBoxLayout,
    QWidget,
)

APP_NAME = "LRBar-RankGen"
VERSION = "1.0.0"
PUBLISHER = "LRBar"
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\LRBar-RankGen"
MANIFEST = "install_manifest.json"

QSS = """
QWidget#root { background: #eef2f8; }
QWidget#brand {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #1e3a8a, stop:0.55 #2563eb, stop:1 #38bdf8);
    border-radius: 0px;
}
QLabel#brandTitle { color: #ffffff; font-size: 22px; font-weight: 800; }
QLabel#brandSub { color: #dbeafe; font-size: 12px; }
QLabel#brandVer { color: #bfdbfe; font-size: 11px; }
QWidget#panel { background: #ffffff; border: 1px solid #dfe6ef;
                border-radius: 14px; }
QLabel#h1 { color: #0f172a; font-size: 17px; font-weight: 700; }
QLabel#body { color: #6b7a90; font-size: 12px; }
QLabel#fieldLabel { color: #0f172a; font-size: 12px; font-weight: 600; }
QLineEdit { background: #f6f8fc; border: 1px solid #dfe6ef; border-radius: 8px;
            padding: 7px 10px; color: #0f172a; font-size: 12px; }
QLineEdit:focus { border: 1px solid #2563eb; }
QCheckBox { color: #0f172a; font-size: 12px; spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px;
                       border: 1px solid #dfe6ef; background: #f6f8fc; }
QCheckBox::indicator:checked { background: #2563eb; border: 1px solid #2563eb;
                               image: none; }
QPushButton { background: #f6f8fc; border: 1px solid #dfe6ef; border-radius: 8px;
              padding: 8px 16px; color: #0f172a; font-size: 12px;
              font-weight: 600; }
QPushButton:hover { background: #eef2f8; border-color: #2563eb; }
QPushButton#primary { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                      stop:0 #2563eb, stop:1 #1d4ed8); color: #ffffff;
                      border: none; }
QPushButton#primary:hover { background: #1d4ed8; }
QPushButton#primary:disabled { background: #dfe6ef; color: #6b7a90; }
QProgressBar { background: #f6f8fc; border: 1px solid #dfe6ef; border-radius: 7px;
               height: 14px; text-align: center; color: #0f172a; font-size: 10px; }
QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                      stop:0 #2563eb, stop:1 #38bdf8); border-radius: 6px; }
QLabel#status { color: #6b7a90; font-size: 12px; }
QLabel#doneTitle { color: #0f172a; font-size: 18px; font-weight: 800; }
"""


def _no_window():
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def base_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def payload_exe():
    if getattr(sys, "frozen", False):
        return os.path.join(base_dir(), "payload", APP_NAME + ".exe")
    return os.path.join(base_dir(), "dist", APP_NAME + ".exe")


def logo_png():
    if getattr(sys, "frozen", False):
        return os.path.join(base_dir(), "app_icon.png")
    return os.path.join(base_dir(), "packaging", "app_icon.png")


def default_dir():
    local = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(local, "Programs", APP_NAME)


def desktop_dir():
    return os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")),
                        "Desktop")


def startmenu_dir():
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu",
                        "Programs")


def _ps_quote(path):
    return path.replace("'", "''")


def make_shortcut(lnk, target, workdir, icon):
    os.makedirs(os.path.dirname(lnk), exist_ok=True)
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{_ps_quote(lnk)}'); "
        f"$s.TargetPath = '{_ps_quote(target)}'; "
        f"$s.WorkingDirectory = '{_ps_quote(workdir)}'; "
        f"$s.IconLocation = '{_ps_quote(icon)}'; "
        f"$s.Description = '{APP_NAME}'; "
        "$s.Save()"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True, creationflags=_no_window())
    return proc.returncode == 0 and os.path.isfile(lnk)


def register_uninstall(install_dir, uninstall_cmd):
    key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_KEY, 0,
                             winreg.KEY_SET_VALUE)
    quoted = f'"{uninstall_cmd}"'
    values = {
        "DisplayName": APP_NAME,
        "DisplayVersion": VERSION,
        "Publisher": PUBLISHER,
        "InstallLocation": install_dir,
        "UninstallString": quoted,
        "QuietUninstallString": quoted + " --silent",
        "DisplayIcon": os.path.join(install_dir, APP_NAME + ".exe") + ",0",
        "NoModify": 1,
        "NoRepair": 1,
    }
    for name, val in values.items():
        winreg.SetValueEx(key, name, 0,
                          winreg.REG_DWORD if isinstance(val, int)
                          else winreg.REG_SZ, val)
    winreg.CloseKey(key)


def unregister_uninstall():
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_KEY)
    except FileNotFoundError:
        pass


def do_install(install_dir, desktop, startmenu, cb=None):
    def report(pct, msg):
        if cb:
            cb(pct, msg)

    src = payload_exe()
    if not os.path.isfile(src):
        raise FileNotFoundError(f"Payload not found: {src}")
    os.makedirs(install_dir, exist_ok=True)
    report(10, "Copying application files…")
    app_dst = os.path.join(install_dir, APP_NAME + ".exe")
    shutil.copy2(src, app_dst)
    report(45, "Writing uninstaller…")
    if getattr(sys, "frozen", False):
        uninstall_cmd = os.path.join(install_dir, "uninstall.exe")
        shutil.copy2(sys.executable, uninstall_cmd)
    else:
        uninstall_cmd = os.path.join(install_dir, "uninstall.cmd")
        with open(uninstall_cmd, "w", encoding="utf-8") as fh:
            fh.write(f'@echo off\r\n"{sys.executable}" '
                     f'"{os.path.abspath(__file__)}" --uninstall --silent '
                     f'--dir "{install_dir}"\r\n')
    report(60, "Creating shortcuts…")
    manifest = {"dir": install_dir, "version": VERSION, "shortcuts": []}
    icon = app_dst + ",0"
    if startmenu:
        lnk = os.path.join(startmenu_dir(), APP_NAME + ".lnk")
        if make_shortcut(lnk, app_dst, install_dir, icon):
            manifest["shortcuts"].append(lnk)
    if desktop:
        lnk = os.path.join(desktop_dir(), APP_NAME + ".lnk")
        if make_shortcut(lnk, app_dst, install_dir, icon):
            manifest["shortcuts"].append(lnk)
    report(80, "Registering uninstall entry…")
    register_uninstall(install_dir, uninstall_cmd)
    with open(os.path.join(install_dir, MANIFEST), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    report(100, "Installed.")
    return manifest


def do_uninstall(install_dir, cb=None):
    manifest_path = os.path.join(install_dir, MANIFEST)
    shortcuts = []
    if os.path.isfile(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as fh:
            shortcuts = json.load(fh).get("shortcuts", [])
    for lnk in shortcuts:
        try:
            os.remove(lnk)
        except OSError:
            pass
    unregister_uninstall()
    # The uninstaller runs from inside the install dir; a temp batch deletes
    # the folder after this process exits (ping delay works without a console).
    bat = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")),
                       "_lrbar_uninstall.bat")
    with open(bat, "w", encoding="utf-8") as fh:
        fh.write('@echo off\r\n'
                 'ping -n 2 127.0.0.1 >nul\r\n'
                 f'rd /s /q "{install_dir}"\r\n'
                 'del "%~f0"\r\n')
    subprocess.Popen(["cmd", "/c", bat], creationflags=_no_window())


class InstallWorker(QThread):
    progress = pyqtSignal(int, str)
    done = pyqtSignal(bool, str)

    def __init__(self, install_dir, desktop, startmenu):
        super().__init__()
        self.install_dir = install_dir
        self.desktop = desktop
        self.startmenu = startmenu

    def run(self):
        try:
            do_install(self.install_dir, self.desktop, self.startmenu,
                       lambda p, m: self.progress.emit(p, m))
            self.done.emit(True, "")
        except Exception as exc:
            self.done.emit(False, str(exc))


class SetupWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle(f"{APP_NAME} Setup")
        self.setFixedSize(760, 460)
        logo = logo_png()
        if os.path.isfile(logo):
            self.setWindowIcon(QIcon(logo))
        self.worker = None
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        brand = QWidget()
        brand.setObjectName("brand")
        brand.setFixedWidth(250)
        bl = QVBoxLayout(brand)
        bl.setContentsMargins(24, 28, 24, 24)
        bl.setSpacing(10)
        mark = QLabel()
        pm = QPixmap(logo_png())
        if not pm.isNull():
            mark.setPixmap(pm.scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation))
        bl.addWidget(mark)
        t = QLabel(APP_NAME)
        t.setObjectName("brandTitle")
        bl.addWidget(t)
        s = QLabel("Cinematic 3D ranking videos.\nLive preview · 2K export.")
        s.setObjectName("brandSub")
        s.setWordWrap(True)
        bl.addWidget(s)
        bl.addStretch(1)
        v = QLabel(f"Version {VERSION} · {PUBLISHER}")
        v.setObjectName("brandVer")
        bl.addWidget(v)
        root.addWidget(brand)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(22, 22, 22, 18)
        rl.setSpacing(14)
        self.stack = QStackedWidget()
        rl.addWidget(self.stack, 1)
        self.stack.addWidget(self._page_options())
        self.stack.addWidget(self._page_progress())
        self.stack.addWidget(self._page_done())

        foot = QHBoxLayout()
        foot.addStretch(1)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.close)
        self.next_btn = QPushButton("Install")
        self.next_btn.setObjectName("primary")
        self.next_btn.clicked.connect(self._next)
        foot.addWidget(self.cancel_btn)
        foot.addWidget(self.next_btn)
        rl.addLayout(foot)
        root.addWidget(right, 1)
        self._sync_buttons()

    def _page_options(self):
        panel = QWidget()
        panel.setObjectName("panel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        h = QLabel("Install location & options")
        h.setObjectName("h1")
        lay.addWidget(h)
        b = QLabel("Installs for your user account only — no administrator "
                   "rights needed.")
        b.setObjectName("body")
        b.setWordWrap(True)
        lay.addWidget(b)
        fl = QLabel("Folder")
        fl.setObjectName("fieldLabel")
        lay.addWidget(fl)
        row = QHBoxLayout()
        self.dir_edit = QLineEdit(default_dir())
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row.addWidget(self.dir_edit, 1)
        row.addWidget(browse)
        lay.addLayout(row)
        self.desktop_check = QCheckBox("Create a Desktop shortcut")
        self.desktop_check.setChecked(True)
        self.startmenu_check = QCheckBox("Add to Start Menu")
        self.startmenu_check.setChecked(True)
        lay.addWidget(self.desktop_check)
        lay.addWidget(self.startmenu_check)
        lay.addStretch(1)
        return panel

    def _page_progress(self):
        panel = QWidget()
        panel.setObjectName("panel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)
        h = QLabel("Installing…")
        h.setObjectName("h1")
        lay.addWidget(h)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        lay.addWidget(self.bar)
        self.status = QLabel("Preparing…")
        self.status.setObjectName("status")
        lay.addWidget(self.status)
        lay.addStretch(1)
        return panel

    def _page_done(self):
        panel = QWidget()
        panel.setObjectName("panel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        h = QLabel("Installation complete")
        h.setObjectName("doneTitle")
        lay.addWidget(h)
        b = QLabel(f"{APP_NAME} is now installed and listed in Windows "
                   "Settings → Apps. An uninstaller is included.")
        b.setObjectName("body")
        b.setWordWrap(True)
        lay.addWidget(b)
        self.launch_check = QCheckBox(f"Launch {APP_NAME} now")
        self.launch_check.setChecked(True)
        lay.addWidget(self.launch_check)
        lay.addStretch(1)
        return panel

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Choose install folder",
                                                self.dir_edit.text())
        if path:
            self.dir_edit.setText(os.path.join(path, APP_NAME))

    def _sync_buttons(self):
        page = self.stack.currentIndex()
        self.cancel_btn.setVisible(page != 2)
        self.next_btn.setText({0: "Install", 1: "Installing…",
                               2: "Finish"}[page])
        self.next_btn.setEnabled(page != 1)

    def _next(self):
        page = self.stack.currentIndex()
        if page == 0:
            target = self.dir_edit.text().strip()
            if not target:
                return
            self.install_dir = target
            self.stack.setCurrentIndex(1)
            self._sync_buttons()
            self.worker = InstallWorker(target, self.desktop_check.isChecked(),
                                        self.startmenu_check.isChecked())
            self.worker.progress.connect(self._progress)
            self.worker.done.connect(self._installed)
            self.worker.start()
        elif page == 2:
            if self.launch_check.isChecked():
                exe = os.path.join(self.install_dir, APP_NAME + ".exe")
                subprocess.Popen([exe], cwd=self.install_dir,
                                 creationflags=_no_window())
            self.close()

    def _progress(self, pct, msg):
        self.bar.setValue(pct)
        self.status.setText(msg)

    def _installed(self, ok, err):
        if not ok:
            QMessageBox.critical(self, "Install failed", err)
            self.stack.setCurrentIndex(0)
        else:
            self.stack.setCurrentIndex(2)
        self._sync_buttons()


def _parse_args(argv):
    opts = {"silent": False, "uninstall": False, "dir": default_dir(),
            "desktop": True, "startmenu": True}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--silent", "/S"):
            opts["silent"] = True
        elif a == "--uninstall":
            opts["uninstall"] = True
        elif a == "--no-desktop":
            opts["desktop"] = False
        elif a == "--no-startmenu":
            opts["startmenu"] = False
        elif a == "--dir" and i + 1 < len(argv):
            i += 1
            opts["dir"] = argv[i]
        i += 1
    return opts


def main():
    argv = sys.argv[1:]
    opts = _parse_args(argv)
    is_uninstall_exe = os.path.basename(sys.executable).lower() == "uninstall.exe"
    if is_uninstall_exe or opts["uninstall"]:
        target = opts["dir"]
        if is_uninstall_exe:
            target = os.path.dirname(os.path.abspath(sys.executable))
        if not opts["silent"]:
            app = QApplication(sys.argv)
            ans = QMessageBox.question(
                None, f"Uninstall {APP_NAME}",
                f"Remove {APP_NAME} from this computer?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                return 0
        do_uninstall(target)
        return 0

    if opts["silent"]:
        try:
            do_install(opts["dir"], opts["desktop"], opts["startmenu"])
            result = {"ok": True, "dir": opts["dir"]}
            code = 0
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
            code = 1
        try:
            print(json.dumps(result))
        except Exception:
            pass  # windowed exe has no stdout
        return code

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(QSS)
    win = SetupWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())