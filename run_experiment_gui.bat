@echo off
cd /d "%~dp0"
set "CODEX_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%CODEX_PY%" (
    "%CODEX_PY%" experiment_gui.py
) else (
    python experiment_gui.py
)
if errorlevel 1 pause
