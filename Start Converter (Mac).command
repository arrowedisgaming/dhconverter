#!/bin/bash
# Double-click this file in Finder to launch the Daggerheart Adversary Converter web UI.

# Move to the directory where this script lives (the project root)
cd "$(dirname "$0")" || exit 1

# Check for Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: Python 3 is required but not found."
    echo "Install from https://www.python.org/downloads/"
    echo ""
    echo "Press any key to close..."
    read -n 1
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "Setting up local Python environment..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo ""
        echo "Could not create .venv. Install Python 3.10+ from https://www.python.org/downloads/"
        echo "Press any key to close..."
        read -n 1
        exit 1
    fi
fi

echo "Checking dependencies..."
.venv/bin/python -c "import importlib.util, sys; sys.exit(0 if all(importlib.util.find_spec(m) for m in ('pdfplumber', 'openpyxl')) else 1)"
if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    .venv/bin/python -m pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo ""
        echo "Dependency install failed. Check your internet connection and try again."
        echo "Press any key to close..."
        read -n 1
        exit 1
    fi
fi

# Launch the web server (opens browser automatically)
.venv/bin/python app.py

# If the server exits unexpectedly, keep the window open so the user can read errors
if [ $? -ne 0 ]; then
    echo ""
    echo "The server exited with an error. Press any key to close..."
    read -n 1
fi
