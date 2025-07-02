"""
Enhanced CLI UI for the Solana pump.fun sniping bot.
Provides a real-time interface with improved visuals and tracking display.
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
from rich.progress import Progress, BarColumn, TextColumn

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
        self.tracked_wallet_activity = deque(maxlen=20)  # Last 20 activities
        self.bot_actions = deque(maxlen=20)
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
        # Delay callback registration until components are initialized
    
    def _setup_layout(self):
        """Setup the enhanced layout for the CLI UI."""
        # Main layout structure
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=3)
        )
        
        # Header
        self._update_header()
        
        # Body - 3 columns
        body = self.layout["body"]
        body.split_row(
            Layout(name="left", ratio=1),
            Layout(name="center", ratio=2),
            Layout(name="right", ratio=1)
        )
        
        # Left column - Stats & Performance
        body["left"].split_column(
            Layout(name="stats", size=12),
            Layout(name="performance", ratio=1)
        )
        
        # Center column - Activity & Trades
        body["center"].split_column(
            Layout(name="activity", ratio=1),
            Layout(name="trades", size=15)
        )
        
        # Right column - Holdings & Tracking
        body["right"].split_column(
            Layout(name="holdings", ratio=1),
            Layout(name="tracking", size=12)
        )
        
        # Initialize all panels
        self._initialize_panels()
    
    def _update_header(self):
        """Update header with title and status."""
        status_color = "green" if self.running else "red"
        header_text = Text()
        header_text.append("🚀 ", style="bold")
        header_text.append("Solana Pump.fun Sniper Bot", style="bold cyan")
        header_text.append(" | ", style="dim")
        header_text.append(f"Status: {'Running' if self.running else 'Stopped'}", style=f"bold {status_color}")
        
        self.layout["header"].update(
            Panel(
                header_text,
                border_style="cyan",
                box=box.DOUBLE
            )
        )
    
    def _update_footer(self):
        """Update footer with connection status and controls."""
        footer_text = Text()
        footer_text.append(f"RPC: {self.stats['connection_status']} | ", style="dim")
        footer_text.append(f"WS: {self.stats['websocket_status']} | ", style="dim")
        footer_text.append("Press Ctrl+C to stop", style="dim yellow")
        
        self.layout["footer"].update(
            Panel(
                footer_text,
                border_style="dim",
                box=box.ROUNDED
            )
        )
    
    def _initialize_panels(self):
        """Initialize all UI panels with default content."""
        body = self.layout["body"]
        
        # Stats panel
        body["left"]["stats"].update(self._render_stats())
        
        # Performance panel
        body["left"]["performance"].update(self._render_performance())
        
        # Activity panel
        body["center"]["activity"].update(self._render_activity())
        
        # Trades panel
        body["center"]["trades"].update(self._render_trades())
        
        # Holdings panel
        body["right"]["holdings"].update(self._render_holdings())
        
        # Tracking panel
        body["right"]["tracking"].update(self._render_tracking())
        
        # Footer
        self._update_footer()
    
    def _render_stats(self) -> Panel:
        """Render statistics panel."""
        stats_table = Table(show_header=False, box=None, padding=(0, 1))
        stats_table.add_column("Stat", style="cyan")
        stats_table.add_column("Value", style="white")
        
        # Calculate current PnL
        total_pnl = self.stats["realized_pnl"] + self.stats["unrealized_pnl"]
        pnl_color = "green" if total_pnl >= 0 else "red"
        
        stats_data = [
            ("💰 Balance", f"{self.wallet_balance:.4f} SOL"),
            ("📊 Total PnL", Text(f"{total_pnl:+.4f} SOL", style=pnl_color)),
            ("📈 Win Rate", f"{self.stats['win_rate']:.1f}%"),
            ("🎯 Total Trades", str(self.stats["total_trades"])),
            ("✅ Successful", str(self.stats["successful_trades"])),
            ("❌ Failed", str(self.stats["failed_trades"])),
            ("💎 Best Trade", f"{self.stats['best_trade']:.4f} SOL"),
            ("💸 Worst Trade", f"{self.stats['worst_trade']:.4f} SOL"),
            ("📡 Buy Signals", str(self.stats["buy_signals"])),
        ]
        
        for label, value in stats_data:
            if isinstance(value, Text):
                stats_table.add_row(label, value)
            else:
                stats_table.add_row(label, value)
        
        return Panel(
            stats_table,
            title="📊 Statistics",
            border_style="blue",
            box=box.ROUNDED
        )
    
    def _render_performance(self) -> Panel:
        """Render performance chart panel."""
        # Simple ASCII chart of PnL history
        if not self.performance_history:
            content = Text("No performance data yet...", style="dim")
        else:
            # Create a simple sparkline
            values = list(self.performance_history)
            if values:
                min_val = min(values) if values else 0
                max_val = max(values) if values else 0
                range_val = max_val - min_val if max_val != min_val else 1
                
                # Normalize to 0-7 for 8 height levels
                sparkline = ""
                chars = " ▁▂▃▄▅▆▇█"
                
                for val in values[-20:]:  # Show last 20 points
                    normalized = int(((val - min_val) / range_val) * 7) if range_val > 0 else 0
                    sparkline += chars[normalized]
                
                content = Text()
                content.append("PnL Trend: ", style="dim")
                content.append(sparkline, style="cyan")
                content.append(f"\nRange: {min_val:.2f} to {max_val:.2f} SOL", style="dim")
            else:
                content = Text("Collecting data...", style="dim")
        
        return Panel(
            content,
            title="📈 Performance",
            border_style="green",
            box=box.ROUNDED
        )
    
    def _render_activity(self) -> Panel:
        """Render activity feed panel."""
        activity_table = Table(show_header=True, header_style="bold yellow", box=None)
        activity_table.add_column("Time", style="dim", width=8)
        activity_table.add_column("Event", style="white")
        activity_table.add_column("Details", style="cyan")
        
        # Combine wallet activity and bot actions
        all_activity = []
        
        for activity in self.tracked_wallet_activity:
            all_activity.append(("wallet", activity))
        
        for action in self.bot_actions:
            all_activity.append(("bot", action))
        
        # Sort by timestamp and show most recent
        all_activity.sort(key=lambda x: x[1].get("timestamp", 0), reverse=True)
        
        for activity_type, activity in all_activity[:10]:  # Show last 10
            time_str = datetime.fromtimestamp(activity.get("timestamp", 0)).strftime("%H:%M:%S")
            
            if activity_type == "wallet":
                event = f"👁️ {activity.get('action', 'Unknown')}"
                details = f"{activity.get('wallet', '')[:8]}... → {activity.get('token', '')[:8]}..."
                if activity.get("amount"):
                    details += f" ({activity.get('amount', 0):.3f} SOL)"
            else:
                event = f"🤖 {activity.get('action', 'Unknown')}"
                details = activity.get('details', '')
            
            activity_table.add_row(time_str, event, details)
        
        if not all_activity:
            activity_table.add_row("--:--:--", "Waiting for activity...", "")
        
        return Panel(
            activity_table,
            title="🔔 Live Activity Feed",
            border_style="yellow",
            box=box.ROUNDED
        )
    
    def _render_trades(self) -> Panel:
        """Render recent trades table."""
        trades_table = Table(show_header=True, header_style="bold magenta")
        trades_table.add_column("Time", style="dim", width=8)
        trades_table.add_column("Type", width=6)
        trades_table.add_column("Token", width=12)
        trades_table.add_column("Amount", width=10)
        trades_table.add_column("Price", width=10)
        trades_table.add_column("PnL", width=10)
        
        for trade in self.trades[-8:]:  # Show last 8 trades
            time_str = datetime.fromtimestamp(trade.timestamp).strftime("%H:%M:%S")
            type_color = "green" if trade.trade_type == "BUY" else "red"
            pnl_color = "green" if trade.pnl >= 0 else "red"
            
            trades_table.add_row(
                time_str,
                Text(trade.trade_type, style=type_color),
                f"{trade.token_address[:8]}...",
                f"{trade.amount:.3f}",
                f"{trade.price:.6f}",
                Text(f"{trade.pnl:+.4f}", style=pnl_color) if trade.pnl != 0 else "-"
            )
        
        if not self.trades:
            trades_table.add_row("--:--:--", "-", "No trades yet", "-", "-", "-")
        
        return Panel(
            trades_table,
            title="💹 Recent Trades",
            border_style="magenta",
            box=box.ROUNDED
        )
    
    def _render_holdings(self) -> Panel:
        """Render current token holdings."""
        holdings_table = Table(show_header=True, header_style="bold green")
        holdings_table.add_column("Token", width=12)
        holdings_table.add_column("Amount", width=10)
        holdings_table.add_column("Avg Price", width=10)
        holdings_table.add_column("Current", width=10)
        holdings_table.add_column("PnL %", width=8)
        
        for token, holding in list(self.token_holdings.items())[:6]:  # Show top 6
            if holding["amount"] > 0:
                current_price = holding.get("current_price", holding["avg_price"])
                pnl_percent = ((current_price - holding["avg_price"]) / holding["avg_price"] * 100) if holding["avg_price"] > 0 else 0
                pnl_color = "green" if pnl_percent >= 0 else "red"
                
                holdings_table.add_row(
                    f"{token[:8]}...",
                    f"{holding['amount']:.3f}",
                    f"{holding['avg_price']:.6f}",
                    f"{current_price:.6f}",
                    Text(f"{pnl_percent:+.1f}%", style=pnl_color)
                )
        
        if not any(h["amount"] > 0 for h in self.token_holdings.values()):
            holdings_table.add_row("No holdings", "-", "-", "-", "-")
        
        return Panel(
            holdings_table,
            title="💼 Current Holdings",
            border_style="green",
            box=box.ROUNDED
        )
    
    def _render_tracking(self) -> Panel:
        """Render wallet tracking information."""
        tracking_info = Table(show_header=False, box=None, padding=(0, 1))
        tracking_info.add_column("Label", style="cyan")
        tracking_info.add_column("Value", style="white")
        
        # Get wallet tracker stats if available
        tracker_stats = {}
        try:
            from src.monitoring.wallet_tracker import wallet_tracker
            if wallet_tracker:
                tracker_stats = wallet_tracker.get_stats()
        except:
            pass
        
        tracking_data = [
            ("📍 Tracked Wallets", f"{len(self.tracked_wallet_activity)} active"),
            ("🔍 Total Monitored", f"{tracker_stats.get('transactions_detected', 0)}"),
            ("🟢 Buys Detected", f"{tracker_stats.get('buys_detected', 0)}"),
            ("🔴 Sells Detected", f"{tracker_stats.get('sells_detected', 0)}"),
            ("✨ Creates Detected", f"{tracker_stats.get('creates_detected', 0)}"),
            ("⚠️ Errors", f"{tracker_stats.get('errors', 0)}"),
        ]
        
        for label, value in tracking_data:
            tracking_info.add_row(label, value)
        
        # Add active wallet addresses
        tracking_info.add_row("", "")
        tracking_info.add_row("[bold]Active Wallets:[/bold]", "")
        
        settings = config_manager.get_settings()
        for wallet in settings.tracking.wallets[:3]:  # Show first 3
            tracking_info.add_row("", f"{wallet[:8]}...{wallet[-4:]}")
        
        if len(settings.tracking.wallets) > 3:
            tracking_info.add_row("", f"... and {len(settings.tracking.wallets) - 3} more")
        
        return Panel(
            tracking_info,
            title="🎯 Wallet Tracking",
            border_style="blue",
            box=box.ROUNDED
        )
    
    def _update_ui(self):
        """Update all UI components."""
        try:
            # Update dynamic components
            body = self.layout["body"]
            
            # Update stats
            body["left"]["stats"].update(self._render_stats())
            body["left"]["performance"].update(self._render_performance())
            
            # Update activity
            body["center"]["activity"].update(self._render_activity())
            body["center"]["trades"].update(self._render_trades())
            
            # Update holdings
            body["right"]["holdings"].update(self._render_holdings())
            body["right"]["tracking"].update(self._render_tracking())
            
            # Update footer
            self._update_footer()
            
        except Exception as e:
            logger.error(f"Error updating UI: {e}")
    
    async def _update_balance(self):
        """Update wallet balance periodically."""
        await asyncio.sleep(2)  # Initial delay
        
        # Set initial balance on first update
        first_update = True
        
        while self.running:
            try:
                balance = await wallet_manager.get_balance()
                self.wallet_balance = balance
                
                if first_update:
                    self.initial_balance = balance
                    first_update = False
                
                # Update performance history
                total_pnl = self.stats["realized_pnl"] + self.stats["unrealized_pnl"]
                self.performance_history.append(total_pnl)
                
                # Update connection status
                rpc_connected = await self._check_rpc_connection()
                self.stats["connection_status"] = "🟢 Connected" if rpc_connected else "🔴 Disconnected"
                
                # Update WebSocket status based on wallet tracker
                try:
                    from src.monitoring.wallet_tracker import wallet_tracker
                    if wallet_tracker and hasattr(wallet_tracker, 'websocket') and wallet_tracker.websocket and not wallet_tracker.websocket.closed:
                        self.stats["websocket_status"] = "🟢 Connected"
                    else:
                        self.stats["websocket_status"] = "🔴 Disconnected"
                except:
                    pass
                
                self.stats["last_update"] = time.time()
                
                if self.live:
                    self._update_ui()
                    
            except Exception as e:
                logger.error(f"Error updating balance: {e}")
                
            await asyncio.sleep(3)  # Update every 3 seconds
    
    async def _check_rpc_connection(self) -> bool:
        """Check if RPC connection is active."""
        try:
            client = await connection_manager.get_rpc_client()
            if client:
                # Simple test - get slot
                await client.get_slot()
                return True
        except:
            pass
        return False
    
    def register_callbacks(self):
        """Register callbacks for bot events - call this after components are initialized."""
        try:
            # Import here to avoid circular imports
            from src.monitoring.wallet_tracker import wallet_tracker
            from src.trading.strategy_engine import strategy_engine
            
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
        activity = {
            "timestamp": time.time(),
            "action": "Wallet Buy",
            "wallet": wallet_address,
            "token": token_address,
            "amount": amount_sol
        }
        self.tracked_wallet_activity.append(activity)
        self.stats["buy_signals"] += 1
        self.stats["transactions_monitored"] += 1
        
        if self.live:
            self._update_ui()
    
    def _on_bot_trade(self, trade_type: str, token_address: str, amount: float, price: float):
        """Callback for when the bot executes a trade."""
        trade = Trade(trade_type, token_address, amount, price, time.time())
        self.trades.append(trade)
        
        action = {
            "timestamp": time.time(),
            "action": f"Bot {trade_type}",
            "details": f"{token_address[:8]}... {amount:.3f} @ {price:.6f}"
        }
        self.bot_actions.append(action)
        
        # Update statistics
        self.stats["total_trades"] += 1
        self.stats["total_volume"] += amount * price
        
        if trade_type == "BUY":
            # Update holdings
            if token_address not in self.token_holdings:
                self.token_holdings[token_address] = {
                    "amount": 0,
                    "avg_price": 0,
                    "current_price": price
                }
            
            holding = self.token_holdings[token_address]
            total_amount = holding["amount"] + amount
            total_cost = (holding["amount"] * holding["avg_price"]) + (amount * price)
            holding["amount"] = total_amount
            holding["avg_price"] = total_cost / total_amount if total_amount > 0 else 0
            
        elif trade_type == "SELL":
            if token_address in self.token_holdings:
                holding = self.token_holdings[token_address]
                profit = (price - holding["avg_price"]) * amount
                trade.pnl = profit
                
                # Update statistics
                self.stats["realized_pnl"] += profit
                
                if profit > 0:
                    self.stats["successful_trades"] += 1
                    self.stats["best_trade"] = max(self.stats["best_trade"], profit)
                else:
                    self.stats["failed_trades"] += 1
                    self.stats["worst_trade"] = min(self.stats["worst_trade"], profit)
                
                # Update holdings
                holding["amount"] -= amount
                if holding["amount"] <= 0:
                    del self.token_holdings[token_address]
        
        # Update win rate
        if self.stats["total_trades"] > 0:
            self.stats["win_rate"] = (self.stats["successful_trades"] / self.stats["total_trades"]) * 100
        
        if self.live:
            self._update_ui()
    
    async def start(self):
        """Start the CLI UI."""
        self.running = True
        self._update_header()
        
        # Register callbacks now that components are initialized
        self.register_callbacks()
        
        # Start balance update task
        asyncio.create_task(self._update_balance())
        
        # Start live display
        logger.info("Starting UI live display")
        with Live(self.layout, refresh_per_second=2, screen=True) as live:
            self.live = live
            logger.info("UI live display started")
            
            while self.running:
                await asyncio.sleep(0.5)  # Keep the UI running
    
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