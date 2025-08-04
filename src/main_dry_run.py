"""
Dry-run version of the main bot for safe testing.
This version simulates trades without executing real transactions.
"""
import asyncio
import signal
import sys
import os
from typing import Optional, Dict, Any
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging FIRST
from src.utils.logger import setup_logging

# Initialize logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)
setup_logging(
    level="INFO",
    file_path=os.path.join(log_dir, "pump_bot_dry_run.log"),
    max_file_size_mb=10,
    backup_count=5,
    console_output=True
)

from src.utils.config import config_manager
from src.utils.logger import get_logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live

logger = get_logger("main.dry_run")
console = Console()

# Global shutdown flag
shutdown_event = asyncio.Event()

# Simulated portfolio
simulated_portfolio = {
    "balance_sol": 1.0,  # Start with 1 SOL
    "positions": {},
    "trade_history": [],
    "total_trades": 0,
    "profitable_trades": 0,
    "total_pnl": 0.0
}


class DryRunTransactionBuilder:
    """Mock transaction builder for dry run mode."""
    
    async def build_buy_transaction(self, token_address: str, amount_sol: float) -> Dict[str, Any]:
        """Simulate building a buy transaction."""
        logger.info(f"[DRY RUN] Building buy transaction: {amount_sol} SOL for token {token_address}")
        return {
            "type": "buy",
            "token": token_address,
            "amount_sol": amount_sol,
            "simulated": True,
            "timestamp": datetime.now()
        }
    
    async def build_sell_transaction(self, token_address: str, amount: float) -> Dict[str, Any]:
        """Simulate building a sell transaction."""
        logger.info(f"[DRY RUN] Building sell transaction for token {token_address}")
        return {
            "type": "sell",
            "token": token_address,
            "amount": amount,
            "simulated": True,
            "timestamp": datetime.now()
        }


class DryRunWalletManager:
    """Mock wallet manager for dry run mode."""
    
    def __init__(self):
        self.balance = simulated_portfolio["balance_sol"]
    
    async def initialize(self):
        """Initialize mock wallet."""
        logger.info("[DRY RUN] Wallet manager initialized with simulated balance")
    
    async def get_balance(self) -> float:
        """Get simulated balance."""
        return simulated_portfolio["balance_sol"]
    
    def get_public_key(self) -> str:
        """Get mock public key."""
        return "DRY_RUN_WALLET_" + "A" * 32
    
    async def sign_and_send_transaction(self, transaction: Dict[str, Any]) -> str:
        """Simulate sending a transaction."""
        if transaction["type"] == "buy":
            # Simulate buy
            amount = transaction["amount_sol"]
            if simulated_portfolio["balance_sol"] >= amount:
                simulated_portfolio["balance_sol"] -= amount
                simulated_portfolio["positions"][transaction["token"]] = {
                    "amount_sol": amount,
                    "entry_price": 1.0,  # Mock price
                    "entry_time": datetime.now(),
                    "token_amount": amount * 1000000  # Mock token amount
                }
                simulated_portfolio["total_trades"] += 1
                logger.info(f"[DRY RUN] ✅ Buy executed: {amount} SOL, New balance: {simulated_portfolio['balance_sol']} SOL")
                return f"DRY_RUN_TX_{transaction['token'][:8]}"
            else:
                raise Exception("Insufficient balance for dry run trade")
        
        elif transaction["type"] == "sell":
            # Simulate sell
            token = transaction["token"]
            if token in simulated_portfolio["positions"]:
                position = simulated_portfolio["positions"][token]
                # Simulate 20% profit for testing
                sell_value = position["amount_sol"] * 1.2
                simulated_portfolio["balance_sol"] += sell_value
                
                profit = sell_value - position["amount_sol"]
                simulated_portfolio["total_pnl"] += profit
                if profit > 0:
                    simulated_portfolio["profitable_trades"] += 1
                
                # Record trade
                simulated_portfolio["trade_history"].append({
                    "token": token,
                    "buy_amount": position["amount_sol"],
                    "sell_amount": sell_value,
                    "profit": profit,
                    "profit_percent": (profit / position["amount_sol"]) * 100,
                    "hold_time": (datetime.now() - position["entry_time"]).total_seconds()
                })
                
                del simulated_portfolio["positions"][token]
                logger.info(f"[DRY RUN] ✅ Sell executed: Profit {profit:.4f} SOL ({profit/position['amount_sol']*100:.1f}%)")
                return f"DRY_RUN_SELL_TX_{token[:8]}"
        
        return "DRY_RUN_TX_UNKNOWN"


