@echo off
cd /d "%~dp0"

REM ── P2-5 命令行控制台：检查 venv 是否已激活 ──
if not defined VIRTUAL_ENV (
    if exist "venv\Scripts\activate.bat" (
        echo [INFO] Activating virtual environment...
        call venv\Scripts\activate.bat
    ) else (
        echo [WARN] venv not found, running with system Python
    )
) else (
    echo [INFO] Virtual environment already active: %VIRTUAL_ENV%
)

python main.py

pause
