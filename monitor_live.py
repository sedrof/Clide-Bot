#!/usr/bin/env python3
"""
Live monitoring dashboard for the Solana pump.fun bot.
Shows real-time trades, P&L, and bot activity.
"""
import asyncio
import sys
import os
import time
from datetime import datetime
from collections import deque
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich import box
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

console = Console()


class LiveMonitor:
    """Live monitoring dashboard for the bot."""
    
    def __init__(self):
        self.layout = Layout()
        self.trades = deque(maxlen=20)
        self.log_entries = deque(maxlen=30)
        self.stats = {
            "balance": 0.0,
            "initial_balance": 0.0,
            "total_trades": 0,
            "profitable_trades": 0,
            "total_pnl": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "active_positions": 0,
            "last_update": datetime.now()
        }
        self.positions = {}
        self.setup_layout()
        
    def setup_layout(self):
        """Setup the dashboard layout."""
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="stats", size=6),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        
        self.layout["main"].split_row(
            Layout(name="trades", ratio=1),
            Layout(name="positions", ratio=1)
        )
        
    def update_header(self):
        """Update header with title and time."""
        header_text = Text()
        header_text.append("📊 SOLANA BOT LIVE MONITOR", style="bold cyan")
        header_text.append(f"\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim")
        
        self.layout["header"].update(
            Panel(Align.center(header_text), border_style="cyan", box=box.DOUBLE)
        )
        
    def update_stats(self):
        """Update statistics panel."""
        stats_table = Table(box=box.SIMPLE, show_header=False, expand=True)
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", justify="right", style="yellow")
        
        # Calculate P&L
        pnl = self.stats["balance"] - self.stats["initial_balance"]
        pnl_pct = (pnl / self.stats["initial_balance"] * 100) if self.stats["initial_balance"] > 0 else 0
        pnl_color = "green" if pnl >= 0 else "red"
        
        # Win rate
        win_rate = 0
        if self.stats["total_trades"] > 0:
            win_rate = (self.stats["profitable_trades"] / self.stats["total_trades"]) * 100
        
        stats_table.add_row("💰 Current Balance", f"{self.stats['balance']:.6f} SOL")
        stats_table.add_row("📈 Total P&L", f"[{pnl_color}]{pnl:+.6f} SOL ({pnl_pct:+.2f}%)[/{pnl_color}]")
        stats_table.add_row("🎯 Win Rate", f"{win_rate:.1f}%")
        stats_table.add_row("📊 Total Trades", str(self.stats['total_trades']))
        stats_table.add_row("💼 Active Positions", str(self.stats['active_positions']))
        stats_table.add_row("🏆 Best Trade", f"{self.stats['best_trade']:+.2f}%")
        stats_table.add_row("📉 Worst Trade", f"{self.stats['worst_trade']:+.2f}%")
        
        self.layout["stats"].update(
            Panel(stats_table, title="📊 Statistics", border_style="green")
        )
        
    def update_trades(self):
        """Update recent trades panel."""
        trades_table = Table(box=box.SIMPLE, expand=True)
        trades_table.add_column("Time", style="dim", width=12)
        trades_table.add_column("Type", width=6)
        trades_table.add_column("Token", overflow="fold")
        trades_table.add_column("Amount", justify="right")
        trades_table.add_column("P&L", justify="right")
        
        for trade in list(self.trades):
            trade_type = trade.get("type", "")
            type_color = "green" if trade_type == "BUY" else "red"
            
            pnl = trade.get("pnl", 0)
            pnl_color = "green" if pnl >= 0 else "red"
            
            trades_table.add_row(
                trade.get("time", ""),
                f"[{type_color}]{trade_type}[/{type_color}]",
                trade.get("token", "")[:16] + "...",
                f"{trade.get('amount', 0):.4f} SOL",
                f"[{pnl_color}]{pnl:+.2f}%[/{pnl_color}]" if trade_type == "SELL" else "-"
            )
            
        self.layout["trades"].update(
            Panel(trades_table, title="📈 Recent Trades", border_style="yellow")
        )
        
    def update_positions(self):
        """Update open positions panel."""
        positions_table = Table(box=box.SIMPLE, expand=True)
        positions_table.add_column("Token", overflow="fold")
        positions_table.add_column("Entry", justify="right")
        positions_table.add_column("Current", justify="right")
        positions_table.add_column("P&L", justify="right")
        positions_table.add_column("Age", justify="right")
        
        for token, pos in self.positions.items():
            current_price = pos.get("current_price", pos.get("entry_price", 0))
            entry_price = pos.get("entry_price", 0)
            
            pnl = 0
            if entry_price > 0:
                pnl = ((current_price - entry_price) / entry_price) * 100
                
            pnl_color = "green" if pnl >= 0 else "red"
            
            # Calculate age
            entry_time = pos.get("entry_time", datetime.now())
            age = datetime.now() - entry_time
            age_str = f"{int(age.total_seconds() / 60)}m"
            
            positions_table.add_row(
                token[:12] + "...",
                f"{entry_price:.6f}",
                f"{current_price:.6f}",
                f"[{pnl_color}]{pnl:+.2f}%[/{pnl_color}]",
                age_str
            )
            
        self.layout["positions"].update(
            Panel(positions_table, title="💼 Open Positions", border_style="magenta")
        )
        
    def update_footer(self):
        """Update footer with instructions."""
        footer_text = Text()
        footer_text.append("Press Ctrl+C to exit monitor", style="dim yellow")
        footer_text.append(" | ", style="dim")
        footer_text.append("Updates every 2 seconds", style="dim cyan")
        
        self.layout["footer"].update(
            Panel(Align.center(footer_text), border_style="dim")
        )
        
    async def parse_log_file(self):
        """Parse log file for trades and updates."""
        log_path = "logs/pump_bot.log"
        if not os.path.exists(log_path):
            return
            
        try:
            # Read last 100 lines
            with open(log_path, 'r') as f:
                lines = f.readlines()[-100:]
                
            for line in lines:
                # Parse buy/sell events
                if "BUY executed" in line or "Buy transaction" in line:
                    parts = line.split()
                    timestamp = f"{parts[0]} {parts[1]}"
                    
                    # Extract token and amount
                    if "for token" in line:
                        token_idx = line.find("for token") + 10
                        token = line[token_idx:token_idx+44]
                        
                        amount_idx = line.find("Amount:") + 8 if "Amount:" in line else -1
                        amount = 0.001  # Default
                        if amount_idx > 0:
                            try:
                                amount = float(line[amount_idx:].split()[0])
                            except:
                                pass
                                
                        self.trades.append({
                            "time": timestamp.split()[1][:8],
                            "type": "BUY",
                            "token": token,
                            "amount": amount,
                            "pnl": 0
                        })
                        
                        self.positions[token] = {
                            "entry_price": 1.0,
                            "entry_time": datetime.now(),
                            "amount": amount
                        }
                        
                        self.stats["total_trades"] += 1
                        
                elif "SELL executed" in line or "Sell transaction" in line:
                    parts = line.split()
                    timestamp = f"{parts[0]} {parts[1]}"
                    
                    # Extract token and profit
                    if "Profit:" in line:
                        profit_idx = line.find("Profit:") + 8
                        try:
                            profit = float(line[profit_idx:].split('%')[0])
                            
                            self.trades.append({
                                "time": timestamp.split()[1][:8],
                                "type": "SELL",
                                "token": "Unknown",
                                "amount": 0.001,
                                "pnl": profit
                            })
                            
                            if profit > 0:
                                self.stats["profitable_trades"] += 1
                            if profit > self.stats["best_trade"]:
                                self.stats["best_trade"] = profit
                            if profit < self.stats["worst_trade"]:
                                self.stats["worst_trade"] = profit
                                
                        except:
                            pass
                            
        except Exception as e:
            console.print(f"Error parsing logs: {e}", style="red")
            
    async def update_wallet_balance(self):
        """Update wallet balance from config."""
        try:
            # Load wallet config
            with open("config/wallet.json", 'r') as f:
                wallet_data = json.load(f)
                
            # Connect to RPC
            client = AsyncClient("https://api.mainnet-beta.solana.com")
            pubkey = Pubkey.from_string(wallet_data["public_key"])
            
            # Get balance
            response = await client.get_balance(pubkey)
            self.stats["balance"] = response.value / 1_000_000_000
            
            # Set initial balance if not set
            if self.stats["initial_balance"] == 0:
                self.stats["initial_balance"] = self.stats["balance"]
                
            await client.close()
            
        except Exception as e:
            console.print(f"Error getting balance: {e}", style="red")
            
    async def run(self):
        """Run the live monitor."""
        with Live(self.layout, refresh_per_second=2, screen=True) as live:
            while True:
                try:
                    # Update all panels
                    self.update_header()
                    self.update_stats()
                    self.update_trades()
                    self.update_positions()
                    self.update_footer()
                    
                    # Update data
                    await self.parse_log_file()
                    await self.update_wallet_balance()
                    
                    self.stats["active_positions"] = len(self.positions)
                    self.stats["last_update"] = datetime.now()
                    
                    await asyncio.sleep(2)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    console.print(f"Error: {e}", style="red")
                    await asyncio.sleep(2)


async def main():
    """Main entry point."""
    console.print("[bold cyan]Starting Live Monitor...[/bold cyan]")
    console.print("[dim]Reading logs and wallet data...[/dim]\n")
    
    monitor = LiveMonitor()
    await monitor.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitor stopped by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")