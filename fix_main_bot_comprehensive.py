#!/usr/bin/env python3

import os
import shutil
import sys
from pathlib import Path

def backup_file(filepath):
    """Create a backup of the file before modifying."""
    backup_path = f"{filepath}.backup_main_{os.getpid()}"
    if os.path.exists(filepath):
        shutil.copy2(filepath, backup_path)
        print(f"✓ Backed up: {filepath}")
    return backup_path

def write_file(filepath, content):
    """Write content to file."""
    dir_path = os.path.dirname(filepath)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Updated: {filepath}")

def fix_logger():
    """Fix logger.py with simplified configuration for Python 3.13."""
    content = '''"""
Simplified logging configuration for the Solana pump.fun sniping bot.
Fixed for Python 3.13 compatibility.
"""

import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
from datetime import datetime

# Simple console formatter
class SimpleConsoleFormatter(logging.Formatter):
    """Simple formatter with color support."""
    
    COLORS = {
        'DEBUG': '\\033[36m',    # Cyan
        'INFO': '\\033[32m',     # Green
        'WARNING': '\\033[33m',  # Yellow
        'ERROR': '\\033[31m',    # Red
        'CRITICAL': '\\033[35m', # Purple
    }
    RESET = '\\033[0m'
    
    def format(self, record):
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        
        # Format the message
        message = super().format(record)
        return message


def setup_logging(
    level: str = "DEBUG",
    file_path: str = "logs/bot.log",
    max_file_size_mb: int = 100,
    backup_count: int = 5,
    console_output: bool = True
) -> None:
    """
    Setup simple logging with file rotation and console output.
    """
    
    # Create logs directory if it doesn't exist
    log_file = Path(file_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=max_file_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, level.upper()))
    
    # Simple file formatter
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        
        # Console formatter with colors
        console_formatter = SimpleConsoleFormatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # Log initialization
    root_logger.info(f"Logging initialized - Level: {level}, File: {file_path}")
    print(f"✓ Logging initialized - Level: {level}, File: {file_path}")


class BotLogger:
    """Enhanced logger for bot-specific functionality."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._trade_count = 0
        self._error_count = 0
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        if extra_info:
            message = f"{message} | {extra_info}"
        self.logger.info(message)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        if extra_info:
            message = f"{message} | {extra_info}"
        self.logger.warning(message)
    
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self._error_count += 1
        kwargs['error_count'] = self._error_count
        extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        if extra_info:
            message = f"{message} | {extra_info}"
        self.logger.error(message, exc_info=kwargs.get('exc_info', False))
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        if extra_info:
            message = f"{message} | {extra_info}"
        self.logger.debug(message)
    
    def trade_executed(self, action: str, token: str, amount: float, price: float, **kwargs):
        """Log trade execution with structured data."""
        self._trade_count += 1
        self.logger.info(
            f"TRADE EXECUTED: {action} | token={token[:8]}... | amount={amount:.6f} | "
            f"price={price:.6f} | trade_number={self._trade_count}"
        )
    
    def position_update(self, token: str, entry_price: float, current_price: float, 
                       gain_percent: float, time_held: float, **kwargs):
        """Log position updates with performance metrics."""
        self.logger.info(
            f"POSITION UPDATE: {token[:8]}... | entry={entry_price:.6f} | "
            f"current={current_price:.6f} | gain={gain_percent:+.2f}% | held={time_held:.0f}s"
        )
    
    def strategy_triggered(self, rule_name: str, token: str, conditions: dict, **kwargs):
        """Log when a selling strategy rule is triggered."""
        cond_str = ", ".join([f"{k}={v}" for k, v in conditions.items()])
        self.logger.info(f"STRATEGY TRIGGERED: {rule_name} | token={token[:8]}... | {cond_str}")
    
    def performance_summary(self, total_trades: int, successful_trades: int, 
                          total_pnl: float, avg_hold_time: float, **kwargs):
        """Log performance summary statistics."""
        success_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0
        self.logger.info(
            f"PERFORMANCE SUMMARY: trades={total_trades} | successful={successful_trades} | "
            f"success_rate={success_rate:.1f}% | pnl={total_pnl:.4f} SOL | avg_hold={avg_hold_time:.0f}s"
        )
    
    def connection_status(self, service: str, status: str, **kwargs):
        """Log connection status for various services."""
        self.logger.info(f"CONNECTION {status}: {service}")
    
    def token_detected(self, token: str, market_cap: float, liquidity: float, **kwargs):
        """Log new token detection."""
        symbol = kwargs.get('symbol', 'Unknown')
        self.logger.info(
            f"NEW TOKEN DETECTED: {symbol} ({token[:8]}...) | "
            f"market_cap=${market_cap:,.2f} | liquidity=${liquidity:,.2f}"
        )
    
    def get_stats(self) -> dict:
        """Get logger statistics."""
        return {
            "trade_count": self._trade_count,
            "error_count": self._error_count
        }


def get_logger(name: str) -> BotLogger:
    """Get a bot logger instance."""
    return BotLogger(name)


# Pre-configured loggers for different modules
main_logger = get_logger("main")
trading_logger = get_logger("trading")
monitoring_logger = get_logger("monitoring")
strategy_logger = get_logger("strategy")
connection_logger = get_logger("connection")
'''
    
    write_file('src/utils/logger.py', content)

