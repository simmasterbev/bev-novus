@echo off
cd /d "%~dp0"
python experiment_gui.py
if errorlevel 1 pause
