@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0read-swd.ps1" %*
