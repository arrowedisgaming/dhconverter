@echo off
REM Double-click this file to launch the Daggerheart Adversary Converter web UI.

cd /d "%~dp0"

REM Check for Python
where py >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON=py -3"
    goto :setup
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON=python"
    goto :setup
)

where python3 >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON=python3"
    goto :setup
)

echo Error: Python is required but not found.
echo Install from https://www.python.org/downloads/
echo.
pause
exit /b 1

:setup
if not exist ".venv\Scripts\python.exe" (
    echo Setting up local Python environment...
    %PYTHON% -m venv .venv
    if %errorlevel% neq 0 (
        echo.
        echo Could not create .venv. Install Python 3.10+ from https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

echo Checking dependencies...
".venv\Scripts\python.exe" -c "import importlib.util, sys; sys.exit(0 if all(importlib.util.find_spec(m) for m in ('pdfplumber', 'openpyxl')) else 1)"
if %errorlevel% neq 0 (
    echo Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo Dependency install failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" app.py
if %errorlevel% neq 0 (
    echo.
    echo The server exited with an error.
    pause
)
exit /b
