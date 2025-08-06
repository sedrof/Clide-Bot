#!/bin/bash
# Start script for Pump.fun Bot services using conda environment

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

# Check if running as azureuser
if [ "$USER" != "azureuser" ]; then
    print_error "This script must be run as azureuser"
    exit 1
fi

# Copy service files to systemd directory
print_status "Installing systemd service files..."
echo "01061359214Asdf" | sudo -S cp /home/azureuser/pump-bot/deployment/pump-bot-telegram-conda.service /etc/systemd/system/
echo "01061359214Asdf" | sudo -S cp /home/azureuser/pump-bot/deployment/pump-bot-web-conda.service /etc/systemd/system/

# Reload systemd daemon
print_status "Reloading systemd daemon..."
echo "01061359214Asdf" | sudo -S systemctl daemon-reload

# Stop old services if they exist
print_status "Stopping old services if running..."
echo "01061359214Asdf" | sudo -S systemctl stop pump-bot-telegram 2>/dev/null || true
echo "01061359214Asdf" | sudo -S systemctl stop pump-bot-web 2>/dev/null || true
echo "01061359214Asdf" | sudo -S systemctl disable pump-bot-telegram 2>/dev/null || true
echo "01061359214Asdf" | sudo -S systemctl disable pump-bot-web 2>/dev/null || true

# Enable and start new services
print_status "Enabling services..."
echo "01061359214Asdf" | sudo -S systemctl enable pump-bot-telegram-conda
echo "01061359214Asdf" | sudo -S systemctl enable pump-bot-web-conda

print_status "Starting Telegram controller service..."
echo "01061359214Asdf" | sudo -S systemctl start pump-bot-telegram-conda

print_status "Starting Web monitor service..."
echo "01061359214Asdf" | sudo -S systemctl start pump-bot-web-conda

# Wait a moment for services to start
sleep 3

# Check service status
print_status "Checking service status..."
if systemctl is-active --quiet pump-bot-telegram-conda; then
    print_success "Telegram controller service is running"
else
    print_error "Telegram controller service failed to start"
    echo "01061359214Asdf" | sudo -S journalctl -u pump-bot-telegram-conda -n 20
fi

if systemctl is-active --quiet pump-bot-web-conda; then
    print_success "Web monitor service is running"
else
    print_error "Web monitor service failed to start"
    echo "01061359214Asdf" | sudo -S journalctl -u pump-bot-web-conda -n 20
fi

print_success "Services started successfully!"
echo ""
echo "📊 Service Management Commands:"
echo "  Check status:  echo "01061359214Asdf" | sudo -S systemctl status pump-bot-telegram-conda"
echo "                 echo "01061359214Asdf" | sudo -S systemctl status pump-bot-web-conda"
echo "  View logs:     echo "01061359214Asdf" | sudo -S journalctl -u pump-bot-telegram-conda -f"
echo "                 echo "01061359214Asdf" | sudo -S journalctl -u pump-bot-web-conda -f"
echo "  Restart:       echo "01061359214Asdf" | sudo -S systemctl restart pump-bot-telegram-conda"
echo "                 echo "01061359214Asdf" | sudo -S systemctl restart pump-bot-web-conda"
echo ""
echo "🌐 Web monitor available at: http://$(hostname -I | awk '{print $1}'):8889"
echo "📱 Control your bot via Telegram"