# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the self-contained, windowed LRBar-RankGen.exe."""
import os

from PyInstaller.utils.hooks import collect_dynamic_libs

HERE = os.path.abspath(SPECPATH)
PACK = os.path.join(HERE, "packaging")

a = Analysis(
    ["main.py"],
    pathex=[HERE],
    binaries=collect_dynamic_libs("cairo") + [(os.path.join(PACK, "ffmpeg.exe"), ".")],
    datas=[
        (os.path.join(HERE, "ui", "assets"), os.path.join("ui", "assets")),
        (os.path.join(PACK, "app_icon.png"), "."),
        (os.path.join(PACK, "seed"), "seed"),
    ],
    hiddenimports=[
        "cairo", "pandas", "numpy", "openpyxl", "PIL",
        "openpyxl.cell._writer", "PyQt6.QtSvg",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib",
        "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineQuick",
        "PyQt6.QtQuick", "PyQt6.QtQml", "PyQt6.QtQuick3D", "PyQt6.QtQuickWidgets",
        "PyQt6.QtMultimedia", "PyQt6.QtMultimediaWidgets", "PyQt6.QtSpatialAudio",
        "PyQt6.Qt3DCore", "PyQt6.Qt3DRender", "PyQt6.Qt3DInput", "PyQt6.Qt3DLogic",
        "PyQt6.Qt3DAnimation", "PyQt6.Qt3DExtras", "PyQt6.QtCharts", "PyQt6.QtDataVisualization",
        "PyQt6.QtPdf", "PyQt6.QtPdfWidgets", "PyQt6.QtBluetooth", "PyQt6.QtNfc",
        "PyQt6.QtPositioning", "PyQt6.QtLocation", "PyQt6.QtSensors", "PyQt6.QtSerialPort",
        "PyQt6.QtSerialBus", "PyQt6.QtWebSockets", "PyQt6.QtWebChannel", "PyQt6.QtRemoteObjects",
        "PyQt6.QtScxml", "PyQt6.QtStateMachine", "PyQt6.QtTextToSpeech", "PyQt6.QtNetworkAuth",
        "PyQt6.QtHttpServer", "PyQt6.QtGrpc", "PyQt6.QtDesigner", "PyQt6.QtHelp",
        "PyQt6.QtTest", "PyQt6.QtXml", "PyQt6.QtSql", "PyQt6.QtDBus", "PyQt6.QtConcurrent",
        "PyQt6.QtOpenGLWidgets",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="LRBar-RankGen",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PACK, "app_icon.ico"),
    version=os.path.join(PACK, "version_info.txt"),
)