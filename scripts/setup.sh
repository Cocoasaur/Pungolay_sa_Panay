#!/usr/bin/env bash
# PUNGOLAY SA PANAY - setup for Linux / macOS
set -e
cd "$(dirname "$0")/.."

echo "== Creating virtual environment =="
python3 -m venv .venv
source .venv/bin/activate

echo "== Installing dependencies =="
pip install --upgrade pip
pip install -r requirements.txt

echo "== Downloading pose model + fonts =="
python tools/setup_assets.py

echo
echo "Setup complete. Run the game with:"
echo "    source .venv/bin/activate && python main.py"