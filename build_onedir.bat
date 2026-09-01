@echo off
cd /d "%~dp0"

call .venv\Scripts\activate.bat

set "MINEEXP_BUILD_MODE=onedir"
pyinstaller --clean --noconfirm MineExp.spec
set "BUILD_EXIT=%ERRORLEVEL%"
set "MINEEXP_BUILD_MODE="

if %BUILD_EXIT% equ 0 (
    echo.
    echo Build success! exe is at dist\MineExp\MineExp.exe
    echo.
    echo NOTE: Session/ and language/ are auto-initialized at first run.
) else (
    echo.
    echo Build failed.
)

pause
exit /b %BUILD_EXIT%
