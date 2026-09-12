#!/bin/bash

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f "venv/bin/activate" ]; then
    echo "First launch: installing the Mac environment..."
    bash setup.sh || {
        echo "Setup failed. Review the message above."
        read -r -p "Press Enter to close..."
        exit 1
    }
fi

if [ ! -f ".env" ]; then
    cp .env.example .env
fi

if grep -q "your_zhipu_api_key_here" .env; then
    echo "Please enter a Zhipu API key in the .env file that is opening now."
    open -e .env 2>/dev/null || true
    echo "Save .env, then double-click Start Mac.command again."
    read -r -p "Press Enter to close..."
    exit 1
fi

bash run.sh

if [ $? -ne 0 ]; then
    read -r -p "The app stopped. Press Enter to close..."
fi
