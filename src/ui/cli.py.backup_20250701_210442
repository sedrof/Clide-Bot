"""
Enhanced CLI UI for the Solana pump.fun sniping bot.
Fixed version with proper layout structure and no justify errors.
"""
# File Location: src/ui/cli.py

import asyncio
from typing import List, Dict, Any, Optional
import time
from datetime import datetime
from dataclasses import dataclass
from collections import deque

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich import box
from rich.align import Align

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.core.wallet_manager import wallet_manager
from src.core.connection_manager import connection_manager

logger = get_logger("cli_ui")
console = Console()


@dataclass
class Trade:
    """Represents a trade executed by the bot."""
    trade_type: str
    token_address: str
    amount: float
    price: float
    timestamp: float
    pnl: float = 0.0


class BotCLI:
    """Enhanced CLI UI for the Solana pump.fun sniping bot."""
    
    def __init__(self):
        self.layout = Layout()
        self.live = None
        self.running = False
        
        # Data storage
        self.tracked_wallet_activity = deque(maxlen=10)  # Reduced for cleaner display
        self.bot_actions = deque(maxlen=10)
        self.trades: List[Trade] = []
        self.token_holdings: Dict[str, Dict[str, float]] = {}
        
        # Statistics
        self.wallet_balance = 0.0
        self.initial_balance = 0.0
        self.performance_history = deque(maxlen=50)
        
        self.stats = {
            "total_trades": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "total_volume": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "win_rate": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "buy_signals": 0,
            "transactions_monitored": 0,
            "connection_status": "🔴 Disconnected",
            "websocket_status": "🔴 Disconnected",
            "last_update": time.time()
        }
        
        self._setup_layout()
    
    def _setup_layout(self):
        """Setup the enhanced layout for the CLI UI."""
        # Main layout structure with better proportions
        self.layout.split(
            Layout(name="header", size=4),     # Increased header size
            Layout(name="body", ratio=1),
            Layout(name="footer", size=4)      # Increased footer size
        )
        
        # Header
        self._update_header()
        
        # Body - reorganized for better readability
        body = self.layout["body"]
        body.split_column(
            Layout(name="top_row", size=15),    # Stats and tracking
            Layout(name="middle_row", ratio=1), # Activity and holdings
            Layout(name="bottom_row", size=12)  # Trades
        )
        
        # Top row - Stats and Tracking side by side
        body["top_row"].split_row(
            Layout(name="stats", ratio=1),
            Layout(name="tracking", ratio=1)
        )
        
        # Middle row - Activity and Holdings
        body["middle_row"].split_row(
            Layout(name="activity", ratio=2),
            Layout(name="holdings", ratio=1)
        )
        
        # Bottom row - Trades table
        body["bottom_row"].update(Layout(name="trades"))
        
        # Initialize all panels
        self._initialize_panels()
    
    def _update_header(self):
        """Update header with title and status."""
        status_color = "green" if self.running else "red"
        
        # Create title and status texts
        title_text = Text()
        title_text.append("🚀 ", style="bold")
        title_text.append("SOLANA PUMP.FUN SNIPER BOT", style="bold cyan")
        
        status_text = Text()
        status_text.append("Status: ", style="dim")
        status_text.append(f"{'RUNNING' if self.running else 'STOPPED'}", style=f"bold {status_color}")
        status_text.append(" | ", style="dim")
        status_text.append(f"Balance: {self.wallet_balance:.4f} SOL", style="yellow")
        
        # Create combined content panel
        combined_text = Text()
        combined_text.append(title_text)
        combined_text.append("\n")
        combined_text.append(status_text)
        
        # Update header with centered content
        self.layout["header"].update(
            Panel(
                Align.center(combined_text),
                border_style="cyan",
                box=box.DOUBLE
            )
        )
    
    def _update_footer(self):
        """Update footer with connection status."""
        footer_text = Text()
        footer_text.append(f"RPC: {self.stats['connection_status']} | ", style="dim")
        footer_text.append(f"WS: {self.stats['websocket_status']} | ", style="dim")
        footer_text.append("Press Ctrl+C to stop", style="dim yellow")
        
        self.layout["footer"].update(
            Panel(
                Align.center(footer_text),
                border_style="dim",
                box=box.ROUNDED
            )
        )
    
    def _initialize_panels(self):
        """Initialize all UI panels with default content."""
        # Stats panel
        self._update_stats_panel()
        
        # Tracking panel
        self._update_tracking_panel()
        
        # Activity panel
        self._update_activity_panel()
        
        # Holdings panel
        self._update_holdings_panel()
        
        # Trades panel
        self._update_trades_panel()
        
        # Footer
        self._update_footer()
    
    def _update_stats_panel(self):
        """Update statistics panel."""
        stats_table = Table(
            title="📊 Statistics",
            box=box.SIMPLE,
            show_header=False,
            expand=True
        )
        
        stats_table.add_column("Metric", style="dim")
        stats_table.add_column("Value", justify="right")
        
        # Calculate win rate
        if self.stats["total_trades"] > 0:
            win_rate = (self.stats["successful_trades"] / self.stats["total_trades"]) * 100
        else:
            win_rate = 0.0
        
        # Add stats rows
        stats_table.add_row("Total Trades", f"{self.stats['total_trades']}")
        stats_table.add_row("Win Rate", f"{win_rate:.1f}%")
        stats_table.add_row("Total Volume", f"{self.stats['total_volume']:.4f} SOL")
        stats_table.add_row("Realized PnL", f"{self.stats['realized_pnl']:+.4f} SOL")
        stats_table.add_row("Best Trade", f"{self.stats['best_trade']:+.2f}%")
        stats_table.add_row("Worst Trade", f"{self.stats['worst_trade']:+.2f}%")
        
        self.layout["body"]["top_row"]["stats"].update(
            Panel(stats_table, border_style="green", box=box.ROUNDED)
        )
    
    def _update_tracking_panel(self):
        """Update wallet tracking panel."""
        tracking_table = Table(
            title="👁️ Wallet Tracking",
            box=box.SIMPLE,
            show_header=True,
            expand=True
        )
        
        tracking_table.add_column("Time", style="dim", width=8)
        tracking_table.add_column("Action", width=6)
        tracking_table.add_column("Details", overflow="fold")
        
        # Add recent wallet activities
        for activity in list(self.tracked_wallet_activity)[-5:]:  # Show last 5
            tracking_table.add_row(
                activity.get("time", ""),
                activity.get("action", ""),
                activity.get("details", "")
            )
        
        self.layout["body"]["top_row"]["tracking"].update(
            Panel(tracking_table, border_style="blue", box=box.ROUNDED)
        )
    
    def _update_activity_panel(self):
        """Update bot activity panel."""
        activity_table = Table(
            title="📋 Bot Activity",
            box=box.SIMPLE,
            show_header=True,
            expand=True
        )
        
        activity_table.add_column("Time", style="dim", width=12)
        activity_table.add_column("Event", width=12)
        activity_table.add_column("Details")
        
        # Add recent bot actions
        for action in list(self.bot_actions)[-8:]:  # Show last 8
            activity_table.add_row(
                action.get("time", ""),
                action.get("event", ""),
                action.get("details", "")
            )
        
        self.layout["body"]["middle_row"]["activity"].update(
            Panel(activity_table, border_style="yellow", box=box.ROUNDED)
        )
    
    def _update_holdings_panel(self):
        """Update token holdings panel."""
        holdings_table = Table(
            title="💼 Holdings",
            box=box.SIMPLE,
            show_header=True,
            expand=True
        )
        
        holdings_table.add_column("Token", overflow="fold")
        holdings_table.add_column("Amount", justify="right")
        holdings_table.add_column("PnL", justify="right")
        
        # Add token holdings
        for token_address, holding in self.token_holdings.items():
            pnl = holding.get("pnl", 0.0)
            pnl_color = "green" if pnl >= 0 else "red"
            
            holdings_table.add_row(
                f"{holding.get('symbol', token_address[:8])}",
                f"{holding.get('amount', 0):.2f}",
                f"[{pnl_color}]{pnl:+.2f}%[/{pnl_color}]"
            )
        
        self.layout["body"]["middle_row"]["holdings"].update(
            Panel(holdings_table, border_style="magenta", box=box.ROUNDED)
        )
    
    def _update_trades_panel(self):
        """Update trades history panel."""
        trades_table = Table(
            title="📈 Recent Trades",
            box=box.SIMPLE,
            show_header=True,
            expand=True
        )
        
        trades_table.add_column("Time", style="dim", width=12)
        trades_table.add_column("Type", width=6)
        trades_table.add_column("Token", overflow="fold")
        trades_table.add_column("Amount", justify="right")
        trades_table.add_column("PnL", justify="right")
        
        # Add recent trades (last 5)
        for trade in list(self.trades)[-5:]:
            trade_time = datetime.fromtimestamp(trade.timestamp).strftime("%H:%M:%S")
            trade_color = "green" if trade.trade_type == "BUY" else "red"
            pnl_color = "green" if trade.pnl >= 0 else "red"
            
            trades_table.add_row(
                trade_time,
                f"[{trade_color}]{trade.trade_type}[/{trade_color}]",
                trade.token_address[:8] + "...",
                f"{trade.amount:.4f}",
                f"[{pnl_color}]{trade.pnl:+.2f}%[/{pnl_color}]"
            )
        
        self.layout["body"]["bottom_row"].update(
            Panel(trades_table, border_style="cyan", box=box.ROUNDED)
        )
    
    def register_callbacks(self):
        """Register callbacks with various components."""
        try:
            # Import here to avoid circular imports
            from src.monitoring.wallet_tracker import wallet_tracker
            from src.trading.strategy_engine import strategy_engine
            
            # Register wallet buy callback
            if wallet_tracker:
                wallet_tracker.register_buy_callback(self.handle_wallet_buy)
                logger.info("Registered wallet buy callback with UI")
            
            # Register trade callback
            if strategy_engine:
                strategy_engine.register_trade_callback(self.handle_trade)
                logger.info("Registered trade callback with UI")
                
        except Exception as e:
            logger.error(f"Error registering callbacks: {e}")
    
    def handle_wallet_buy(self, wallet_address: str, token_address: str, amount_sol: float, platform: str = "Unknown", tx_url: str = "") -> None:
        """Handle buy signal from tracked wallet."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Add to tracked wallet activity
        self.tracked_wallet_activity.append({
            "time": timestamp,
            "action": "BUY",
            "details": f"{amount_sol:.4f} SOL on {platform}"
        })
        
        # Update stats
        self.stats["buy_signals"] += 1
        self.stats["transactions_monitored"] += 1
        
        # Refresh UI
        self._update_tracking_panel()
        self._update_stats_panel()
    
    def handle_trade(self, trade_data: Dict[str, Any]) -> None:
        """Handle trade execution from strategy engine."""
        timestamp = time.time()
        
        # Create trade object
        trade = Trade(
            trade_type=trade_data["type"].upper(),
            token_address=trade_data["token"],
            amount=trade_data.get("amount_sol", 0.0),
            price=0.0,  # Would need price data
            timestamp=timestamp,
            pnl=0.0
        )
        
        # Add to trades list
        self.trades.append(trade)
        
        # Add to bot actions
        self.bot_actions.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "event": f"{trade_data['type'].upper()}",
            "details": f"{trade_data['token'][:8]}... for {trade_data.get('amount_sol', 0):.4f} SOL"
        })
        
        # Update stats
        self.stats["total_trades"] += 1
        if trade_data.get("success", True):
            self.stats["successful_trades"] += 1
        self.stats["total_volume"] += trade_data.get("amount_sol", 0.0)
        
        # Refresh UI
        self._update_activity_panel()
        self._update_trades_panel()
        self._update_stats_panel()
    
    async def _update_balance(self):
        """Periodically update wallet balance."""
        while self.running:
            try:
                balance = await wallet_manager.get_balance()
                self.wallet_balance = balance
                
                if self.initial_balance == 0:
                    self.initial_balance = balance
                
                # Update connection status
                self.stats["connection_status"] = "🟢 Connected"
                
                # Refresh header
                self._update_header()
                
            except Exception as e:
                logger.error(f"Error updating balance: {e}")
                self.stats["connection_status"] = "🔴 Error"
                
            await asyncio.sleep(5)  # Update every 5 seconds
    
    async def start(self):
        """Start the CLI UI."""
        self.running = True
        self._update_header()
        
        # Register callbacks
        self.register_callbacks()
        
        # Start balance update task
        asyncio.create_task(self._update_balance())
        
        # Start live display with faster refresh
        logger.info("Starting UI live display")
        with Live(self.layout, refresh_per_second=4, screen=True) as live:
            self.live = live
            logger.info("UI live display started")
            
            while self.running:
                await asyncio.sleep(0.25)  # Faster update loop
    
    def stop(self):
        """Stop the CLI UI."""
        self.running = False
        if self.live:
            self.live.stop()
        
        # Update header to show stopped status
        self._update_header()


# Global CLI UI instance
bot_cli = None

def initialize_bot_cli():
    """Initialize the global bot CLI instance."""
    global bot_cli
    bot_cli = BotCLI()
    return bot_cli
