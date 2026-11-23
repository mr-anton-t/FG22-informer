@echo off
rem Official erase-unlock. Does not flash. Usage: unlock.cmd status   or   unlock.cmd unlock
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0unlock.ps1" -Action %1
