@echo off
setlocal
cd /d "%~dp0"
if not exist build\classes mkdir build\classes
javac -encoding UTF-8 -d build\classes src\lrbar\license\*.java
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)
if not exist dist mkdir dist
set "JAR_TOOL=jar"
where jar >nul 2>&1
if not errorlevel 1 goto havejar
for /f "tokens=2 delims==" %%H in ('java -XshowSettings:properties -version 2^>^&1 ^| findstr /C:"java.home ="') do set "JH=%%H"
for /f "tokens=* delims= " %%H in ("%JH%") do set "JH=%%H"
if defined JH set "JAR_TOOL=%JH%\bin\jar.exe"
:havejar
"%JAR_TOOL%" --create --file dist\LRBar-License-Manager.jar --main-class lrbar.license.Main -C build\classes .
if errorlevel 1 exit /b 1
echo Built %~dp0dist\LRBar-License-Manager.jar
