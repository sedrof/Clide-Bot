#!/bin/bash
# Deployment script for pump-bot

cd /home/azureuser/pump-bot

echo "Installing Python dependencies in user space..."
export PATH="/home/azureuser/.local/bin:$PATH"

# Install pip if not available
which pip3 || python3 -m pip install --user --upgrade pip

echo "Installing dependencies..."
# Install using python3 -m pip to ensure we use the right Python
python3 -m pip install --user --upgrade pip wheel setuptools

# Install main requirements (skip those that fail)
python3 -m pip install --user solana solders aiohttp websockets python-dateutil || true

# Install additional dependencies for telegram bot and monitoring
python3 -m pip install --user python-telegram-bot psutil requests aiofiles aiohttp-cors

# Verify critical imports
python3 -c 'import telegram; print("✓ telegram module OK")'
python3 -c 'import psutil; print("✓ psutil module OK")'
python3 -c 'import aiofiles; print("✓ aiofiles module OK")'

echo "Setting up directories..."
mkdir -p logs
chmod 755 logs

echo "Dependencies installed successfully"