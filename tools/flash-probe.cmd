@echo off
rem Five probe-rs tries. Beep at the start of each. Stops after a verified write.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0flash-probe.ps1" %*
