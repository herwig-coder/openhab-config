#!/bin/bash

echo "========================================"
echo "OpenHAB Battery Monitor - Setup"
echo "========================================"
echo

echo "Creating virtual environment..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create virtual environment"
    echo "Make sure Python 3.8+ is installed"
    exit 1
fi

echo
echo "Activating virtual environment..."
source venv/bin/activate

echo
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo
echo "Creating .env file from template..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file - Please edit it with your OpenHAB credentials"
else
    echo ".env file already exists, skipping"
fi

echo
echo "========================================"
echo "Setup complete!"
echo "========================================"
echo
echo "Next steps:"
echo "1. Edit .env file with your OpenHAB URL and API token"
echo "2. Run: source venv/bin/activate"
echo "3. Run: python battery_monitor.py --token YOUR_TOKEN"
echo
echo "Or open this folder in VS Code and press F5 to debug"
echo
