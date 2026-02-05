#!/bin/bash
# Quick install script for II-Telegram-Agent

set -e

echo "\ud83e\udd16 II-Telegram-Agent Quick Install"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "\u274c Python 3.10 or higher is required (found $PYTHON_VERSION)"
    exit 1
fi

echo "\u2705 Python $PYTHON_VERSION detected"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "\ud83d\udce6 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate
source venv/bin/activate

# Install
echo "\ud83d\udce6 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -e .

# Initialize
echo "\ud83d\udd27 Initializing..."
python -m ii_telegram_agent.cli init

echo ""
echo "\u2705 Installation complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your tokens"
echo "2. Run: source venv/bin/activate"
echo "3. Run: ii-telegram serve"