#!/bin/bash
# Complete deployment script to sync and deploy to Ubuntu server

set -e

# Server configuration
SERVER_USER="azureuser"
SERVER_HOST="20.248.114.135"
SSH_KEY="$HOME/.ssh/script_key.pem"
REMOTE_DIR="/home/azureuser/pump-bot"

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

# Ensure SSH key has correct permissions
chmod 600 $SSH_KEY

print_status "Starting deployment to Ubuntu server..."

# Create remote directory if it doesn't exist
print_status "Creating remote directory structure..."
ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST "mkdir -p $REMOTE_DIR/{config,logs,deployment,src/{core,integrations,monitoring,trading,ui,utils}}"

# Sync all necessary files (excluding venv and unnecessary files)
print_status "Syncing files to server..."
rsync -avz --delete \
    --exclude 'venv/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.git/' \
    --exclude '.github/' \
    --exclude 'logs/*.log' \
    --exclude '.env' \
    -e "ssh -i $SSH_KEY" \
    . $SERVER_USER@$SERVER_HOST:$REMOTE_DIR/

# Copy .env file if it exists locally (otherwise use example)
if [ -f ".env" ]; then
    print_status "Copying .env file..."
    scp -i $SSH_KEY .env $SERVER_USER@$SERVER_HOST:$REMOTE_DIR/
else
    print_status "No .env file found locally, creating from example..."
    ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST "cd $REMOTE_DIR && [ ! -f .env ] && cp .env.example .env || true"
fi

# Execute deployment on server
print_status "Running deployment script on server..."
ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST << 'ENDSSH'
cd /home/azureuser/pump-bot

echo "Making scripts executable..."
chmod +x deployment/*.sh

echo "Running conda deployment script..."
bash deployment/deploy_conda.sh

echo "Starting services with conda environment..."
bash deployment/start_services_conda.sh

echo "Checking service status..."
systemctl is-active pump-bot-telegram-conda && echo "✅ Telegram service active" || echo "❌ Telegram service not active"
systemctl is-active pump-bot-web-conda && echo "✅ Web monitor active" || echo "❌ Web monitor not active"

echo "Recent logs from Telegram service:"
sudo journalctl -u pump-bot-telegram-conda -n 10 --no-pager

echo ""
echo "Deployment completed!"
ENDSSH

print_success "Deployment completed successfully!"
echo ""
echo "📊 Next steps:"
echo "1. SSH to server: ssh -i $SSH_KEY $SERVER_USER@$SERVER_HOST"
echo "2. Check services: sudo systemctl status pump-bot-telegram-conda"
echo "3. View logs: sudo journalctl -u pump-bot-telegram-conda -f"
echo "4. Web monitor: http://$SERVER_HOST:8889"