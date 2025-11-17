@echo off
REM Oracle Database Monitor GUI - Windows Batch Script
REM Usage: run_gui.bat

echo ========================================
echo Oracle Database Monitor - GUI Version
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

REM Check if dependencies are installed
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo Installing required dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo Starting Oracle Monitor GUI...
echo The web interface will open in your default browser
echo Press Ctrl+C to stop the application
echo.

streamlit run oracle_monitor_gui.py

if errorlevel 1 (
    echo.
    echo ERROR: Failed to start GUI
    pause
    exit /b 1
)

