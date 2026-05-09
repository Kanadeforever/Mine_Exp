@echo off
cd /d "%~dp0"

call venv\Scripts\activate.bat

pyinstaller --onedir --noconsole ^
    --name "ExplorerSessionSaver" ^
    --clean ^
    --icon "app/resources/icon.ico" ^
    --add-data "language;language" ^
    --add-data "app/resources;app/resources" ^
    main.py

if %ERRORLEVEL% equ 0 (
    echo.
    echo Build success! exe is at dist\ExplorerSessionSaver.exe
    echo.
    echo NOTE: Session/ and language/ are auto-initialized at first run.
) else (
    echo.
    echo Build failed.
)

pause