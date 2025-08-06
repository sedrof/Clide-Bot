#!/bin/bash
# Start pump-bot services

cd /home/azureuser/pump-bot
export PATH="/home/azureuser/.local/bin:$PATH"

# Source environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo "Environment variables loaded"
else
    echo "Warning: .env file not found"
fi

# Kill existing processes
pkill -f telegram_controller.py || true
pkill -f simple_web_monitor.py || true

sleep 2

# Start services with environment variables
nohup python3 telegram_controller.py > logs/telegram_controller.log 2>&1 &
echo "Telegram controller started (PID: $!)"

nohup python3 simple_web_monitor.py > logs/web_monitor.log 2>&1 &
echo "Web monitor started (PID: $!)"

# Check if services are running
sleep 5
if pgrep -f telegram_controller.py > /dev/null; then
    echo "✅ Telegram Controller: Running"
else
    echo "❌ Telegram Controller: Failed to start"
    tail -10 logs/telegram_controller.log
fi

if pgrep -f simple_web_monitor.py > /dev/null; then
    echo "✅ Web Monitor: Running"
else
    echo "❌ Web Monitor: Failed to start"
    tail -10 logs/web_monitor.log
fi