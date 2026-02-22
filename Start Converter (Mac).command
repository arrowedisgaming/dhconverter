#!/bin/bash
# Double-click this file in Finder to launch the Daggerheart Adversary Converter web UI.

# Move to the directory where this script lives (the project root)
cd "$(dirname "$0")" || exit 1

# Check for Python 3
if ! command -v python3 &>/dev/null; then
    echo "Error: Python 3 is required but not found."
    echo "Install from https://www.python.org/downloads/"
    echo ""
    echo "Press any key to close..."
    read -n 1
    exit 1
fi

# Launch the web server (opens browser automatically)
python3 app.py

# If the server exits unexpectedly, keep the window open so the user can read errors
if [ $? -ne 0 ]; then
    echo ""
    echo "The server exited with an error. Press any key to close..."
    read -n 1
fi
