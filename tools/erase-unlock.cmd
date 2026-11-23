@echo off
rem Five tries. Beep, then official erase-unlock. Stops after success. Does not flash.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0erase-unlock.ps1" %*
