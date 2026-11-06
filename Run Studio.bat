@echo off
cd /d "%~dp0ranking_video_studio"
set "PY=..\.venv\Scripts\pythonw.exe"
if not exist "%PY%" set "PY=..\.venv\Scripts\python.exe"
start "" "%PY%" main.py
