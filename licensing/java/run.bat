@echo off
cd /d "%~dp0"
if not exist dist\LRBar-License-Manager.jar call build.bat
if errorlevel 1 exit /b 1
start "" javaw -jar dist\LRBar-License-Manager.jar
