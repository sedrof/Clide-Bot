#!/bin/bash
# Setup script for Pump.fun Bot deployment
# Run this script on your VPS to prepare for deployment

set -e

echo "🚀 Setting up Pump.fun Bot deployment environment..."

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

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as correct user
if [ "$USER" != "azureuser" ]; then
    print_warning "This script should be run as 'azureuser'. Current user: $USER"
    print_warning "Continuing anyway, but paths may need adjustment..."
fi

# Update system packages
print_status "Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install required system packages
print_status "Installing required system packages..."
sudo apt install -y python3 python3-pip python3-venv git curl wget htop

# Install Python packages
print_status "Installing Python dependencies..."
python3 -m pip install --user --upgrade pip setuptools wheel

# Create directory structure
print_status "Creating directory structure..."
mkdir -p /home/azureuser/pump-bot/{config,logs,deployment}

# Set up firewall rules (if ufw is available)
if command -v ufw &> /dev/null; then
    print_status "Configuring firewall for web monitor (port 8889)..."
    sudo ufw allow 8889/tcp
    print_success "Firewall configured"
else
    print_warning "UFW not found, skipping firewall configuration"
fi

# Check for existing services that might conflict
print_status "Checking for port conflicts..."
if netstat -tulpn 2>/dev/null | grep -q ":8889 "; then
    print_warning "Port 8889 is already in use. Web monitor may not start correctly."
    print_warning "Consider changing WEB_MONITOR_PORT in your .env file"
else
    print_success "Port 8889 is available"
fi

# Create systemd directory if it doesn't exist
sudo mkdir -p /etc/systemd/system

# Set up log rotation
print_status "Setting up log rotation..."
sudo tee /etc/logrotate.d/pump-bot > /dev/null << EOF
/home/azureuser/pump-bot/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 644 azureuser azureuser
}
EOF

print_success "Log rotation configured"

# Create environment template
print_status "Creating environment template..."
cat > /home/azureuser/pump-bot/.env.example << EOF
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_AUTHORIZED_USERS=123456789,987654321

# RPC Configuration (Optional)
DRPC_API_KEY=your_drpc_api_key_here

# Web Monitor Configuration
WEB_MONITOR_PORT=8889

# Trading Configuration
DRY_RUN_MODE=true
MAX_BUY_AMOUNT_SOL=0.1
BUY_AMOUNT_SOL=0.001
EOF

print_success "Environment template created at /home/azureuser/pump-bot/.env.example"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
if [ "$(echo "$PYTHON_VERSION >= 3.8" | bc 2>/dev/null)" -eq 1 ] 2>/dev/null; then
    print_success "Python version $PYTHON_VERSION is compatible"
else
    print_warning "Python version $PYTHON_VERSION may not be fully compatible. Python 3.8+ is recommended."
fi

# Create health check script
print_status "Creating health check script..."
cat > /home/azureuser/pump-bot/health_check.sh << 'EOF'
#!/bin/bash
# Health check script for pump-bot services

echo "🏥 Pump.fun Bot Health Check"
echo "============================"

# Check services
services=("pump-bot-telegram" "pump-bot-web")

for service in "${services[@]}"; do
    if systemctl is-active --quiet "$service"; then
        echo "✅ $service: Running"
    else
        echo "❌ $service: Stopped"
    fi
done

# Check if trading bot is running (it's controlled via Telegram)
if pgrep -f "src/main" > /dev/null; then
    echo "✅ Trading bot: Running"
else
    echo "⏸️  Trading bot: Stopped (normal - controlled via Telegram)"
fi

# Check ports
echo ""
echo "🌐 Port Status:"
if netstat -tulpn 2>/dev/null | grep -q ":8889 "; then
    echo "✅ Port 8889: Web monitor running"
else
    echo "❌ Port 8889: Web monitor not accessible"
fi

# Check disk space
echo ""
echo "💾 Disk Usage:"
df -h /home/azureuser/pump-bot | tail -1 | awk '{print "📁 Used: " $3 "/" $2 " (" $5 ")"}'

# Check recent logs
echo ""
echo "📋 Recent Activity:"
if [ -f "/home/azureuser/pump-bot/logs/pump_bot.log" ]; then
    echo "📊 Last log entries:"
    tail -3 /home/azureuser/pump-bot/logs/pump_bot.log 2>/dev/null || echo "No recent logs"
else
    echo "📊 No log file found (normal if bot hasn't started trading)"
fi

echo ""
echo "Run 'sudo systemctl status pump-bot-telegram' for detailed status"
EOF

chmod +x /home/azureuser/pump-bot/health_check.sh
print_success "Health check script created"

print_success "Setup completed successfully!"
echo ""
echo "📋 Next Steps:"
echo "1. Configure your GitHub repository secrets:"
echo "   - SSH_PRIVATE_KEY"
echo "   - HOST (this server's IP)"
echo "   - USERNAME (azureuser)"
echo "   - TELEGRAM_BOT_TOKEN"
echo "   - TELEGRAM_AUTHORIZED_USERS"
echo ""
echo "2. Push your code to trigger deployment, or run manual deployment"
echo ""
echo "3. After deployment, check health with:"
echo "   ./health_check.sh"
echo ""
echo "🌐 Web monitor will be available at: http://$(curl -s ifconfig.me):8889"
echo "📱 Control your bot via Telegram after deployment"

print_success "VPS is ready for Pump.fun Bot deployment! 🚀"