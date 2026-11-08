@echo off
cd /d "%~dp0"
if not exist java\dist\LRBar-License-Manager.jar call java\build.bat
if errorlevel 1 exit /b 1
cd /d "%~dp0"
start "" javaw -jar java\dist\LRBar-License-Manager.jar
