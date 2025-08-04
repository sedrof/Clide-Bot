#!/usr/bin/env python3
"""
Monitor blockchain transactions for your wallet in real-time.
Shows all incoming/outgoing transactions with token details.
"""
import asyncio
import sys
import os
from datetime import datetime
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.signature import Signature
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
import json

console = Console()


class BlockchainMonitor:
    """Monitor wallet transactions on Solana blockchain."""
    
    def __init__(self, wallet_address: str):
        self.wallet_address = wallet_address
        self.pubkey = Pubkey.from_string(wallet_address)
        self.transactions = deque(maxlen=50)
        self.last_signature = None
        self.client = None
        
    async def connect(self):
        """Connect to Solana RPC."""
        self.client = AsyncClient("https://api.mainnet-beta.solana.com")
        console.print(f"[green]✓ Connected to Solana mainnet[/green]")
        console.print(f"[cyan]Monitoring wallet: {self.wallet_address}[/cyan]\n")
        
    async def get_recent_transactions(self):
        """Get recent transactions for the wallet."""
        try:
            # Get transaction signatures
            response = await self.client.get_signatures_for_address(
                self.pubkey,
                limit=10
            )
            
            if not response.value:
                return
                
            for sig_info in response.value:
                sig_str = str(sig_info.signature)
                
                # Skip if we've already processed this
                if self.last_signature and sig_str == self.last_signature:
                    break
                    
                # Get transaction details
                try:
                    tx_response = await self.client.get_transaction(
                        Signature.from_string(sig_str),
                        max_supported_transaction_version=0
                    )
                    
                    if tx_response.value:
                        tx = tx_response.value
                        
                        # Parse transaction
                        tx_data = {
                            "signature": sig_str[:16] + "...",
                            "time": datetime.fromtimestamp(sig_info.block_time).strftime("%H:%M:%S"),
                            "status": "✅" if not sig_info.err else "❌",
                            "type": "Unknown",
                            "amount": 0,
                            "token": "SOL",
                            "fee": tx.meta.fee / 1_000_000_000 if tx.meta else 0
                        }
                        
                        # Analyze pre/post balances to determine transaction type
                        if tx.meta:
                            pre_balance = tx.meta.pre_balances[0] / 1_000_000_000
                            post_balance = tx.meta.post_balances[0] / 1_000_000_000
                            diff = post_balance - pre_balance
                            
                            if diff > 0:
                                tx_data["type"] = "Receive"
                                tx_data["amount"] = diff
                            elif diff < -0.0001:  # Account for fees
                                tx_data["type"] = "Send"
                                tx_data["amount"] = abs(diff)
                            else:
                                tx_data["type"] = "Contract"
                                
                        self.transactions.appendleft(tx_data)
                        
                except Exception as e:
                    console.print(f"[red]Error parsing transaction: {e}[/red]")
                    
            # Update last signature
            if response.value:
                self.last_signature = str(response.value[0].signature)
                
        except Exception as e:
            console.print(f"[red]Error fetching transactions: {e}[/red]")
            
    def create_display(self) -> Table:
        """Create transaction display table."""
        table = Table(title="🔍 Recent Blockchain Transactions", expand=True)
        table.add_column("Time", style="dim", width=10)
        table.add_column("Status", width=6)
        table.add_column("Type", width=10)
        table.add_column("Amount", justify="right", width=15)
        table.add_column("Token", width=8)
        table.add_column("Fee", justify="right", width=10)
        table.add_column("Signature", style="dim")
        
        for tx in list(self.transactions)[:20]:
            type_color = {
                "Send": "red",
                "Receive": "green",
                "Contract": "yellow",
                "Unknown": "dim"
            }.get(tx["type"], "white")
            
            table.add_row(
                tx["time"],
                tx["status"],
                f"[{type_color}]{tx['type']}[/{type_color}]",
                f"{tx['amount']:.6f}" if tx['amount'] > 0 else "-",
                tx["token"],
                f"{tx['fee']:.6f}",
                tx["signature"]
            )
            
        return table
        
    async def monitor(self):
        """Run the monitoring loop."""
        await self.connect()
        
        with Live(console=console, refresh_per_second=1) as live:
            while True:
                try:
                    await self.get_recent_transactions()
                    
                    # Create display
                    display = Panel(
                        self.create_display(),
                        border_style="cyan",
                        title=f"[bold]Wallet: {self.wallet_address}[/bold]",
                        subtitle=f"[dim]Updated: {datetime.now().strftime('%H:%M:%S')}[/dim]"
                    )
                    
                    live.update(display)
                    
                    # Wait before next update
                    await asyncio.sleep(5)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    console.print(f"[red]Monitor error: {e}[/red]")
                    await asyncio.sleep(5)
                    
        await self.client.close()


async def main():
    """Main entry point."""
    # Load wallet address from config
    try:
        with open("config/wallet.json", 'r') as f:
            wallet_data = json.load(f)
            wallet_address = wallet_data["public_key"]
    except Exception as e:
        console.print(f"[red]Error loading wallet config: {e}[/red]")
        return
        
    console.print("[bold cyan]🔍 Blockchain Transaction Monitor[/bold cyan]")
    console.print("[dim]Monitoring all transactions for your wallet[/dim]\n")
    
    monitor = BlockchainMonitor(wallet_address)
    await monitor.monitor()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitor stopped[/yellow]")