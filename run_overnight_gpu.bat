@echo off
cd /d "%~dp0"
set "CODEX_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "OUT=Results\overnight-gpu-sweep.json"
if exist "%CODEX_PY%" (
    "%CODEX_PY%" gpu_sweep.py --configs 768 --seeds 1,2,3,4,5,6,7,8 --screen-steps 40000 --replay-steps 500000 --sample-every 5000 --batch-size 128 --top 12 --workers 4 --out "%OUT%" %*
) else (
    python gpu_sweep.py --configs 768 --seeds 1,2,3,4,5,6,7,8 --screen-steps 40000 --replay-steps 500000 --sample-every 5000 --batch-size 128 --top 12 --workers 4 --out "%OUT%" %*
)
if errorlevel 1 pause
