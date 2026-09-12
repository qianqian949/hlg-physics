#!/bin/bash
set -e

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f "venv/bin/activate" ]; then
    echo "Mac environment is not installed yet. Run ./setup.sh first."
    exit 1
fi

if [ ! -f ".env" ] || grep -q "your_zhipu_api_key_here" .env; then
    echo "Zhipu API key is not configured."
    echo "Open .env and replace the placeholder after ZHIPU_API_KEY=."
    if command -v open >/dev/null 2>&1; then
        open -e .env 2>/dev/null || true
    fi
    exit 1
fi

source venv/bin/activate
echo "Starting Research Logic Graph Extractor at http://localhost:8650"
exec python -m streamlit run app.py --server.port 8650
