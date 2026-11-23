@echo off
REM Builds and flashes demo/tag/test.hex (card.h -> tag over SWD via Pico).
setlocal
cmd /c "%~dp0..\tag\build.cmd"
if errorlevel 1 exit /b 1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\..\tools\flash-probe.ps1" -Image "%~dp0..\tag\test.hex" -Tries 5 -Pause 5
