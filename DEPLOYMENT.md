# 🚀 VPS Deployment Guide

Deploy your Solana Pump.fun Bot to a VPS with Telegram remote control and web monitoring.

## 📋 Prerequisites

1. **VPS/Server Requirements:**
   - Ubuntu 20.04+ or similar Linux distribution
   - Python 3.8+
   - At least 1GB RAM
   - SSH access with sudo privileges

2. **Required Accounts:**
   - GitHub repository with your bot code
   - Telegram Bot Token (from @BotFather)
   - Your Telegram User ID

3. **GitHub Secrets to Configure:**
   - `SSH_PRIVATE_KEY` - Your VPS SSH private key
   - `HOST` - Your VPS IP address
   - `USERNAME` - Your VPS username (usually 'azureuser')
   - `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
   - `TELEGRAM_AUTHORIZED_USERS` - Comma-separated Telegram user IDs (e.g., "123456789,987654321")
   - `DRPC_API_KEY` - Your DRPC API key (optional)

## 🎯 Deployment Features

### 📱 Telegram Remote Control
- Start/stop bot remotely
- Switch between dry-run and production modes
- View real-time statistics
- Monitor wallet balance
- Change trading settings
- View logs and activity

### 🌐 Web Dashboard
- Accessible at `http://YOUR_VPS_IP:8889`
- Real-time trading statistics
- Live trade history
- Bot activity logs
- No port conflicts with existing bots

### 🔧 SystemD Services
- `pump-bot-telegram` - Telegram controller (always running)
- `pump-bot-web` - Web monitor (always running)
- `pump-bot` - Trading bot (controlled via Telegram)

## 🛠️ Setup Instructions

### Step 1: Create Telegram Bot

1. Message @BotFather on Telegram
2. Send `/newbot`
3. Choose a name and username
4. Save the bot token

### Step 2: Get Your Telegram User ID

1. Message @userinfobot on Telegram
2. Send `/start`
3. Copy your user ID number

### Step 3: Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these secrets:
```
SSH_PRIVATE_KEY: [Your VPS SSH private key]
HOST: [Your VPS IP address]
USERNAME: azureuser
TELEGRAM_BOT_TOKEN: [Your bot token from BotFather]
TELEGRAM_AUTHORIZED_USERS: [Your Telegram user ID]
DRPC_API_KEY: [Your DRPC API key - optional]
```

### Step 4: Deploy

1. Push your code to the `main` branch or `deploy-pump-bot` branch
2. GitHub Actions will automatically deploy to your VPS
3. Check the Actions tab for deployment progress

## 📊 Port Configuration

To avoid conflicts with existing bots:

| Service | Port | Purpose |
|---------|------|---------|
| Existing Bot | 8888 | Your current trading bot |
| Pump.fun Bot Web | 8889 | Web dashboard |
| Telegram Controller | N/A | Uses Telegram API |

## 🎮 Telegram Bot Commands

Once deployed, message your Telegram bot:

- `/start` - Open the control panel
- Choose from buttons:
  - 📊 **Status** - View bot and system status
  - 🔄 **Start Dry Run** - Start in simulation mode
  - 🚀 **Start Production** - Start with real money
  - ⏹️ **Stop Bot** - Stop trading bot
  - 📈 **View Stats** - Trading statistics
  - ⚙️ **Settings** - Adjust bot settings

## 🔍 Monitoring

### Web Dashboard
- Open `http://YOUR_VPS_IP:8889` in your browser
- View real-time statistics, trades, and logs

### SSH Commands
```bash
# Check service status
sudo systemctl status pump-bot-telegram
sudo systemctl status pump-bot-web
sudo systemctl status pump-bot

# View logs
sudo journalctl -u pump-bot-telegram -f
sudo journalctl -u pump-bot-web -f
sudo journalctl -u pump-bot -f

# Manual service control
sudo systemctl start/stop/restart pump-bot-telegram
sudo systemctl start/stop/restart pump-bot-web
```

## 🔧 Manual Deployment (Alternative)

If you prefer manual deployment:

```bash
# 1. Clone repository on VPS
git clone https://github.com/yourusername/your-repo.git /home/azureuser/pump-bot
cd /home/azureuser/pump-bot

# 2. Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install python-telegram-bot requests psutil

# 3. Create environment file
cat > .env << EOF
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_AUTHORIZED_USERS=your_user_id_here
WEB_MONITOR_PORT=8889
EOF

# 4. Setup services
sudo cp deployment/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pump-bot-telegram pump-bot-web
sudo systemctl start pump-bot-telegram pump-bot-web
```

## 🛡️ Security Notes

1. **Environment Variables**: Sensitive data is stored in `.env` file with restricted permissions (600)
2. **Service Isolation**: Each service runs with limited privileges
3. **Authorized Users**: Only specified Telegram users can control the bot
4. **Network Security**: Consider using a firewall to restrict access to port 8889

## 🚨 Troubleshooting

### Bot not responding on Telegram
```bash
sudo journalctl -u pump-bot-telegram -f
```

### Web dashboard not accessible
```bash
sudo systemctl status pump-bot-web
sudo journalctl -u pump-bot-web -f
```

### Trading bot issues
```bash
# Check if bot is running
sudo systemctl status pump-bot

# View bot logs
tail -f /home/azureuser/pump-bot/logs/pump_bot.log
```

### Port conflicts
```bash
# Check what's using ports
sudo netstat -tulpn | grep :8889
```

## 📞 Support

If you encounter issues:

1. Check the GitHub Actions deployment logs
2. SSH to your VPS and check service logs
3. Verify all environment variables are set correctly
4. Ensure your Telegram bot token is valid
5. Confirm your user ID is in the authorized users list

## 🔄 Updates

To update your bot:

1. Push changes to your GitHub repository
2. GitHub Actions will automatically redeploy
3. Services will restart with new code
4. Check Telegram bot for status updates

---

🎉 **Your bot is now deployed with full remote control capabilities!**