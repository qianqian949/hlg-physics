#!/bin/bash
set -e

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "Research Logic Graph Extractor - macOS Setup"
echo "========================================"

# Pick the best available Python (3.12 > 3.11 > 3.10 > 3.9 > python3)
PY=""
for candidate in python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "Python 3 was not found. Install Python 3.11 or 3.12, then run this script again."
    echo "Download: https://www.python.org/downloads/macos/"
    exit 1
fi

echo "Using $($PY --version) ($(command -v $PY))"

# Warn (but continue) on older interpreters
PY_MINOR="$($PY -c 'import sys; print(sys.version_info[1])')"
if [ "$PY_MINOR" -lt 10 ]; then
    echo ""
    echo "WARNING: Python 3.$PY_MINOR detected. 3.11 or 3.12 is recommended."
    echo "Install a newer Python from https://www.python.org/downloads/macos/ if setup fails."
    echo ""
fi

if [ ! -d "venv" ]; then
    echo "Creating Mac virtual environment..."
    "$PY" -m venv venv
fi

source venv/bin/activate

echo "Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env. Add your Zhipu API key before starting the app."
fi

echo ""
echo "Setup complete. Edit .env (set ZHIPU_API_KEY=...), then run ./run.sh"
