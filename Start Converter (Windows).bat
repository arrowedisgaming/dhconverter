@echo off
REM Double-click this file to launch the Daggerheart Adversary Converter web UI.

cd /d "%~dp0"

REM Check for Python
where python >nul 2>nul
if %errorlevel% equ 0 (
    python app.py
    if %errorlevel% neq 0 (
        echo.
        echo The server exited with an error.
        pause
    )
    exit /b
)

where python3 >nul 2>nul
if %errorlevel% equ 0 (
    python3 app.py
    if %errorlevel% neq 0 (
        echo.
        echo The server exited with an error.
        pause
    )
    exit /b
)

echo Error: Python is required but not found.
echo Install from https://www.python.org/downloads/
echo.
pause
exit /b 1