def fix_main_py():
    """Fix main.py to initialize logging properly."""
    content = '''"""
Main entry point for the Solana pump.fun sniping bot.
Initializes and coordinates all bot components.
"""
# File Location: src/main.py

import asyncio
import signal
import sys
from typing import Optional
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# CRITICAL: Setup logging FIRST before any imports that use logging
from src.utils.logger import setup_logging

# Initialize logging immediately
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)
setup_logging(
    level="INFO",  # Set to INFO for production, DEBUG for troubleshooting
    file_path=os.path.join(log_dir, "pump_bot.log"),
    max_file_size_mb=10,
    backup_count=5,
    console_output=True
)

# Now import everything else
from src.utils.config import config_manager
from src.utils.logger import get_logger

logger = get_logger("main")

# Global shutdown flag
shutdown_event = asyncio.Event()


async def start_bot():
    """Start the Solana pump.fun sniping bot with all components."""
    try:
        logger.info("="*60)
        logger.info("Starting Solana pump.fun sniping bot")
        logger.info("="*60)
        
        # Load configurations FIRST
        config_manager.load_all()
        logger.info("Configurations loaded successfully")
        
        # Import and initialize components AFTER config is loaded
        from src.core.connection_manager import connection_manager
        from src.core.wallet_manager import wallet_manager
        from src.trading.strategy_engine import initialize_strategy_engine
        from src.core.transaction_builder import initialize_transaction_builder
        from src.monitoring.pump_monitor import initialize_pump_monitor
        from src.monitoring.price_tracker import initialize_price_tracker
        from src.monitoring.volume_analyzer import initialize_volume_analyzer
        from src.monitoring.wallet_tracker import initialize_wallet_tracker
        from src.monitoring.event_processor import initialize_event_processor
        from src.ui.cli import initialize_bot_cli
        
        # Initialize components in order
        logger.info("Initializing components...")
        
        # Core components
        strategy_engine = initialize_strategy_engine()
        logger.info("✓ Strategy engine initialized")
        
        transaction_builder = initialize_transaction_builder()
        logger.info("✓ Transaction builder initialized")
        
        await connection_manager.initialize()
        logger.info("✓ Connection manager initialized")
        
        await wallet_manager.initialize()
        balance = await wallet_manager.get_balance()
        logger.info(f"✓ Wallet initialized. Balance: {balance:.6f} SOL")
        
        # Monitoring components
        pump_monitor = initialize_pump_monitor()
        price_tracker = initialize_price_tracker()
        volume_analyzer = initialize_volume_analyzer()
        wallet_tracker = initialize_wallet_tracker()
        logger.info("✓ Monitoring components initialized")
        
        # Event processor
        event_processor = initialize_event_processor()
        logger.info("✓ Event processor initialized")
        
        # UI
        bot_cli = initialize_bot_cli()
        logger.info("✓ CLI UI initialized")
        
        # Import components to ensure they're available
        from src.trading.strategy_engine import strategy_engine
        from src.monitoring.event_processor import event_processor
        from src.monitoring.pump_monitor import pump_monitor
        from src.monitoring.price_tracker import price_tracker
        from src.monitoring.volume_analyzer import volume_analyzer
        from src.monitoring.wallet_tracker import wallet_tracker
        from src.ui.cli import bot_cli
        
        # Register callbacks
        logger.info("Registering callbacks...")
        
        if event_processor and strategy_engine:
            event_processor.register_new_token_callback(strategy_engine.evaluate_new_token)
            event_processor.register_price_update_callback(strategy_engine.evaluate_price_update)
            event_processor.register_volume_spike_callback(strategy_engine.evaluate_volume_spike)
            logger.info("✓ Event callbacks registered")
        
        # Start all monitoring components
        logger.info("Starting monitoring components...")
        
        if pump_monitor:
            await pump_monitor.start()
            logger.info("✓ Pump monitor started")
            
        if price_tracker:
            await price_tracker.start()
            logger.info("✓ Price tracker started")
            
        if volume_analyzer:
            await volume_analyzer.start()
            logger.info("✓ Volume analyzer started")
            
        if wallet_tracker:
            await wallet_tracker.start()
            logger.info("✓ Wallet tracker started")
            tracked_wallets = list(wallet_tracker.tracked_wallets)
            logger.info(f"  Tracking {len(tracked_wallets)} wallet(s): {tracked_wallets}")
            
        if event_processor:
            await event_processor.start()
            logger.info("✓ Event processor started")
        
        # Start strategy engine
        if strategy_engine:
            await strategy_engine.start()
            logger.info("✓ Strategy engine started")
        
        logger.info("="*60)
        logger.info("Bot started successfully! Monitoring for transactions...")
        logger.info("="*60)
        
        # Start UI (this will block until stopped)
        if bot_cli:
            await bot_cli.start()
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        raise


async def stop_bot():
    """Stop the bot gracefully."""
    try:
        logger.info("="*60)
        logger.info("Stopping Solana pump.fun sniping bot...")
        
        # Import components
        try:
            from src.trading.strategy_engine import strategy_engine
            from src.monitoring.event_processor import event_processor
            from src.monitoring.pump_monitor import pump_monitor
            from src.monitoring.price_tracker import price_tracker
            from src.monitoring.volume_analyzer import volume_analyzer
            from src.monitoring.wallet_tracker import wallet_tracker
            from src.ui.cli import bot_cli
            from src.core.connection_manager import connection_manager
        except ImportError as e:
            logger.warning(f"Some components could not be imported for shutdown: {e}")
        
        # Stop components in reverse order
        components = [
            ("UI", 'bot_cli'),
            ("Strategy Engine", 'strategy_engine'),
            ("Event Processor", 'event_processor'),
            ("Wallet Tracker", 'wallet_tracker'),
            ("Volume Analyzer", 'volume_analyzer'),
            ("Price Tracker", 'price_tracker'),
            ("Pump Monitor", 'pump_monitor'),
            ("Connection Manager", 'connection_manager')
        ]
        
        for name, var_name in components:
            try:
                if var_name in locals():
                    component = locals()[var_name]
                    if component:
                        if var_name == 'bot_cli':
                            component.stop()
                        elif var_name == 'connection_manager':
                            await component.close()
                        else:
                            await component.stop()
                        logger.info(f"✓ {name} stopped")
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")
        
        logger.info("Bot stopped successfully")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Error stopping bot: {e}", exc_info=True)


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    logger.info(f"Received shutdown signal: {sig}")
    shutdown_event.set()


async def main():
    """Main entry point."""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start the bot
        bot_task = asyncio.create_task(start_bot())
        
        # Wait for shutdown signal
        await shutdown_event.wait()
        
        # Stop the bot
        await stop_bot()
        
        # Cancel the bot task if still running
        if not bot_task.done():
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await stop_bot()
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}", exc_info=True)
        await stop_bot()
        sys.exit(1)


if __name__ == "__main__":
    # Run the bot
    print("🚀 Starting Solana Pump.fun Sniping Bot...")
    print(f"📁 Log file: logs/pump_bot.log")
    print("Press Ctrl+C to stop\\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n👋 Bot terminated by user")
    except Exception as e:
        print(f"\\n❌ Fatal error: {e}")
        sys.exit(1)
'''
    
    write_file('src/main.py', content)

