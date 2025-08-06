#!/bin/bash
# Deployment script for pump-bot using existing conda environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Navigate to bot directory
cd /home/azureuser/pump-bot

print_status "Activating conda environment myenv39..."
source /home/azureuser/miniconda3/etc/profile.d/conda.sh
conda activate myenv39

print_status "Python version:"
python --version

print_status "Installing only necessary additional dependencies..."

# Core dependencies that might not be in the shared environment
DEPS_TO_INSTALL=""

# Check and add missing dependencies
python -c "import telegram" 2>/dev/null || DEPS_TO_INSTALL="$DEPS_TO_INSTALL python-telegram-bot"
python -c "import psutil" 2>/dev/null || DEPS_TO_INSTALL="$DEPS_TO_INSTALL psutil"
python -c "import aiofiles" 2>/dev/null || DEPS_TO_INSTALL="$DEPS_TO_INSTALL aiofiles"
python -c "import aiohttp" 2>/dev/null || DEPS_TO_INSTALL="$DEPS_TO_INSTALL aiohttp"
python -c "import aiohttp_cors" 2>/dev/null || DEPS_TO_INSTALL="$DEPS_TO_INSTALL aiohttp-cors"
python -c "import dotenv" 2>/dev/null || DEPS_TO_INSTALL="$DEPS_TO_INSTALL python-dotenv"
python -c "import rich" 2>/dev/null || DEPS_TO_INSTALL="$DEPS_TO_INSTALL rich"
python -c "import yaml" 2>/dev/null || DEPS_TO_INSTALL="$DEPS_TO_INSTALL PyYAML"

# For Solana dependencies (if not already installed)
python -c "import solana" 2>/dev/null || DEPS_TO_INSTALL="$DEPS_TO_INSTALL solana"
python -c "import websockets" 2>/dev/null || DEPS_TO_INSTALL="$DEPS_TO_INSTALL websockets"
python -c "import base58" 2>/dev/null || DEPS_TO_INSTALL="$DEPS_TO_INSTALL base58"

if [ -n "$DEPS_TO_INSTALL" ]; then
    print_status "Installing missing dependencies: $DEPS_TO_INSTALL"
    pip install $DEPS_TO_INSTALL
else
    print_success "All required dependencies are already installed"
fi

# Verify critical imports
print_status "Verifying critical imports..."
python -c 'import telegram; print("✓ telegram module OK")'
python -c 'import psutil; print("✓ psutil module OK")'
python -c 'import aiofiles; print("✓ aiofiles module OK")'
python -c 'import aiohttp; print("✓ aiohttp module OK")'

print_status "Setting up directories..."
mkdir -p logs
chmod 755 logs

print_success "Deployment completed successfully using conda environment myenv39"