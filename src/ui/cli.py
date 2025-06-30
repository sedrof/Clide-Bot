"""
CLI UI for the Solana pump.fun sniping bot.
Provides a real-time interface to monitor bot activities, wallet balance, PnL, and trades.
"""
# File Location: src/ui/cli.py

import asyncio
from typing import List, Dict, Any, Optional
import time
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich import box

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.core.wallet_manager import wallet_manager
from src.monitoring.wallet_tracker import wallet_tracker
from src.trading.strategy_engine import strategy_engine

logger = get_logger("cli_ui")
console = Console()

class BotCLI:
    """CLI UI for the Solana pump.fun sniping bot."""
    
    def __init__(self):
        self.layout = Layout()
        self.live = None
        self.running = False
        self.tracked_wallet_activity = []
        self.bot_actions = []
        self.trades = []
        self.balance = 0.0
        self.pnl = 0.0
        self.max_lines = 10  # Max lines to display in activity logs
        self.main_layout = None
        self.top_layout = None
        self.bottom_layout = None
        
        self._setup_layout()
        self._register_callbacks()
    
    def _setup_layout(self):
        """Setup the layout for the CLI UI."""
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=2)
        )
        
        # Header with title
        self.layout["header"].update(
            Panel(
                Text("Solana Pump.fun Sniper Bot", style="bold cyan", justify="center"),
                border_style="cyan",
                box=box.ROUNDED
            )
        )
        
        # Footer with status
        self.layout["footer"].update(
            Panel(
                Text("Status: Running", style="green", justify="center"),
                border_style="green",
                box=box.ROUNDED
            )
        )
        
        # Main layout split into columns
        self.main_layout = Layout()
        self.main_layout.split_column(
            Layout(name="top", ratio=1),
            Layout(name="bottom", size=8)
        )
        
        # Top part split into two for wallet activity and bot actions
        self.top_layout = Layout()
        self.top_layout.split_row(
            Layout(name="wallet_activity", ratio=1),
            Layout(name="bot_actions", ratio=1)
        )
        
        # Wallet activity panel
        self.top_layout["wallet_activity"].update(
            Panel(
                self._render_wallet_activity(),
                title="Tracked Wallet Activity",
                border_style="blue",
                box=box.ROUNDED
            )
        )
        
        # Bot actions panel
        self.top_layout["bot_actions"].update(
            Panel(
                self._render_bot_actions(),
                title="Bot Actions",
                border_style="magenta",
                box=box.ROUNDED
            )
        )
        
        self.main_layout["top"].update(self.top_layout)
        
        # Bottom part for trades and balance
        self.bottom_layout = Layout()
        self.bottom_layout.split_row(
            Layout(name="trades", ratio=3),
            Layout(name="balance", ratio=1)
        )
        
        # Trades table
        self.bottom_layout["trades"].update(
            Panel(
                self._render_trades(),
                title="Recent Trades",
                border_style="yellow",
                box=box.ROUNDED
            )
        )
        
        # Balance and PnL
        self.bottom_layout["balance"].update(
            Panel(
                self._render_balance(),
                title="Wallet Stats",
                border_style="green",
                box=box.ROUNDED
            )
        )
        
        self.main_layout["bottom"].update(self.bottom_layout)
        self.layout["main"].update(self.main_layout)
    
    def _render_wallet_activity(self) -> Text:
        """Render tracked wallet activity log."""
        text = Text()
        for activity in self.tracked_wallet_activity[-self.max_lines:]:
            text.append(activity + "\n")
        return text
    
    def _render_bot_actions(self) -> Text:
        """Render bot actions log."""
        text = Text()
        for action in self.bot_actions[-self.max_lines:]:
            text.append(action + "\n")
        return text
    
    def _render_trades(self) -> Table:
        """Render recent trades table."""
        table = Table(show_header=True, header_style="bold yellow")
        table.add_column("Time", style="dim")
        table.add_column("Type")
        table.add_column("Token")
        table.add_column("Amount")
        table.add_column("Price")
        
        for trade in self.trades[-5:]:  # Show last 5 trades
            table.add_row(
                trade["time"],
                Text(trade["type"], style="green" if trade["type"] == "BUY" else "red"),
                trade["token"],
                str(trade["amount"]),
                str(trade["price"])
            )
        return table
    
    def _render_balance(self) -> Text:
        """Render wallet balance and PnL."""
        text = Text()
        text.append(f"Balance: {self.balance:.4f} SOL\n", style="bold green")
        pnl_style = "green" if self.pnl >= 0 else "red"
        text.append(f"PnL: {self.pnl:.4f} SOL", style=f"bold {pnl_style}")
        return text
    
    def _register_callbacks(self):
        """Register callbacks for bot events."""
        try:
            if wallet_tracker:
                wallet_tracker.register_buy_callback(self._on_wallet_buy)
                logger.info("Registered wallet buy callback with UI")
            if strategy_engine:
                strategy_engine.register_trade_callback(self._on_bot_trade)
                logger.info("Registered trade callback with UI")
        except Exception as e:
            logger.error(f"Error registering callbacks: {e}")
    
    def _on_wallet_buy(self, wallet_address: str, token_address: str, amount_sol: float):
        """Callback for when a tracked wallet buys a token."""
        timestamp = time.strftime("%H:%M:%S")
        activity = f"[{timestamp}] Wallet {wallet_address[:8]}... bought {token_address[:8]}... for {amount_sol:.2f} SOL"
        self.tracked_wallet_activity.append(Text(activity, style="blue"))
        if self.live:
            self._update_ui()
    
    def _on_bot_trade(self, trade_type: str, token_address: str, amount: float, price: float):
        """Callback for when the bot executes a trade."""
        timestamp = time.strftime("%H:%M:%S")
        action = f"[{timestamp}] {trade_type} {token_address[:8]}... - {amount:.2f} @ {price:.6f} SOL"
        self.bot_actions.append(Text(action, style="green" if trade_type == "BUY" else "red"))
        self.trades.append({
            "time": timestamp,
            "type": trade_type,
            "token": token_address[:8] + "...",
            "amount": amount,
            "price": price
        })
        if self.live:
            self._update_ui()
    
    async def _update_balance(self):
        """Update wallet balance and PnL periodically."""
        # Wait a bit for initialization to complete
        await asyncio.sleep(5)
        while self.running:
            try:
                # Wait for wallet manager to be initialized
                balance = 0.0
                try:
                    balance = await wallet_manager.get_balance()
                    logger.info(f"Balance updated: {balance} SOL")
                except Exception as e:
                    logger.warning(f"Wallet balance retrieval failed: {e}")
                self.balance = balance
                # PnL calculation would depend on tracking initial balance and trade outcomes
                # For simplicity, we'll just show a placeholder
                self.pnl = 0.0  # Placeholder until full trade tracking is implemented
                if self.live:
                    self._update_ui()
                    logger.info("UI updated with new balance")
            except Exception as e:
                logger.error(f"Error updating balance: {e}")
            await asyncio.sleep(5)  # Update more frequently
    
    def _update_ui(self):
        """Update the UI components with new data."""
        try:
            if not self.top_layout or not self.bottom_layout:
                logger.warning("Layouts not initialized during update")
                return
                
            # Access nested layouts properly using instance variables
            self.top_layout["wallet_activity"].update(
                Panel(
                    self._render_wallet_activity(),
                    title="Tracked Wallet Activity",
                    border_style="blue",
                    box=box.ROUNDED
                )
            )
            self.top_layout["bot_actions"].update(
                Panel(
                    self._render_bot_actions(),
                    title="Bot Actions",
                    border_style="magenta",
                    box=box.ROUNDED
                )
            )
            self.bottom_layout["trades"].update(
                Panel(
                    self._render_trades(),
                    title="Recent Trades",
                    border_style="yellow",
                    box=box.ROUNDED
                )
            )
            self.bottom_layout["balance"].update(
                Panel(
                    self._render_balance(),
                    title="Wallet Stats",
                    border_style="green",
                    box=box.ROUNDED
                )
            )
        except Exception as e:
            logger.error(f"Error updating UI: {e}")
    
    async def start(self):
        """Start the CLI UI."""
        self.running = True
        # Start balance update task
        asyncio.create_task(self._update_balance())
        # Start live display
        logger.info("Starting UI live display")
        with Live(self.layout, refresh_per_second=2, screen=True) as live:
            self.live = live
            logger.info("UI live display started")
            while self.running:
                await asyncio.sleep(1)  # Keep the UI running
    
    def stop(self):
        """Stop the CLI UI."""
        self.running = False
        if self.live:
            self.live.stop()
        self.layout["footer"].update(
            Panel(
                Text("Status: Stopped", style="red", justify="center"),
                border_style="red",
                box=box.ROUNDED
            )
        )


# Global CLI UI instance (will be initialized later)
bot_cli = None

def initialize_bot_cli():
    """Initialize the global bot CLI instance."""
    global bot_cli
    bot_cli = BotCLI()
    return bot_cli
