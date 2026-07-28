@echo off
cd /d "%~dp0"
set "CODEX_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%CODEX_PY%" set "CODEX_PY=python"
"%CODEX_PY%" -m pip install --upgrade --target .gpu-packages -r requirements-gpu.txt
if errorlevel 1 (
    pause
    exit /b 1
)
"%CODEX_PY%" gpu_sweep.py --self-test
if errorlevel 1 pause