def fix_wallet_tracker_final():
    """Fix wallet_tracker.py with all DEX support and proper logging."""
    content = '''"""
Enhanced wallet tracking for the Solana pump.fun sniping bot.
Monitors specific wallets for transactions on pump.fun, Raydium, and other DEXs.
"""
# File Location: src/monitoring/wallet_tracker.py

import asyncio
from typing import Dict, Any, Optional, Callable, List, Set
import json
from datetime import datetime
from solders.pubkey import Pubkey as PublicKey
from solana.rpc.commitment import Confirmed
import base58
import time
from solders.signature import Signature

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.core.connection_manager import connection_manager

logger = get_logger("wallet_tracker")


class EnhancedWalletTracker:
    """
    Enhanced wallet tracker with robust monitoring for pump.fun and DEX transactions.
    """
    
    def __init__(self):
        self.settings = config_manager.get_settings()
        self.tracked_wallets: Set[str] = set(self.settings.tracking.wallets)
        
        # Program IDs for various DEXs and protocols
        self.program_ids = {
            "Pump.fun": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
            "Raydium V4": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
            "Raydium Launchpad": "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj",
            "OKX DEX Router": "6m2CDdhRgxpH4WjvdzxAYbGxwdGUz5MziiL5jek2kBma",
            "Jupiter V6": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
        }
        
        self.dex_program_ids = set(self.program_ids.values())
        self.running: bool = False
        self.buy_callbacks: List[Callable[[str, str, float], None]] = []
        self.processed_signatures: Set[str] = set()
        self.monitoring_tasks: List[asyncio.Task] = []
        self.monitoring_active = False
        
        # Statistics
        self.stats = {
            "transactions_detected": 0,
            "buys_detected": 0,
            "sells_detected": 0,
            "dex_swaps_detected": 0,
            "errors": 0,
            "checks_performed": 0,
            "last_check": time.time()
        }
        
        logger.info(f"WalletTracker initialized - tracking {len(self.tracked_wallets)} wallet(s)")
        
    async def start(self) -> None:
        """Start tracking specified wallets for transactions."""
        if self.running:
            logger.warning("Wallet tracker already running")
            return
            
        if not self.tracked_wallets:
            logger.warning("No wallets specified for tracking")
            return
            
        self.running = True
        self.monitoring_active = True
        
        logger.info(f"Starting wallet tracker for wallets: {list(self.tracked_wallets)}")
        
        # Start monitoring task for each wallet
        for wallet_address in self.tracked_wallets:
            task = asyncio.create_task(self._monitor_wallet(wallet_address))
            self.monitoring_tasks.append(task)
        
        # Start statistics logger
        asyncio.create_task(self._log_statistics())
        
    async def stop(self) -> None:
        """Stop tracking wallets."""
        self.running = False
        self.monitoring_active = False
        
        # Cancel all monitoring tasks
        for task in self.monitoring_tasks:
            task.cancel()
        
        await asyncio.gather(*self.monitoring_tasks, return_exceptions=True)
        self.monitoring_tasks.clear()
        
        logger.info("Wallet tracker stopped")
    
    async def _monitor_wallet(self, wallet_address: str) -> None:
        """Monitor a wallet for transactions."""
        logger.info(f"Starting to monitor wallet: {wallet_address}")
        
        while self.running:
            try:
                await self._check_wallet_transactions(wallet_address)
                self.stats["checks_performed"] += 1
                await asyncio.sleep(1)  # Check every second
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring wallet {wallet_address}: {e}")
                self.stats["errors"] += 1
                await asyncio.sleep(5)
    
    async def _check_wallet_transactions(self, wallet_address: str) -> None:
        """Check recent transactions for a wallet."""
        try:
            client = await connection_manager.get_rpc_client()
            if not client:
                return
            
            # Get recent signatures
            response = await client.get_signatures_for_address(
                PublicKey.from_string(wallet_address),
                limit=5
            )
            
            if not response or not response.value:
                return
            
            # Process new transactions
            for sig_info in response.value:
                signature = str(sig_info.signature)
                
                if signature in self.processed_signatures:
                    continue
                
                # Mark as processed
                self.processed_signatures.add(signature)
                
                # Fetch transaction details
                tx_response = await client.get_transaction(
                    sig_info.signature,
                    encoding="jsonParsed",
                    commitment=Confirmed,
                    max_supported_transaction_version=0
                )
                
                if tx_response and tx_response.value:
                    await self._analyze_transaction(tx_response.value, wallet_address, signature)
                    
        except Exception as e:
            logger.error(f"Error checking transactions: {e}")
            self.stats["errors"] += 1
    
    async def _analyze_transaction(self, tx_data: Any, wallet_address: str, signature: str) -> None:
        """Analyze a transaction for DEX operations."""
        try:
            # Convert to dict if needed
            if hasattr(tx_data, 'to_json'):
                tx_json = tx_data.to_json()
                tx_data = json.loads(tx_json)
            
            meta = tx_data.get("meta", {})
            if meta.get("err"):
                return  # Skip failed transactions
            
            transaction = tx_data.get("transaction", {})
            message = transaction.get("message", {})
            instructions = message.get("instructions", [])
            logs = meta.get("logMessages", [])
            
            # Check for DEX programs
            program_ids_in_tx = set()
            for instruction in instructions:
                program_id = instruction.get("programId")
                if program_id and program_id in self.dex_program_ids:
                    program_ids_in_tx.add(program_id)
            
            if not program_ids_in_tx:
                return  # No DEX programs found
            
            # Log the DEX transaction
            self.stats["transactions_detected"] += 1
            
            for prog_id in program_ids_in_tx:
                prog_name = next((name for name, id in self.program_ids.items() if id == prog_id), prog_id)
                logger.info(f"[{prog_name}] Transaction detected: {signature[:32]}...")
            
            # Analyze for swap details
            swap_info = self._extract_swap_info(instructions, logs, program_ids_in_tx)
            
            if swap_info and swap_info.get("is_buy"):
                self.stats["buys_detected"] += 1
                self.stats["dex_swaps_detected"] += 1
                
                token_address = swap_info.get("token_address", "Unknown")
                amount_sol = swap_info.get("amount_sol", 0)
                dex_name = swap_info.get("dex_name", "Unknown DEX")
                
                logger.info(
                    f"🟢 BUY DETECTED on {dex_name} | "
                    f"Wallet: {wallet_address[:8]}... | "
                    f"Token: {token_address[:16]}... | "
                    f"Amount: {amount_sol:.6f} SOL | "
                    f"TX: {signature[:32]}..."
                )
                
                # Trigger callbacks
                for callback in self.buy_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(wallet_address, token_address, amount_sol)
                        else:
                            callback(wallet_address, token_address, amount_sol)
                    except Exception as e:
                        logger.error(f"Error in buy callback: {e}")
                        
        except Exception as e:
            logger.error(f"Error analyzing transaction: {e}")
            self.stats["errors"] += 1
    
    def _extract_swap_info(self, instructions: List[Dict], logs: List[str], 
                          program_ids: Set[str]) -> Optional[Dict[str, Any]]:
        """Extract swap information from transaction."""
        try:
            # Default values
            is_buy = False
            token_address = "Unknown"
            amount_sol = 0.0
            dex_name = "Unknown DEX"
            
            # Identify DEX
            for prog_id in program_ids:
                if prog_id in self.program_ids.values():
                    dex_name = next(name for name, id in self.program_ids.items() if id == prog_id)
                    break
            
            # Parse logs for swap details
            for log in logs:
                log_lower = log.lower()
                
                # Detect buy operations
                if any(buy_indicator in log_lower for buy_indicator in 
                      ["buy", "swap executed", "buyexactin", "buy_exact_in"]):
                    is_buy = True
                
                # Extract amounts
                if "amount_in:" in log:
                    try:
                        amount_str = log.split("amount_in:")[1].strip().split()[0].replace(",", "")
                        amount_sol = float(amount_str) / 1e9  # Convert lamports to SOL
                    except:
                        pass
            
            # Extract token address from instructions
            for instruction in instructions:
                accounts = instruction.get("accounts", [])
                if len(accounts) >= 5:
                    # Common pattern: destination mint at index 4 for buys
                    potential_token = accounts[4] if isinstance(accounts[4], str) else None
                    if potential_token and potential_token != "So11111111111111111111111111111111111111112":
                        token_address = potential_token
                        break
            
            if is_buy and amount_sol > 0:
                return {
                    "is_buy": True,
                    "token_address": token_address,
                    "amount_sol": amount_sol,
                    "dex_name": dex_name
                }
                
        except Exception as e:
            logger.error(f"Error extracting swap info: {e}")
        
        return None
    
    async def _log_statistics(self):
        """Log statistics periodically."""
        while self.running:
            await asyncio.sleep(30)  # Every 30 seconds
            
            logger.info(
                f"📊 STATS | Checks: {self.stats['checks_performed']} | "
                f"TX: {self.stats['transactions_detected']} | "
                f"Buys: {self.stats['buys_detected']} | "
                f"DEX Swaps: {self.stats['dex_swaps_detected']} | "
                f"Errors: {self.stats['errors']}"
            )
    
    def register_buy_callback(self, callback: Callable[[str, str, float], None]) -> None:
        """Register a callback for buy transactions."""
        self.buy_callbacks.append(callback)
        logger.info(f"Registered buy callback - Total callbacks: {len(self.buy_callbacks)}")
    
    def get_stats(self) -> Dict[str, int]:
        """Get tracking statistics."""
        stats = self.stats.copy()
        stats["monitoring_active"] = self.monitoring_active
        stats["tracked_wallets"] = len(self.tracked_wallets)
        return stats
    
    def is_monitoring_active(self) -> bool:
        """Check if monitoring is actively running."""
        return self.monitoring_active and self.running


# Global wallet tracker instance
wallet_tracker = None

def initialize_wallet_tracker():
    """Initialize the global wallet tracker instance."""
    global wallet_tracker
    wallet_tracker = EnhancedWalletTracker()
    return wallet_tracker
'''
    
    write_file('src/monitoring/wallet_tracker.py', content)

