#!/bin/bash

echo "========================================"
echo "Router ACL Controller - Setup"
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
    echo "Created .env — edit it with your router credentials and paths."
else
    echo ".env already exists, skipping."
fi

echo
echo "========================================"
echo "Setup complete!"
echo "========================================"
echo
echo "Next steps:"
echo "  1. Edit .env — set ROUTER_URL, ROUTER_USERNAME, ROUTER_PASSWORD"
echo "  2. Run the probe to discover your router's form paths:"
echo "       source venv/bin/activate"
echo "       python router_acl.py --probe --verbose"
echo "  3. Update .env with the paths found by --probe"
echo "  4. Test: python router_acl.py --status"
echo
