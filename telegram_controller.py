#!/usr/bin/env python3
"""
Telegram Bot Controller for Solana Pump.fun Bot
Remote management and monitoring via Telegram
"""
import os
import sys
import json
import asyncio
import subprocess
import psutil
from datetime import datetime
from typing import Optional, Dict, Any
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
except ImportError:
    print("Installing python-telegram-bot...")
    subprocess.run([sys.executable, "-m", "pip", "install", "python-telegram-bot"])
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class BotController:
    """Telegram bot controller for managing the trading bot."""
    
    def __init__(self, bot_token: str, authorized_users: list):
        self.bot_token = bot_token
        self.authorized_users = authorized_users
        self.bot_process = None
        self.bot_mode = "stopped"  # stopped, dry_run, production
        self.web_monitor_process = None
        
    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized."""
        return user_id in self.authorized_users
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not self.is_authorized(update.effective_user.id):
            await update.message.reply_text("❌ Unauthorized access")
            return
            
        keyboard = [
            [InlineKeyboardButton("📊 Status", callback_data="status")],
            [InlineKeyboardButton("🔄 Start Dry Run", callback_data="start_dry")],
            [InlineKeyboardButton("🚀 Start Production", callback_data="start_prod")],
            [InlineKeyboardButton("⏹️ Stop Bot", callback_data="stop")],
            [InlineKeyboardButton("📈 View Stats", callback_data="stats")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🤖 *Solana Pump.fun Bot Controller*\n\n"
            "Choose an action:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks."""
        query = update.callback_query
        await query.answer()
        
        if not self.is_authorized(query.from_user.id):
            await query.edit_message_text("❌ Unauthorized access")
            return
            
        data = query.data
        
        if data == "status":
            await self.show_status(query)
        elif data == "start_dry":
            await self.start_bot(query, dry_run=True)
        elif data == "start_prod":
            await self.start_bot(query, dry_run=False)
        elif data == "stop":
            await self.stop_bot(query)
        elif data == "stats":
            await self.show_stats(query)
        elif data == "settings":
            await self.show_settings(query)
        elif data.startswith("config_"):
            await self.handle_config(query, data)
            
    async def show_status(self, query):
        """Show bot status."""
        status_text = f"🤖 *Bot Status Report*\n\n"
        
        # Bot process status
        if self.bot_process and self.bot_process.poll() is None:
            status_text += f"🟢 Bot: Running ({self.bot_mode})\n"
            status_text += f"📊 PID: {self.bot_process.pid}\n"
        else:
            status_text += f"🔴 Bot: Stopped\n"
            
        # Web monitor status
        if self.web_monitor_process and self.web_monitor_process.poll() is None:
            status_text += f"🌐 Web Monitor: Running\n"
            status_text += f"🔗 http://localhost:8889\n"
        else:
            status_text += f"🔴 Web Monitor: Stopped\n"
            
        # System resources
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            status_text += f"\n💻 *System Resources:*\n"
            status_text += f"🔹 CPU: {cpu_percent:.1f}%\n"
            status_text += f"🔹 Memory: {memory.percent:.1f}%\n"
            status_text += f"🔹 Disk: {disk.percent:.1f}%\n"
        except:
            pass
            
        # Wallet balance
        try:
            with open("config/wallet.json", 'r') as f:
                wallet_data = json.load(f)
            balance = await self.get_wallet_balance(wallet_data["public_key"])
            status_text += f"\n💰 *Wallet:*\n"
            status_text += f"🔹 Balance: {balance:.6f} SOL\n"
            status_text += f"🔹 Address: `{wallet_data['public_key'][:8]}...{wallet_data['public_key'][-8:]}`\n"
        except:
            status_text += f"\n💰 *Wallet:* Error reading\n"
            
        status_text += f"\n⏰ Updated: {datetime.now().strftime('%H:%M:%S')}"
        
        keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="status")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            status_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    async def start_bot(self, query, dry_run: bool = True):
        """Start the trading bot."""
        if self.bot_process and self.bot_process.poll() is None:
            await query.edit_message_text("⚠️ Bot is already running")
            return
            
        try:
            mode = "dry_run" if dry_run else "production"
            script = "src/main_dry_run.py" if dry_run else "src/main.py"
            
            # Start bot process
            self.bot_process = subprocess.Popen([
                sys.executable, script
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            self.bot_mode = mode
            
            # Start web monitor on different port
            if not (self.web_monitor_process and self.web_monitor_process.poll() is None):
                env = os.environ.copy()
                env['WEB_MONITOR_PORT'] = '8889'  # Different port to avoid conflicts
                
                self.web_monitor_process = subprocess.Popen([
                    sys.executable, "simple_web_monitor.py"
                ], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            mode_emoji = "🧪" if dry_run else "🚀"
            await query.edit_message_text(
                f"{mode_emoji} *Bot Started Successfully!*\n\n"
                f"📊 Mode: {mode.title()}\n"
                f"🌐 Web Monitor: http://localhost:8889\n"
                f"⏰ Started: {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"{'⚠️ *Dry Run Mode* - No real trades' if dry_run else '💰 *Production Mode* - Real money!'}",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error starting bot: {str(e)}")
            
    async def stop_bot(self, query):
        """Stop the trading bot."""
        stopped_processes = []
        
        # Stop bot process
        if self.bot_process and self.bot_process.poll() is None:
            self.bot_process.terminate()
            try:
                self.bot_process.wait(timeout=10)
                stopped_processes.append("Trading Bot")
            except subprocess.TimeoutExpired:
                self.bot_process.kill()
                stopped_processes.append("Trading Bot (force killed)")
            self.bot_process = None
            
        # Stop web monitor
        if self.web_monitor_process and self.web_monitor_process.poll() is None:
            self.web_monitor_process.terminate()
            try:
                self.web_monitor_process.wait(timeout=5)
                stopped_processes.append("Web Monitor")
            except subprocess.TimeoutExpired:
                self.web_monitor_process.kill()
                stopped_processes.append("Web Monitor (force killed)")
            self.web_monitor_process = None
            
        self.bot_mode = "stopped"
        
        if stopped_processes:
            await query.edit_message_text(
                f"⏹️ *Bot Stopped*\n\n"
                f"Stopped: {', '.join(stopped_processes)}\n"
                f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
            )
        else:
            await query.edit_message_text("ℹ️ Bot was already stopped")
            
    async def show_stats(self, query):
        """Show trading statistics."""
        try:
            stats_text = "📊 *Trading Statistics*\n\n"
            
            # Parse logs for basic stats
            log_path = "logs/pump_bot.log"
            if os.path.exists(log_path):
                with open(log_path, 'r') as f:
                    lines = f.readlines()[-1000:]  # Last 1000 lines
                    
                buy_trades = len([l for l in lines if "BUY executed" in l])
                sell_trades = len([l for l in lines if "SELL executed" in l])
                profitable = len([l for l in lines if "SELL executed" in l and "Profit: +" in l])
                
                win_rate = (profitable / sell_trades * 100) if sell_trades > 0 else 0
                
                stats_text += f"🔹 Buy Trades: {buy_trades}\n"
                stats_text += f"🔹 Sell Trades: {sell_trades}\n"
                stats_text += f"🔹 Profitable: {profitable}\n"
                stats_text += f"🔹 Win Rate: {win_rate:.1f}%\n"
            else:
                stats_text += "No trading data available\n"
                
            # Add wallet balance
            try:
                with open("config/wallet.json", 'r') as f:
                    wallet_data = json.load(f)
                balance = await self.get_wallet_balance(wallet_data["public_key"])
                stats_text += f"\n💰 Current Balance: {balance:.6f} SOL\n"
            except:
                pass
                
            stats_text += f"\n⏰ Updated: {datetime.now().strftime('%H:%M:%S')}"
            
            keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="stats")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                stats_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error getting stats: {str(e)}")
            
    async def show_settings(self, query):
        """Show bot settings."""
        try:
            with open("config/settings.json", 'r') as f:
                settings = json.load(f)
                
            settings_text = "⚙️ *Bot Settings*\n\n"
            trading = settings.get("trading", {})
            
            settings_text += f"🔹 Buy Amount: {trading.get('buy_amount_sol', 0)} SOL\n"
            settings_text += f"🔹 Max Positions: {trading.get('max_positions', 0)}\n"
            settings_text += f"🔹 Take Profit: {trading.get('take_profit_percentage', 0)}%\n"
            settings_text += f"🔹 Stop Loss: {trading.get('stop_loss_percentage', 0)}%\n"
            
            keyboard = [
                [InlineKeyboardButton("💰 Change Buy Amount", callback_data="config_buy_amount")],
                [InlineKeyboardButton("📊 Change Max Positions", callback_data="config_max_pos")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="settings")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                settings_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error reading settings: {str(e)}")
            
    async def handle_config(self, query, data):
        """Handle configuration changes."""
        config_type = data.replace("config_", "")
        
        if config_type == "buy_amount":
            await query.edit_message_text(
                "💰 *Change Buy Amount*\n\n"
                "Send a message with the new buy amount in SOL\n"
                "Example: 0.002\n\n"
                "⚠️ Be careful with production mode!"
            )
        elif config_type == "max_pos":
            await query.edit_message_text(
                "📊 *Change Max Positions*\n\n"
                "Send a message with the new max positions\n"
                "Example: 3\n\n"
                "Current positions will not be affected"
            )
            
    async def get_wallet_balance(self, public_key: str) -> float:
        """Get wallet balance from Solana RPC."""
        try:
            import requests
            
            response = requests.post(
                "https://api.mainnet-beta.solana.com",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getBalance",
                    "params": [public_key]
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    return result["result"]["value"] / 1_000_000_000
                    
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            
        return 0.0
        
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors."""
        logger.error(f"Exception while handling an update: {context.error}")
        
    def run(self):
        """Run the Telegram bot."""
        application = Application.builder().token(self.bot_token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CallbackQueryHandler(self.button_callback))
        application.add_error_handler(self.error_handler)
        
        logger.info("Telegram Bot Controller started")
        application.run_polling()


def main():
    """Main entry point."""
    # Load configuration
    try:
        # Check for environment variables first
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        authorized_users_str = os.getenv("TELEGRAM_AUTHORIZED_USERS", "")
        
        if not bot_token:
            # Try to load from config file
            config_path = "telegram_config.json"
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    bot_token = config.get("bot_token")
                    authorized_users_str = ",".join(map(str, config.get("authorized_users", [])))
        
        if not bot_token:
            print("❌ Telegram bot token not found!")
            print("Set TELEGRAM_BOT_TOKEN environment variable or create telegram_config.json")
            print("\nExample telegram_config.json:")
            print(json.dumps({
                "bot_token": "YOUR_BOT_TOKEN_HERE",
                "authorized_users": [123456789]
            }, indent=2))
            return
            
        # Parse authorized users
        authorized_users = []
        if authorized_users_str:
            try:
                authorized_users = [int(uid.strip()) for uid in authorized_users_str.split(",") if uid.strip()]
            except ValueError:
                print("❌ Invalid authorized users format")
                return
                
        if not authorized_users:
            print("⚠️ No authorized users specified! Bot will be accessible to everyone.")
            print("Set TELEGRAM_AUTHORIZED_USERS environment variable or add to telegram_config.json")
            
        # Start the controller
        controller = BotController(bot_token, authorized_users)
        controller.run()
        
    except KeyboardInterrupt:
        print("\n👋 Telegram controller stopped")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()