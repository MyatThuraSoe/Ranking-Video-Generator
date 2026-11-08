import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

APP_NAME = "LRBar-RankGen"


def _selftest():
    """Headless end-to-end check of a frozen build (no window, no event loop).

    Run ``LRBar-RankGen.exe --selftest``; a JSON report is written to the temp
    directory and the exit code is 0 on success, 1 on any failure.
    """
    import json
    import subprocess
    import tempfile
    import traceback

    from utils.app_paths import bundle_dir, ffmpeg_path, is_frozen

    report = {"app": APP_NAME, "frozen": is_frozen(),
              "bundle_dir": bundle_dir(), "checks": []}
    ok = True

    def check(name, fn):
        nonlocal ok
        try:
            report["checks"].append({"name": name, "ok": True, "detail": fn()})
        except Exception as exc:
            ok = False
            report["checks"].append({"name": name, "ok": False,
                                     "error": str(exc),
                                     "trace": traceback.format_exc()})

    def _imports():
        import cairo  # noqa: F401
        import numpy  # noqa: F401
        import openpyxl  # noqa: F401
        import pandas  # noqa: F401
        import PIL  # noqa: F401
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        from core.render_engine import build_assets, render_frame  # noqa: F401
        from ui.main_window import MainWindow  # noqa: F401
        return "cairo, numpy, openpyxl, pandas, PIL, PyQt6, core, ui imported"

    def _assets():
        from ui import styles
        missing = [pal[key]
                   for pal in styles.THEMES.values()
                   for key in ("icon_chevron_down", "icon_chevron_up", "icon_check")
                   if not os.path.isfile(pal[key])]
        if missing:
            raise RuntimeError(f"missing bundled icons: {missing}")
        return "all theme SVG icons resolved"

    def _ffmpeg():
        path = ffmpeg_path()
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        proc = subprocess.run([path, "-version"], capture_output=True,
                              text=True, timeout=60, creationflags=flags)
        line = (proc.stdout or proc.stderr).splitlines()[0]
        return {"path": path, "version": line}

    def _export():
        import cairo
        from core.render_engine import build_assets, render_frame
        from data.demo_data import get_demo_data
        from utils.config import RenderConfig
        cfg = RenderConfig(width=320, height=180, fps=10, duration=0.5,
                           crf=28, encode_preset="ultrafast", low_resource=True)
        df = get_demo_data()
        assets = build_assets(cfg, df)
        out = os.path.join(tempfile.gettempdir(), "lrbar_selftest.mp4")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        cmd = [ffmpeg_path(), "-y", "-loglevel", "error",
               "-f", "rawvideo", "-vcodec", "rawvideo",
               "-s", f"{cfg.width}x{cfg.height}", "-pix_fmt", "bgra",
               "-r", str(cfg.fps), "-i", "-",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(cfg.crf),
               "-preset", cfg.encode_preset, "-t", f"{cfg.duration:.2f}", out]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                creationflags=flags)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, cfg.width, cfg.height)
        frames = max(1, int(round(cfg.duration * cfg.fps)))
        for i in range(frames):
            ctx = cairo.Context(surface)
            ctx.set_operator(cairo.OPERATOR_SOURCE)
            render_frame(ctx, cfg, df, assets, i / frames)
            surface.flush()
            proc.stdin.write(surface.get_data().tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "ignore")
        rc = proc.wait()
        size = os.path.getsize(out) if os.path.exists(out) else 0
        if rc != 0 or size == 0:
            raise RuntimeError(f"ffmpeg rc={rc} bytes={size} err={err[-300:]}")
        return {"mp4": out, "bytes": size, "frames": frames}

    check("imports", _imports)
    check("bundled_assets", _assets)
    check("ffmpeg", _ffmpeg)
    check("render_export", _export)

    report["ok"] = ok
    report_path = os.path.join(tempfile.gettempdir(), "lrbar_selftest_report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    try:
        print(json.dumps(report))
    except Exception:
        pass
    return 0 if ok else 1


def main():
    from PyQt6.QtGui import QFont, QIcon
    from PyQt6.QtWidgets import QApplication, QMessageBox

    from data.seed import seed_user_data
    from data.state_store import get_theme
    from ui.main_window import MainWindow
    from ui.scroll_guard import install as install_scroll_guard
    from ui.styles import apply_theme
    from utils.app_paths import logo_path
    from utils.ffmpeg_check import ffmpeg_available

    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "LRBar.RankGen.Desktop.1")
        except Exception:
            pass

    app = QApplication(sys.argv)
    install_scroll_guard(app)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    # Fusion gives QSS full control over every control instead of mixing in
    # native Windows chrome (which cannot be rounded or themed consistently).
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    icon = logo_path()
    if icon:
        app.setWindowIcon(QIcon(icon))
    apply_theme(app, get_theme())

    try:
        seed_user_data()
    except Exception as exc:
        print(f"[warn] sample seeding skipped: {exc}")

    window = MainWindow()
    if not ffmpeg_available():
        QMessageBox.warning(
            window, "FFmpeg not found",
            "FFmpeg was not detected.\n"
            "Live preview works, but video export is disabled.\n"
            "Reinstall LRBar-RankGen to restore the bundled encoder.")
        window.set_export_enabled(False)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    main()