def print_portfolio_status():
    """Print current portfolio status."""
    table = Table(title="[DRY RUN] Portfolio Status", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Balance", f"{simulated_portfolio['balance_sol']:.4f} SOL")
    table.add_row("Open Positions", str(len(simulated_portfolio['positions'])))
    table.add_row("Total Trades", str(simulated_portfolio['total_trades']))
    table.add_row("Profitable Trades", str(simulated_portfolio['profitable_trades']))
    table.add_row("Total P&L", f"{simulated_portfolio['total_pnl']:.4f} SOL")
    
    if simulated_portfolio['total_trades'] > 0:
        win_rate = (simulated_portfolio['profitable_trades'] / simulated_portfolio['total_trades']) * 100
        table.add_row("Win Rate", f"{win_rate:.1f}%")
    
    console.print(table)
    
    # Show open positions
    if simulated_portfolio['positions']:
        pos_table = Table(title="Open Positions", show_header=True)
        pos_table.add_column("Token", style="yellow")
        pos_table.add_column("Amount", style="white")
        pos_table.add_column("Hold Time", style="white")
        
        for token, pos in simulated_portfolio['positions'].items():
            hold_time = (datetime.now() - pos['entry_time']).total_seconds()
            pos_table.add_row(
                token[:16] + "...",
                f"{pos['amount_sol']:.4f} SOL",
                f"{hold_time:.0f}s"
            )
        
        console.print(pos_table)


async def start_bot_dry_run():
    """Start the bot in dry-run mode."""
    try:
        console.print(Panel.fit("🧪 Starting Solana Pump.fun Bot in DRY RUN Mode", style="bold yellow"))
        console.print("[bold yellow]⚠️  No real transactions will be executed![/bold yellow]")
        console.print()
        
        # Load configurations
        config_manager.load_all()
        logger.info("[DRY RUN] Configurations loaded successfully")
        
        # Override with dry-run components
        dry_wallet = DryRunWalletManager()
        dry_tx_builder = DryRunTransactionBuilder()
        
        # Import real components that we'll use
        from src.core.connection_manager import connection_manager
        from src.monitoring.pump_monitor import initialize_pump_monitor
        from src.monitoring.price_tracker import initialize_price_tracker
        from src.monitoring.event_processor import initialize_event_processor
        
        # Initialize connection (real, for monitoring)
        await connection_manager.initialize()
        logger.info("[DRY RUN] ✓ Connection manager initialized")
        
        # Initialize wallet
        await dry_wallet.initialize()
        balance = await dry_wallet.get_balance()
        logger.info(f"[DRY RUN] ✓ Wallet initialized with simulated balance: {balance} SOL")
        
        # Initialize monitors (real, for monitoring)
        pump_monitor = initialize_pump_monitor()
        logger.info("[DRY RUN] ✓ Pump monitor initialized")
        
        price_tracker = initialize_price_tracker()
        logger.info("[DRY RUN] ✓ Price tracker initialized")
        
        event_processor = initialize_event_processor()
        logger.info("[DRY RUN] ✓ Event processor initialized")
        
        # Start monitoring
        logger.info("[DRY RUN] Starting monitoring components...")
        
        await pump_monitor.start()
        logger.info("[DRY RUN] ✓ Pump monitor started")
        
        await price_tracker.start()
        logger.info("[DRY RUN] ✓ Price tracker started")
        
        console.print(Panel.fit("✅ Dry Run Mode Active - Monitoring for opportunities...", style="bold green"))
        console.print()
        
        # Periodic status updates
        async def status_updater():
            while not shutdown_event.is_set():
                print_portfolio_status()
                await asyncio.sleep(30)  # Update every 30 seconds
        
        # Run status updater
        status_task = asyncio.create_task(status_updater())
        
        # Wait for shutdown
        await shutdown_event.wait()
        status_task.cancel()
        
    except Exception as e:
        logger.error(f"[DRY RUN] Error: {e}", exc_info=True)
        raise


async def stop_bot_dry_run():
    """Stop the dry-run bot."""
    logger.info("[DRY RUN] Stopping bot...")
    
    # Print final statistics
    console.print()
    console.print(Panel.fit("📊 Final Dry Run Statistics", style="bold blue"))
    print_portfolio_status()
    
    # Print trade history
    if simulated_portfolio['trade_history']:
        trade_table = Table(title="Trade History", show_header=True)
        trade_table.add_column("Token", style="yellow")
        trade_table.add_column("Buy", style="white")
        trade_table.add_column("Sell", style="white")
        trade_table.add_column("Profit", style="green")
        trade_table.add_column("Hold Time", style="white")
        
        for trade in simulated_portfolio['trade_history'][-10:]:  # Last 10 trades
            trade_table.add_row(
                trade['token'][:12] + "...",
                f"{trade['buy_amount']:.4f}",
                f"{trade['sell_amount']:.4f}",
                f"{trade['profit']:.4f} ({trade['profit_percent']:.1f}%)",
                f"{trade['hold_time']:.0f}s"
            )
        
        console.print(trade_table)
    
    logger.info("[DRY RUN] Bot stopped successfully")


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    logger.info(f"[DRY RUN] Received shutdown signal: {sig}")
    shutdown_event.set()


async def main():
    """Main entry point for dry run."""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start the bot
        bot_task = asyncio.create_task(start_bot_dry_run())
        
        # Wait for shutdown signal
        await shutdown_event.wait()
        
        # Stop the bot
        await stop_bot_dry_run()
        
        # Cancel the bot task if still running
        if not bot_task.done():
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
        
    except KeyboardInterrupt:
        logger.info("[DRY RUN] Keyboard interrupt received")
        await stop_bot_dry_run()
    except Exception as e:
        logger.error(f"[DRY RUN] Unexpected error: {e}", exc_info=True)
        await stop_bot_dry_run()
        sys.exit(1)


if __name__ == "__main__":
    console.print("🚀 [bold yellow]Starting Solana Pump.fun Bot in DRY RUN Mode[/bold yellow]")
    console.print("📁 Log file: logs/pump_bot_dry_run.log")
    console.print("Press Ctrl+C to stop\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n👋 Dry run terminated by user")
    except Exception as e:
        console.print(f"\n❌ Fatal error: {e}")
        sys.exit(1)