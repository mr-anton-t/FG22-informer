@echo off
REM Full autonomous card flow: read card planes from the Pico W serial,
REM write demo\tag\card.h, then build + flash to the tag.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0card_reader.ps1"
if errorlevel 1 exit /b 1
cmd /c "%~dp0flash-card.cmd"
