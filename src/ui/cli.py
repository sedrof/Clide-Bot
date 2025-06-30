"""
Modern CLI UI for the Solana pump.fun sniping bot.
Fixed version with proper layout initialization.
"""
# File Location: src/ui/cli.py

import asyncio
from typing import List, Dict, Any, Optional, Tuple
import time
from datetime import datetime, timedelta
from collections import deque
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.align import Align
from rich.columns import Columns
import json

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.core.wallet_manager import wallet_manager
from src.core.connection_manager import connection_manager

logger = get_logger("cli_ui")
console = Console()


class Trade:
    """Represents a single trade for tracking."""
    def __init__(self, trade_type: str, token: str, amount: float, price: float, timestamp: float):
        self.type = trade_type
        self.token = token
        self.amount = amount
        self.price = price
        self.timestamp = timestamp
        self.pnl = 0.0
        self.status = "pending"  # pending, profit, loss
        

class ModernBotCLI:
    """Modern CLI UI for the Solana pump.fun sniping bot with comprehensive statistics."""
    
    def __init__(self):
        self.layout = Layout()
        self.live = None
        self.running = False
        
        # Data tracking
        self.wallet_balance = 0.0
        self.initial_balance = 0.0
        self.tracked_wallet_activity = deque(maxlen=20)
        self.bot_actions = deque(maxlen=20)
        self.trades: List[Trade] = []
        self.token_holdings: Dict[str, Dict] = {}  # token -> {amount, avg_price, current_price}
        
        # Statistics
        self.stats = {
            "start_time": time.time(),
            "total_trades": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "total_volume": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "win_rate": 0.0,
            "avg_profit": 0.0,
            "avg_loss": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "transactions_monitored": 0,
            "buy_signals": 0,
            "sell_signals": 0,
            "tokens_held": 0,
            "connection_status": "🔴 Disconnected",
            "websocket_status": "🔴 Disconnected",
            "last_update": time.time()
        }
        
        # Performance tracking
        self.performance_history = deque(maxlen=100)  # Track PnL over time
        
        # Initialize layout structure
        self._setup_layout()
        self._register_callbacks()
    
    def _setup_layout(self):
        """Setup the modern dashboard layout."""
        # Main layout structure
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=3)
        )
        
        # Header
        self._update_header()
        
        # Create body structure
        self.layout["body"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="center", ratio=3),
            Layout(name="right", ratio=2)
        )
        
        # Create left column structure
        self.layout["body"]["left"].split_column(
            Layout(name="stats", ratio=2),
            Layout(name="performance", ratio=1)
        )
        
        # Create center column structure
        self.layout["body"]["center"].split_column(
            Layout(name="activity", ratio=1),
            Layout(name="trades", ratio=1)
        )
        
        # Create right column structure
        self.layout["body"]["right"].split_column(
            Layout(name="holdings", ratio=1),
            Layout(name="tracking", ratio=1)
        )
        
        # Footer
        self._update_footer()
        
        # Initial content for all panels
        self._initialize_panels()
    
    def _initialize_panels(self):
        """Initialize all panels with default content."""
        # Initialize all panels to prevent errors
        self.layout["body"]["left"]["stats"].update(self._render_stats())
        self.layout["body"]["left"]["performance"].update(self._render_performance())
        self.layout["body"]["center"]["activity"].update(self._render_activity())
        self.layout["body"]["center"]["trades"].update(self._render_trades())
        self.layout["body"]["right"]["holdings"].update(self._render_holdings())
        self.layout["body"]["right"]["tracking"].update(self._render_tracking())
    
    def _update_header(self):
        """Update header with title and status."""
        title = Text("🚀 Solana Pump.fun Sniper Bot Dashboard", style="bold cyan", justify="center")
        subtitle = Text(f"v2.0 | Tracking: {len(self.tracked_wallet_activity)} wallets", style="dim", justify="center")
        
        header_content = Align.center(title + "\n" + subtitle)
        self.layout["header"].update(Panel(header_content, border_style="cyan", box=box.DOUBLE))
    
    def _update_footer(self):
        """Update footer with connection status and controls."""
        uptime = timedelta(seconds=int(time.time() - self.stats["start_time"]))
        status_text = f"⏱️ Uptime: {uptime} | {self.stats['connection_status']} RPC | {self.stats['websocket_status']} WS | 📊 Last Update: {datetime.now().strftime('%H:%M:%S')}"
        
        footer = Panel(
            Text(status_text, justify="center", style="dim"),
            border_style="green" if self.running else "red",
            box=box.ROUNDED
        )
        self.layout["footer"].update(footer)
    
    def _render_stats(self) -> Panel:
        """Render main statistics panel."""
        stats_table = Table(show_header=False, box=None, padding=(0, 1))
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="white", justify="right")
        
        # Calculate current PnL
        total_pnl = self.stats["realized_pnl"] + self.stats["unrealized_pnl"]
        pnl_color = "green" if total_pnl >= 0 else "red"
        
        # Calculate ROI
        roi = 0.0
        if self.initial_balance > 0:
            roi = ((self.wallet_balance - self.initial_balance) / self.initial_balance) * 100
        roi_color = "green" if roi >= 0 else "red"
        
        stats_data = [
            ("💰 Balance", f"{self.wallet_balance:.6f} SOL"),
            ("📈 Total P&L", f"[{pnl_color}]{total_pnl:+.6f} SOL[/{pnl_color}]"),
            ("   ├ Realized", f"{self.stats['realized_pnl']:+.6f} SOL"),
            ("   └ Unrealized", f"{self.stats['unrealized_pnl']:+.6f} SOL"),
            ("📊 ROI", f"[{roi_color}]{roi:+.2f}%[/{roi_color}]"),
            ("", ""),  # Spacer
            ("🎯 Win Rate", f"{self.stats['win_rate']:.1f}%"),
            ("📉 Trades", f"{self.stats['successful_trades']}/{self.stats['total_trades']}"),
            ("💸 Volume", f"{self.stats['total_volume']:.2f} SOL"),
            ("🏆 Best Trade", f"+{self.stats['best_trade']:.4f} SOL"),
            ("💀 Worst Trade", f"{self.stats['worst_trade']:.4f} SOL"),
            ("", ""),  # Spacer
            ("🔍 Monitored", f"{self.stats['transactions_monitored']}"),
            ("🟢 Buy Signals", f"{self.stats['buy_signals']}"),
            ("🔴 Sell Signals", f"{self.stats['sell_signals']}"),
        ]
        
        for metric, value in stats_data:
            if metric:  # Skip empty rows
                stats_table.add_row(metric, value)
            else:
                stats_table.add_row("", "")
        
        return Panel(
            stats_table,
            title="📊 Statistics",
            border_style="blue",
            box=box.ROUNDED
        )
    
    def _render_performance(self) -> Panel:
        """Render performance chart (simplified ASCII)."""
        if not self.performance_history:
            content = Text("No performance data yet...", style="dim", justify="center")
        else:
            # Simple ASCII chart
            max_val = max(self.performance_history) if self.performance_history else 1
            min_val = min(self.performance_history) if self.performance_history else 0
            range_val = max_val - min_val or 1
            
            chart_height = 5
            chart_width = min(len(self.performance_history), 40)
            
            chart_lines = []
            for i in range(chart_height, -1, -1):
                line = ""
                threshold = min_val + (range_val * i / chart_height)
                
                for j in range(chart_width):
                    idx = -(chart_width - j)
                    if idx < -len(self.performance_history):
                        line += " "
                    else:
                        val = self.performance_history[idx]
                        if val >= threshold:
                            line += "█"
                        else:
                            line += " "
                
                if i == chart_height:
                    chart_lines.append(f"{max_val:+.3f} │{line}")
                elif i == 0:
                    chart_lines.append(f"{min_val:+.3f} │{line}")
                else:
                    chart_lines.append(f"      │{line}")
            
            chart_lines.append(f"      └{'─' * chart_width}")
            chart_lines.append(f"       P&L History (Last {chart_width} updates)")
            
            content = Text("\n".join(chart_lines), style="cyan")
        
        return Panel(
            content,
            title="📈 Performance",
            border_style="green",
            box=box.ROUNDED
        )
    
    def _render_activity(self) -> Panel:
        """Render recent activity feed."""
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
        trades_table = Table(show_header=True, header_style="bold magenta", box=None)
        trades_table.add_column("Time", style="dim", width=8)
        trades_table.add_column("Type", width=6)
        trades_table.add_column("Token", width=10)
        trades_table.add_column("Amount", justify="right")
        trades_table.add_column("Price", justify="right")
        trades_table.add_column("P&L", justify="right")
        
        # Show most recent trades
        for trade in self.trades[-8:]:  # Last 8 trades
            time_str = datetime.fromtimestamp(trade.timestamp).strftime("%H:%M:%S")
            type_style = "green" if trade.type == "BUY" else "red"
            
            pnl_str = ""
            if trade.pnl != 0:
                pnl_color = "green" if trade.pnl > 0 else "red"
                pnl_str = f"[{pnl_color}]{trade.pnl:+.4f}[/{pnl_color}]"
            
            trades_table.add_row(
                time_str,
                f"[{type_style}]{trade.type}[/{type_style}]",
                f"{trade.token[:8]}...",
                f"{trade.amount:.3f}",
                f"{trade.price:.6f}",
                pnl_str
            )
        
        if not self.trades:
            trades_table.add_row("--:--:--", "---", "No trades yet", "---", "---", "---")
        
        return Panel(
            trades_table,
            title="💹 Recent Trades",
            border_style="magenta",
            box=box.ROUNDED
        )
    
    def _render_holdings(self) -> Panel:
        """Render current token holdings."""
        holdings_table = Table(show_header=True, header_style="bold green", box=None)
        holdings_table.add_column("Token", width=12)
        holdings_table.add_column("Amount", justify="right")
        holdings_table.add_column("Avg Price", justify="right")
        holdings_table.add_column("Current", justify="right")
        holdings_table.add_column("P&L %", justify="right")
        
        total_value = 0.0
        for token, data in self.token_holdings.items():
            amount = data.get("amount", 0)
            avg_price = data.get("avg_price", 0)
            current_price = data.get("current_price", avg_price)
            
            pnl_pct = 0.0
            if avg_price > 0:
                pnl_pct = ((current_price - avg_price) / avg_price) * 100
            
            pnl_color = "green" if pnl_pct >= 0 else "red"
            
            holdings_table.add_row(
                f"{token[:10]}...",
                f"{amount:.3f}",
                f"{avg_price:.6f}",
                f"{current_price:.6f}",
                f"[{pnl_color}]{pnl_pct:+.1f}%[/{pnl_color}]"
            )
            
            total_value += amount * current_price
        
        if not self.token_holdings:
            holdings_table.add_row("No tokens held", "---", "---", "---", "---")
        
        # Add total value row
        if self.token_holdings:
            holdings_table.add_row("", "", "", "", "")
            holdings_table.add_row(
                "[bold]TOTAL VALUE[/bold]",
                "",
                "",
                f"[bold]{total_value:.4f} SOL[/bold]",
                ""
            )
        
        self.stats["tokens_held"] = len(self.token_holdings)
        
        return Panel(
            holdings_table,
            title="💼 Token Holdings",
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
            # Update all panels
            self.layout["body"]["left"]["stats"].update(self._render_stats())
            self.layout["body"]["left"]["performance"].update(self._render_performance())
            self.layout["body"]["center"]["activity"].update(self._render_activity())
            self.layout["body"]["center"]["trades"].update(self._render_trades())
            self.layout["body"]["right"]["holdings"].update(self._render_holdings())
            self.layout["body"]["right"]["tracking"].update(self._render_tracking())
            
            # Update footer
            self._update_footer()
            
        except Exception as e:
            logger.error(f"Error updating UI: {str(e)}", exc_info=True)
    
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
                    if wallet_tracker and wallet_tracker.websocket and not wallet_tracker.websocket.closed:
                        self.stats["websocket_status"] = "🟢 Connected"
                    else:
                        self.stats["websocket_status"] = "🔴 Disconnected"
                except:
                    pass
                
                self.stats["last_update"] = time.time()
                
                # Only update UI if live display is active
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
    
    def _register_callbacks(self):
        """Register callbacks for bot events."""
        try:
            # Import here to avoid circular imports
            from src.monitoring.wallet_tracker import wallet_tracker
            from src.trading.strategy_engine import strategy_engine
            
            if wallet_tracker:
                wallet_tracker.register_buy_callback(self._on_wallet_buy)
                logger.info("Registered wallet buy callback with UI")
                
            # Strategy engine callbacks would go here
            # if strategy_engine:
            #     strategy_engine.register_trade_callback(self._on_bot_trade)
                
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
        
        # Start background tasks
        asyncio.create_task(self._update_balance())
        
        # Start live display
        logger.info("Starting modern UI live display")
        
        try:
            with Live(self.layout, refresh_per_second=2, screen=True) as live:
                self.live = live
                logger.info("UI live display started")
                
                # Initial UI update
                self._update_ui()
                
                while self.running:
                    await asyncio.sleep(0.5)  # Keep the UI running
        except Exception as e:
            logger.error(f"Error in UI display: {str(e)}", exc_info=True)
            self.running = False
    
    def stop(self):
        """Stop the CLI UI."""
        self.running = False
        if self.live:
            self.live.stop()
        logger.info("UI stopped")


# Global CLI UI instance
bot_cli = None

def initialize_bot_cli():
    """Initialize the global bot CLI instance."""
    global bot_cli
    bot_cli = ModernBotCLI()
    return bot_cli