def main():
    """Apply all fixes to the main bot."""
    print("="*60)
    print("🔧 Applying Comprehensive Fix for Main Bot")
    print("="*60)
    print()
    
    # Check we're in the right directory
    if not os.path.exists('src/main.py'):
        print("❌ ERROR: This script must be run from the project root directory")
        print("   Please cd to C:\\Users\\JJ\\Desktop\\Clide-Bot and run again")
        return 1
    
    print("📁 Working directory:", os.getcwd())
    print()
    
    # Ensure logs directory exists
    log_dir = Path("logs")
    if not log_dir.exists():
        log_dir.mkdir(exist_ok=True)
        print("✓ Created logs directory")
    
    try:
        print("Applying fixes...")
        print()
        
        # Apply all fixes
        fix_logger()
        fix_main_py()
        fix_wallet_tracker_final()
        
        print()
        print("="*60)
        print("✅ All fixes applied successfully!")
        print("="*60)
        print()
        print("📋 What was fixed:")
        print("1. ✓ Logger - Simplified for Python 3.13 compatibility")
        print("2. ✓ Main.py - Better initialization and logging")
        print("3. ✓ Wallet Tracker - Full DEX support (Raydium, OKX, Jupiter)")
        print()
        print("🚀 To run the bot:")
        print("   python -m src.main")
        print()
        print("📊 The bot will now:")
        print("   - Write logs to: logs/pump_bot.log")
        print("   - Monitor tracked wallets every second")
        print("   - Detect buys on Pump.fun, Raydium, OKX DEX, Jupiter")
        print("   - Show colored console output")
        print("   - Display statistics every 30 seconds")
        print()
        print("👀 Watch for:")
        print("   - 🟢 BUY DETECTED messages")
        print("   - 📊 STATS updates")
        print("   - Transaction detections from various DEXs")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error applying fixes: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
