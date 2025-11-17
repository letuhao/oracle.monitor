@echo off
REM Oracle Database Monitor - Windows Batch Script
REM Usage: run_monitor.bat

echo ========================================
echo Oracle Database Session Monitor
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ and try again
    pause
    exit /b 1
)

REM Check if config.json exists
if not exist config.json (
    echo ERROR: config.json not found
    echo Please copy config.example.json to config.json and configure it
    pause
    exit /b 1
)

REM Check if oracledb is installed
python -c "import oracledb" >nul 2>&1
if errorlevel 1 (
    echo Installing required dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo Starting Oracle monitor...
echo.

python oracle_monitor.py

if errorlevel 1 (
    echo.
    echo ERROR: Monitor failed to run
    pause
    exit /b 1
)

echo.
echo Monitoring completed successfully
pause

