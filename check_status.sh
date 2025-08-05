#!/bin/bash
# Quick status check script for pump-bot

echo "🔍 Pump.fun Bot Status Check"
echo "============================"

# Check systemd services
echo "📊 Service Status:"
sudo systemctl status pump-bot-telegram --no-pager | head -5
echo ""
sudo systemctl status pump-bot-web --no-pager | head -5
echo ""
sudo systemctl status pump-bot --no-pager | head -5

# Check if processes are running
echo ""
echo "🔄 Running Processes:"
ps aux | grep -E "(telegram_controller|simple_web_monitor|main.py|main_dry_run.py)" | grep -v grep

# Check listening ports
echo ""
echo "🌐 Open Ports:"
sudo netstat -tlnp | grep -E "(8888|8889)" || echo "No web services listening"

# Check log files
echo ""
echo "📁 Log Files:"
ls -la /home/azureuser/pump-bot/logs/

# Check wallet balance
echo ""
echo "💰 Checking wallet..."
cd /home/azureuser/pump-bot
source venv/bin/activate
python -c "
import json
with open('config/wallet.json', 'r') as f:
    wallet = json.load(f)
print(f\"Wallet: {wallet['public_key'][:8]}...{wallet['public_key'][-8:]}\")
" 2>/dev/null || echo "Could not read wallet"

echo ""
echo "✅ Status check complete!"