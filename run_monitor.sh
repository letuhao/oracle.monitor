#!/bin/bash
# Oracle Database Monitor - Linux/Mac Shell Script
# Usage: ./run_monitor.sh

echo "========================================"
echo "Oracle Database Session Monitor"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.7+ and try again"
    exit 1
fi

# Check if config.json exists
if [ ! -f "config.json" ]; then
    echo "ERROR: config.json not found"
    echo "Please copy config.example.json to config.json and configure it"
    exit 1
fi

# Check if oracledb is installed
python3 -c "import oracledb" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing required dependencies..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install dependencies"
        exit 1
    fi
fi

echo "Starting Oracle monitor..."
echo ""

python3 oracle_monitor.py

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Monitor failed to run"
    exit 1
fi

echo ""
echo "Monitoring completed successfully"

