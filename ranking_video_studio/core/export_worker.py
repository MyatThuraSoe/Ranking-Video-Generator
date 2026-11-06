"""Background export thread: streams raw frames directly to FFmpeg stdin.

Only ONE frame buffer exists at any time. Never accumulate frames in a list.
"""
import subprocess
import threading

import cairo
from PyQt6.QtCore import QThread, pyqtSignal

from core.render_engine import build_assets, render_frame


class VideoExportThread(QThread):
    progress = pyqtSignal(int)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, cfg, df, output_path, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.df = df
        self.output_path = output_path
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _build_command(self):
        cfg = self.cfg
        cmd = [
            "ffmpeg", "-y", "-nostats", "-loglevel", "error",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{cfg.width}x{cfg.height}",
            "-pix_fmt", "bgra",
            "-r", str(cfg.fps),
            "-i", "-",
        ]
        has_audio = bool(cfg.audio_file)
        if has_audio:
            # Input-level -t bounds the infinite loop; without it ffmpeg
            # never sees audio EOF and -shortest hangs the muxer.
            cmd += ["-stream_loop", "-1", "-t", f"{cfg.duration:.2f}",
                    "-i", cfg.audio_file]
            fade_start = max(0.0, cfg.duration - 1.5)
            vol = max(10, min(150, cfg.audio_volume)) / 100.0
            cmd += [
                "-filter_complex",
                f"[1:a]volume={vol:.2f},afade=t=out:st={fade_start:.2f}:d=1.5[aout]",
            ]
        cmd += ["-map", "0:v:0"]
        if has_audio:
            cmd += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
        cmd += [
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", str(cfg.crf),
            "-preset", cfg.encode_preset,
            "-t", f"{cfg.duration:.2f}",
            self.output_path,
        ]
        return cmd

    def run(self):
        proc = None
        try:
            cfg = self.cfg
            assets = build_assets(cfg, self.df)
            total_frames = max(1, int(round(cfg.duration * cfg.fps)))

            cmd = self._build_command()
            import os
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

            proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                creationflags=creationflags,
            )

            # Drain stderr concurrently: a full pipe buffer would block
            # ffmpeg mid-encode and deadlock our stdin writes.
            stderr_chunks = []

            def _drain():
                for chunk in iter(proc.stderr.readline, b""):
                    stderr_chunks.append(chunk)

            threading.Thread(target=_drain, daemon=True).start()

            # Single reused frame buffer
            surface = cairo.ImageSurface(
                cairo.FORMAT_ARGB32, cfg.width, cfg.height)

            for i in range(total_frames):
                if self._cancelled:
                    break
                ctx = cairo.Context(surface)
                ctx.set_operator(cairo.OPERATOR_SOURCE)
                render_frame(ctx, cfg, self.df, assets, i / total_frames)
                surface.flush()
                proc.stdin.write(surface.get_data().tobytes())
                self.progress.emit(int((i + 1) * 100 / total_frames))

            proc.stdin.close()
            rc = proc.wait()
            stderr = b"".join(stderr_chunks).decode("utf-8", "ignore")

            if self._cancelled:
                self.failed.emit("Export cancelled.")
            elif rc != 0:
                tail = "\n".join(stderr.strip().splitlines()[-8:])
                self.failed.emit(f"FFmpeg exited with code {rc}:\n{tail}")
            else:
                self.finished_ok.emit(self.output_path)
        except Exception as e:
            if proc is not None:
                try:
                    proc.kill()
                except Exception:
                    pass
            self.failed.emit(str(e))
