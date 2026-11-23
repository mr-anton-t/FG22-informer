@echo off
rem Five tries. A Windows system sound plays at the start of each. Stops after a successful write.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0flash-btl.ps1" %*
