@echo off
REM ===================================================
REM ShopGuard AI - Launcher for Windows 10/11
REM ===================================================

echo ===================================================
echo Starting ShopGuard AI Engine (Phase 1)...
echo ===================================================

REM Check for virtual environment
IF NOT EXIST "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment 'venv' was not found!
    echo Please create the virtual environment and install requirements:
    echo     python -m venv venv
    echo     .\venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM Run main.py using the virtual environment python interpreter
.\venv\Scripts\python.exe main.py %*

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo [NOTICE] ShopGuard AI terminated with exit code %ERRORLEVEL%.
    pause
)
