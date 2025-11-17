#!/bin/bash
# Oracle Database Monitor GUI - Linux/Mac Shell Script
# Usage: ./run_gui.sh

echo "========================================"
echo "Oracle Database Monitor - GUI Version"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.7+ and try again"
    exit 1
fi

# Check if dependencies are installed
python3 -c "import streamlit" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing required dependencies..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install dependencies"
        exit 1
    fi
fi

echo "Starting Oracle Monitor GUI..."
echo "The web interface will open in your default browser"
echo "Press Ctrl+C to stop the application"
echo ""

streamlit run oracle_monitor_gui.py

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Failed to start GUI"
    exit 1
fi

