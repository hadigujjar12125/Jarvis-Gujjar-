@echo off
REM Build release for Windows using PyInstaller
pyinstaller --onefile -n jarvis_launcher jarvis/cli.py
echo Built jarvis_launcher.exe in dist\
