#!/usr/bin/env python3


import os
import shutil
import sys

def backup_file(filepath):
    """Create a backup of the file before modifying."""
    backup_path = f"{filepath}.backup_{os.getpid()}"
    if os.path.exists(filepath):
        shutil.copy2(filepath, backup_path)
        print(f"✓ Backed up: {filepath}")
    return backup_path

def write_file(filepath, content):
    """Write content to file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Updated: {filepath}")

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

# CRITICAL: Setup logging FIRST before any imports that use logging
from src.utils.logger import setup_logging

# Initialize logging immediately
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)
setup_logging(
    level="DEBUG",  # Set to DEBUG for maximum verbosity
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
        logger.info("="*50)
        logger.info("Starting Solana pump.fun sniping bot")
        logger.info("="*50)
        
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
        
        # Initialize strategy engine
        strategy_engine = initialize_strategy_engine()
        logger.info("Strategy engine initialized")
        
        # Initialize transaction builder
        transaction_builder = initialize_transaction_builder()
        logger.info("Transaction builder initialized")
        
        # Initialize connection manager
        await connection_manager.initialize()
        logger.info("Connection manager initialized")
        
        # Initialize wallet manager
        await wallet_manager.initialize()
        balance = await wallet_manager.get_balance()
        logger.info(f"Wallet initialized. Balance: {balance} SOL")
        
        # Initialize UI
        bot_cli = initialize_bot_cli()
        logger.info("CLI UI initialized")
        
        # Initialize monitoring components
        pump_monitor = initialize_pump_monitor()
        price_tracker = initialize_price_tracker()
        volume_analyzer = initialize_volume_analyzer()
        wallet_tracker = initialize_wallet_tracker()
        logger.info("Monitoring components initialized")
        
        # Initialize event processor
        event_processor = initialize_event_processor()
        logger.info("Event processor initialized")
        
        # Import components again to ensure they're available
        from src.trading.strategy_engine import strategy_engine
        from src.monitoring.event_processor import event_processor
        from src.monitoring.pump_monitor import pump_monitor
        from src.monitoring.price_tracker import price_tracker
        from src.monitoring.volume_analyzer import volume_analyzer
        from src.monitoring.wallet_tracker import wallet_tracker
        from src.ui.cli import bot_cli
        
        # Register callbacks
        if event_processor and strategy_engine:
            event_processor.register_new_token_callback(strategy_engine.evaluate_new_token)
            event_processor.register_price_update_callback(strategy_engine.evaluate_price_update)
            event_processor.register_volume_spike_callback(strategy_engine.evaluate_volume_spike)
            logger.info("Event callbacks registered")
        else:
            logger.error("Failed to register callbacks: event_processor or strategy_engine is None")
        
        # Start all monitoring components
        if pump_monitor:
            await pump_monitor.start()
        if price_tracker:
            await price_tracker.start()
        if volume_analyzer:
            await volume_analyzer.start()
        if wallet_tracker:
            await wallet_tracker.start()
        if event_processor:
            await event_processor.start()
        logger.info("All monitoring components started")
        
        # Start strategy engine
        if strategy_engine:
            await strategy_engine.start()
            logger.info("Strategy engine started")
        
        # Start UI (this will block until stopped)
        logger.info("Solana pump.fun sniping bot started successfully")
        logger.info("="*50)
        if bot_cli:
            await bot_cli.start()
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        raise


async def stop_bot():
    """Stop the bot gracefully."""
    try:
        logger.info("Stopping Solana pump.fun sniping bot")
        
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
        except ImportError:
            logger.warning("Some components could not be imported for shutdown")
        
        # Stop components in reverse order
        try:
            if 'strategy_engine' in locals() and strategy_engine:
                await strategy_engine.stop()
        except:
            pass
            
        try:
            if 'event_processor' in locals() and event_processor:
                await event_processor.stop()
        except:
            pass
        
        try:
            if 'pump_monitor' in locals() and pump_monitor:
                await pump_monitor.stop()
        except:
            pass
            
        try:
            if 'price_tracker' in locals() and price_tracker:
                await price_tracker.stop()
        except:
            pass
            
        try:
            if 'volume_analyzer' in locals() and volume_analyzer:
                await volume_analyzer.stop()
        except:
            pass
            
        try:
            if 'wallet_tracker' in locals() and wallet_tracker:
                await wallet_tracker.stop()
        except:
            pass
        
        try:
            if 'bot_cli' in locals() and bot_cli:
                bot_cli.stop()
        except:
            pass
        
        try:
            if 'connection_manager' in locals() and connection_manager:
                await connection_manager.close()
        except:
            pass
        
        logger.info("Bot stopped successfully")
        
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
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
'''
    
    write_file('src/main.py', content)

def fix_wallet_tracker():
    """Fix wallet_tracker.py with enhanced logging and transaction detection."""
    content = '''"""
Enhanced wallet tracking for the Solana pump.fun sniping bot.
Monitors specific wallets for transactions and mimics their buying behavior.
Fixed version with comprehensive logging and transaction detection.
"""
# File Location: src/monitoring/wallet_tracker.py

import asyncio
from typing import Dict, Any, Optional, Callable, List, Set
import json
from datetime import datetime
from solders.pubkey import Pubkey as PublicKey
from solana.rpc.commitment import Confirmed
import websockets
import base58
import struct
import time
import traceback
from solders.signature import Signature

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.core.connection_manager import connection_manager

logger = get_logger("wallet_tracker")


class WalletTransaction:
    """Stores information about a wallet transaction."""
    
    def __init__(self, signature: str, timestamp: float):
        self.signature: str = signature
        self.timestamp: float = timestamp
        self.token_address: Optional[str] = None
        self.amount_sol: float = 0.0
        self.is_buy: bool = False
        self.is_sell: bool = False
        self.is_create: bool = False
        self.raw_data: Optional[Dict] = None


class EnhancedWalletTracker:
    """
    Enhanced wallet tracker with robust monitoring for pump.fun transactions.
    """
    
    def __init__(self):
        self.settings = config_manager.get_settings()
        
        # Use the configured WebSocket endpoint from settings
        self.websocket_url = self.settings.solana.websocket_endpoint
        logger.info(f"WalletTracker initialized - WebSocket endpoint: {self.websocket_url}")
        
        self.tracked_wallets: Set[str] = set(self.settings.tracking.wallets)
        # Fix PublicKey initialization - use from_string for base58 addresses
        self.pump_program_id = PublicKey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
        self.subscriptions: Dict[int, str] = {}
        self.transaction_cache: Set[str] = set()  # Prevent duplicate processing
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running: bool = False
        self.buy_callbacks: List[Callable[[str, str, float], None]] = []
        self.processed_signatures: Set[str] = set()
        self.websocket_tasks: List[asyncio.Task] = []
        self.monitoring_active = False  # Track if monitoring is active
        
        # Keep track of last signature per wallet to avoid reprocessing
        self.last_signature_per_wallet: Dict[str, str] = {}
        
        # Instruction discriminators for pump.fun
        self.BUY_DISCRIMINATOR = bytes([102, 6, 61, 18, 1, 218, 235, 234])
        self.SELL_DISCRIMINATOR = bytes([51, 230, 133, 164, 1, 127, 131, 173])
        self.CREATE_DISCRIMINATOR = bytes([181, 157, 89, 67, 143, 182, 52, 72])
        
        # Transaction parser
        self.parser = PumpFunTransactionParser()
        
        # Statistics tracking
        self.stats = {
            "transactions_detected": 0,
            "buys_detected": 0,
            "sells_detected": 0,
            "creates_detected": 0,
            "errors": 0,
            "checks_performed": 0,
            "last_check": time.time()
        }
        
        logger.info(f"WalletTracker configured to track {len(self.tracked_wallets)} wallet(s)")
        
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
        logger.info("="*60)
        logger.info(f"Starting enhanced wallet tracker for {len(self.tracked_wallets)} wallets")
        logger.info(f"Tracked wallets: {list(self.tracked_wallets)}")
        logger.info("="*60)
        
        # Start monitoring with periodic transaction checks
        for wallet_address in self.tracked_wallets:
            logger.info(f"🚀 Starting monitoring task for wallet: {wallet_address}")
            task = asyncio.create_task(self._monitor_wallet_transactions(wallet_address))
            self.websocket_tasks.append(task)
        
        # Start statistics logger
        asyncio.create_task(self._log_statistics())
        
    async def stop(self) -> None:
        """Stop tracking wallets."""
        self.running = False
        self.monitoring_active = False
        logger.info("Stopping wallet tracker")
        
        # Cancel all monitoring tasks
        for task in self.websocket_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.websocket_tasks, return_exceptions=True)
        self.websocket_tasks.clear()
        
        # Close WebSocket if open
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
            self.websocket = None
        
        logger.info("Wallet tracker stopped")
    
    async def _log_statistics(self):
        """Log statistics periodically."""
        while self.running:
            await asyncio.sleep(30)  # Log every 30 seconds
            logger.info(
                f"📊 [STATS] Checks: {self.stats['checks_performed']}, "
                f"Transactions: {self.stats['transactions_detected']}, "
                f"Buys: {self.stats['buys_detected']}, "
                f"Sells: {self.stats['sells_detected']}, "
                f"Creates: {self.stats['creates_detected']}, "
                f"Errors: {self.stats['errors']}"
            )
    
    async def _monitor_wallet_transactions(self, wallet_address: str) -> None:
        """Monitor a wallet's transactions periodically."""
        logger.info(f"📡 Starting transaction monitoring loop for wallet {wallet_address[:8]}...")
        check_count = 0
        
        while self.running:
            try:
                check_count += 1
                current_time = datetime.now().strftime("%H:%M:%S")
                logger.debug(f"[{current_time}] Check #{check_count} for wallet {wallet_address[:8]}...")
                
                await self._check_recent_transactions(wallet_address)
                self.stats["last_check"] = time.time()
                self.stats["checks_performed"] += 1
                
                await asyncio.sleep(1)  # Check every 1 second for faster detection
                
            except asyncio.CancelledError:
                logger.info(f"Monitoring cancelled for wallet {wallet_address[:8]}...")
                break
            except Exception as e:
                logger.error(f"❌ Error monitoring wallet {wallet_address[:8]}...: {str(e)}", exc_info=True)
                self.stats["errors"] += 1
                await asyncio.sleep(5)  # Wait longer on error
    
    async def _check_recent_transactions(self, wallet_address: str) -> None:
        """Check recent transactions for a wallet."""
        try:
            # Get RPC client
            client = await connection_manager.get_rpc_client()
            if not client:
                logger.error("No RPC client available")
                return
            
            logger.debug(f"🔍 [RPC] Checking signatures for address: {wallet_address[:8]}...")
            
            # Get recent signatures
            response = await client.get_signatures_for_address(
                PublicKey.from_string(wallet_address),
                limit=5  # Check last 5 transactions
            )
            
            if not response or not response.value:
                logger.debug(f"No transactions found for wallet {wallet_address[:8]}...")
                return
            
            logger.debug(f"📋 [RPC] Found {len(response.value)} recent signatures for wallet {wallet_address[:8]}...")
            
            # Check if there are new transactions
            new_transactions = False
            for sig_info in response.value:
                signature = str(sig_info.signature)
                
                if signature in self.processed_signatures:
                    continue
                
                new_transactions = True
                logger.info(f"🆕 [NEW TX] Found new transaction: {signature[:8]}... for wallet {wallet_address[:8]}...")
                
                # Fetch transaction details
                logger.debug(f"📥 [RPC] Fetching transaction details for: {signature[:8]}...")
                tx_response = await client.get_transaction(
                    sig_info.signature,
                    encoding="jsonParsed",
                    commitment=Confirmed,
                    max_supported_transaction_version=0
                )
                
                if tx_response and tx_response.value:
                    # Process transaction to check if it's pump.fun related
                    await self._analyze_transaction(tx_response.value, wallet_address, signature)
                else:
                    logger.warning(f"⚠️ [RPC] No transaction data returned for signature: {signature[:8]}...")
            
            if not new_transactions:
                logger.debug(f"No new transactions for wallet {wallet_address[:8]}...")
                    
        except Exception as e:
            logger.error(f"❌ [RPC] Error checking recent transactions: {str(e)}", exc_info=True)
            self.stats["errors"] += 1
    
    async def _analyze_transaction(self, tx_data: Any, wallet_address: str, signature: str) -> None:
        """Analyze a transaction for pump.fun operations."""
        try:
            logger.debug(f"🔬 [ANALYZE] Starting analysis of transaction {signature[:8]}...")
            
            # Convert solders object to dict if needed
            if hasattr(tx_data, 'to_json'):
                tx_json = tx_data.to_json()
                tx_data = json.loads(tx_json)
            
            meta = tx_data.get("meta", {})
            if meta.get("err"):
                logger.debug(f"Skipping failed transaction: {signature[:8]}...")
                self.processed_signatures.add(signature)
                return
            
            transaction = tx_data.get("transaction", {})
            message = transaction.get("message", {})
            instructions = message.get("instructions", [])
            logs = meta.get("logMessages", [])
            
            logger.debug(f"📝 [TX] Transaction {signature[:8]}... has {len(instructions)} instructions")
            
            # Log all program IDs in the transaction
            program_ids = set()
            for instruction in instructions:
                program_id = instruction.get("programId")
                if program_id:
                    program_ids.add(program_id)
            
            logger.debug(f"📦 [TX] Programs in transaction: {list(program_ids)}")
            
            # Check each instruction
            pump_found = False
            for i, instruction in enumerate(instructions):
                program_id = instruction.get("programId")
                
                # Check if it's a pump.fun instruction
                if program_id == str(self.pump_program_id):
                    pump_found = True
                    self.processed_signatures.add(signature)
                    logger.info(f"🎯 [PUMP.FUN] Found pump.fun transaction: {signature[:8]}...")
                    logger.info(f"🎯 [PUMP.FUN] Instruction #{i+1} - Program: {program_id}")
                    self.stats["transactions_detected"] += 1
                    
                    # Parse the instruction
                    tx_info = await self._parse_pump_instruction(instruction, logs, wallet_address, signature)
                    if tx_info:
                        await self._process_pump_transaction(tx_info)
            
            if not pump_found:
                logger.debug(f"🔍 [TX] No pump.fun instructions in transaction {signature[:8]}...")
                # Mark as processed to avoid checking again
                self.processed_signatures.add(signature)
                        
        except Exception as e:
            logger.error(f"❌ [TX] Error analyzing transaction: {str(e)}", exc_info=True)
            self.stats["errors"] += 1
    
    async def _parse_pump_instruction(self, instruction: Dict, logs: List[str], wallet: str, signature: str) -> Optional[Dict]:
        """Parse pump.fun instruction to determine operation type."""
        try:
            logger.debug(f"🔍 [PARSE] Parsing pump.fun instruction for signature {signature[:8]}...")
            
            # Get instruction data
            data = instruction.get("data")
            if not data:
                logger.warning("[PARSE] No instruction data found")
                return None
            
            operation = "unknown"
            token = "unknown"
            amount_sol = 0.0
            
            # Log the raw data for debugging
            logger.debug(f"📊 [PARSE] Raw instruction data: {data[:50]}..." if len(str(data)) > 50 else f"[PARSE] Raw instruction data: {data}")
            
            # Try to decode base58 data
            try:
                if isinstance(data, str):
                    decoded = base58.b58decode(data)
                    if len(decoded) >= 8:
                        discriminator = decoded[:8]
                        logger.debug(f"🔢 [PARSE] Discriminator bytes: {discriminator.hex()}")
                        
                        if discriminator == self.BUY_DISCRIMINATOR:
                            operation = "buy"
                            logger.info("💰 [PARSE] ✅ Detected BUY operation from discriminator")
                        elif discriminator == self.SELL_DISCRIMINATOR:
                            operation = "sell"
                            logger.info("💸 [PARSE] ✅ Detected SELL operation from discriminator")
                        elif discriminator == self.CREATE_DISCRIMINATOR:
                            operation = "create"
                            logger.info("✨ [PARSE] ✅ Detected CREATE operation from discriminator")
            except Exception as e:
                logger.debug(f"[PARSE] Could not decode instruction data: {e}")
            
            # If we couldn't determine from discriminator, check logs
            if operation == "unknown" and logs:
                logger.debug(f"📜 [PARSE] Checking {len(logs)} transaction logs...")
                # Log first few logs for debugging
                for i, log in enumerate(logs[:5]):
                    logger.debug(f"  Log {i}: {log}")
                
                logs_str = " ".join(logs).lower()
                if "buy" in logs_str or "swap executed" in logs_str:
                    operation = "buy"
                    logger.info("💰 [PARSE] ✅ Detected BUY operation from logs")
                elif "sell" in logs_str:
                    operation = "sell"
                    logger.info("💸 [PARSE] ✅ Detected SELL operation from logs")
                elif "create" in logs_str or "initialize" in logs_str:
                    operation = "create"
                    logger.info("✨ [PARSE] ✅ Detected CREATE operation from logs")
            
            # Try to extract token address from accounts
            accounts = instruction.get("accounts", [])
            logger.debug(f"👥 [PARSE] Instruction has {len(accounts)} accounts")
            if len(accounts) > 2:
                # Usually the token mint is in the accounts
                token = accounts[2] if isinstance(accounts[2], str) else token
                logger.debug(f"🪙 [PARSE] Extracted token address: {token[:8]}...")
            
            # Try to extract amount from logs
            for log in logs:
                if "amount:" in log.lower():
                    try:
                        # Extract number after "amount:"
                        parts = log.lower().split("amount:")
                        if len(parts) > 1:
                            amount_str = parts[1].strip().split()[0]
                            amount_sol = float(amount_str) / 1e9  # Convert lamports to SOL
                            logger.debug(f"💵 [PARSE] Extracted amount: {amount_sol} SOL")
                    except:
                        pass
            
            result = {
                "operation": operation,
                "wallet": wallet,
                "signature": signature,
                "token": token,
                "amount_sol": amount_sol
            }
            
            logger.info(f"✅ [PARSE] Final result - Operation: {operation}, Token: {token[:8]}..., Amount: {amount_sol} SOL")
            return result
            
        except Exception as e:
            logger.error(f"❌ [PARSE] Error parsing instruction: {str(e)}", exc_info=True)
            return None
    
    async def _process_pump_transaction(self, tx_info: Dict) -> None:
        """Process a pump.fun transaction."""
        operation = tx_info.get("operation")
        wallet = tx_info.get("wallet")
        token = tx_info.get("token", "unknown")
        amount_sol = tx_info.get("amount_sol", 0)
        signature = tx_info.get("signature")
        
        logger.info("="*60)
        
        if operation == "buy":
            self.stats["buys_detected"] += 1
            logger.info(
                f"🟢💰 [BUY DETECTED] Wallet {wallet[:8]}... bought token {token[:8]}... "
                f"for {amount_sol:.4f} SOL (tx: {signature[:8]}...)"
            )
            
            # Trigger buy callbacks
            logger.info(f"📞 [CALLBACK] Triggering {len(self.buy_callbacks)} buy callbacks...")
            for i, callback in enumerate(self.buy_callbacks):
                try:
                    logger.debug(f"[CALLBACK] Executing callback #{i+1}")
                    if asyncio.iscoroutinefunction(callback):
                        await callback(wallet, token, amount_sol)
                    else:
                        callback(wallet, token, amount_sol)
                    logger.debug(f"✅ [CALLBACK] Callback #{i+1} executed successfully")
                except Exception as e:
                    logger.error(f"❌ [CALLBACK] Error in buy callback #{i+1}: {str(e)}", exc_info=True)
                    
        elif operation == "sell":
            self.stats["sells_detected"] += 1
            logger.info(
                f"🔴💸 [SELL DETECTED] Wallet {wallet[:8]}... sold token {token[:8]}... "
                f"for {amount_sol:.4f} SOL (tx: {signature[:8]}...)"
            )
            
        elif operation == "create":
            self.stats["creates_detected"] += 1
            logger.info(
                f"✨🚀 [CREATE DETECTED] Wallet {wallet[:8]}... created token {token[:8]}... "
                f"(tx: {signature[:8]}...)"
            )
            
            # Treat create as a buy signal
            logger.info(f"📞 [CALLBACK] Triggering {len(self.buy_callbacks)} buy callbacks for CREATE...")
            for i, callback in enumerate(self.buy_callbacks):
                try:
                    logger.debug(f"[CALLBACK] Executing callback #{i+1} for CREATE")
                    if asyncio.iscoroutinefunction(callback):
                        await callback(wallet, token, 0.1)  # Default amount for creates
                    else:
                        callback(wallet, token, 0.1)
                    logger.debug(f"✅ [CALLBACK] Callback #{i+1} executed successfully")
                except Exception as e:
                    logger.error(f"❌ [CALLBACK] Error in buy callback #{i+1} for create: {str(e)}", exc_info=True)
        
        logger.info("="*60)
    
    def register_buy_callback(self, callback: Callable[[str, str, float], None]) -> None:
        """Register a callback for buy transactions."""
        self.buy_callbacks.append(callback)
        logger.info(f"✅ Registered wallet buy callback. Total callbacks: {len(self.buy_callbacks)}")
    
    def add_tracked_wallet(self, wallet_address: str) -> None:
        """Add a wallet to track."""
        if wallet_address not in self.tracked_wallets:
            self.tracked_wallets.add(wallet_address)
            logger.info(f"➕ Added wallet to track: {wallet_address[:8]}...")
            
            # If already running, start monitoring this wallet
            if self.running:
                task = asyncio.create_task(self._monitor_wallet_transactions(wallet_address))
                self.websocket_tasks.append(task)
    
    def get_stats(self) -> Dict[str, int]:
        """Get tracking statistics."""
        stats = self.stats.copy()
        stats["monitoring_active"] = self.monitoring_active
        stats["tracked_wallets"] = len(self.tracked_wallets)
        return stats
    
    def is_monitoring_active(self) -> bool:
        """Check if monitoring is actively running."""
        return self.monitoring_active and self.running


class PumpFunTransactionParser:
    """Parser for pump.fun transactions."""
    
    def __init__(self):
        self.BUY_DISCRIMINATOR = bytes([102, 6, 61, 18, 1, 218, 235, 234])
        self.SELL_DISCRIMINATOR = bytes([51, 230, 133, 164, 1, 127, 131, 173])
        self.CREATE_DISCRIMINATOR = bytes([181, 157, 89, 67, 143, 182, 52, 72])


# Global wallet tracker instance
wallet_tracker = None

def initialize_wallet_tracker():
    """Initialize the global wallet tracker instance."""
    global wallet_tracker
    wallet_tracker = EnhancedWalletTracker()
    logger.info("✅ Wallet tracker instance created and ready")
    return wallet_tracker
'''
    
    write_file('src/monitoring/wallet_tracker.py', content)

def fix_logger():
    """Ensure logger writes to file with proper configuration."""
    content = '''"""
Structured logging configuration for the Solana pump.fun sniping bot.
Provides centralized logging with file rotation and console output.
Fixed to ensure log files are created and written properly.
"""

import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
import structlog
from rich.console import Console
from rich.logging import RichHandler
import os

console = Console()


def setup_logging(
    level: str = "DEBUG",
    file_path: str = "logs/bot.log",
    max_file_size_mb: int = 100,
    backup_count: int = 5,
    console_output: bool = True
) -> None:
    """
    Setup structured logging with file rotation and optional console output.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        file_path: Path to log file
        max_file_size_mb: Maximum size of log file in MB before rotation
        backup_count: Number of backup files to keep
        console_output: Whether to output logs to console
    """
    
    # Create logs directory if it doesn't exist
    log_file = Path(file_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Ensure the log file exists
    if not log_file.exists():
        log_file.touch()
        print(f"Created log file: {log_file}")
    
    # Configure structlog processors
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    shared_processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Configure structlog
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
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
    
    # Use ProcessorFormatter for file output
    file_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=False),
        ],
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler with Rich formatting
    if console_output:
        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True
        )
        console_handler.setLevel(getattr(logging, level.upper()))
        
        # Use ProcessorFormatter for console output
        console_formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # Set up Python logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
        handlers=[]  # We've already added handlers above
    )
    
    # Ensure file handler is working
    root_logger.info(f"Logging initialized - Level: {level}, File: {file_path}")
    print(f"✓ Logging initialized - Level: {level}, File: {file_path}")


class BotLogger:
    """Enhanced logger for bot-specific functionality."""
    
    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)
        self._trade_count = 0
        self._error_count = 0
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self._error_count += 1
        self.logger.error(message, error_count=self._error_count, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self.logger.debug(message, **kwargs)
    
    def trade_executed(self, action: str, token: str, amount: float, price: float, **kwargs):
        """Log trade execution with structured data."""
        self._trade_count += 1
        self.logger.info(
            f"Trade executed: {action}",
            action=action,
            token=token,
            amount=amount,
            price=price,
            trade_number=self._trade_count,
            **kwargs
        )
    
    def position_update(self, token: str, entry_price: float, current_price: float, 
                       gain_percent: float, time_held: float, **kwargs):
        """Log position updates with performance metrics."""
        self.logger.info(
            f"Position update: {token[:8]}...",
            token=token,
            entry_price=entry_price,
            current_price=current_price,
            gain_percent=gain_percent,
            time_held_seconds=time_held,
            **kwargs
        )
    
    def strategy_triggered(self, rule_name: str, token: str, conditions: dict, **kwargs):
        """Log when a selling strategy rule is triggered."""
        self.logger.info(
            f"Strategy triggered: {rule_name}",
            rule_name=rule_name,
            token=token,
            conditions=conditions,
            **kwargs
        )
    
    def performance_summary(self, total_trades: int, successful_trades: int, 
                          total_pnl: float, avg_hold_time: float, **kwargs):
        """Log performance summary statistics."""
        success_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0
        self.logger.info(
            "Performance Summary",
            total_trades=total_trades,
            successful_trades=successful_trades,
            success_rate_percent=round(success_rate, 2),
            total_pnl_sol=total_pnl,
            avg_hold_time_seconds=avg_hold_time,
            **kwargs
        )
    
    def connection_status(self, service: str, status: str, **kwargs):
        """Log connection status for various services."""
        self.logger.info(
            f"Connection {status}: {service}",
            service=service,
            status=status,
            **kwargs
        )
    
    def token_detected(self, token: str, market_cap: float, liquidity: float, **kwargs):
        """Log new token detection."""
        self.logger.info(
            f"New token detected: {token[:8]}...",
            token=token,
            market_cap=market_cap,
            liquidity=liquidity,
            **kwargs
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

def create_test_script():
    """Create a test script to verify the fixes."""
    content = '''#!/usr/bin/env python3
"""
Test script to verify wallet tracking is working
Run after applying the patch to check if issues are resolved
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_wallet_tracking():
    print("🧪 Testing Wallet Tracking...")
    print("="*60)
    
    # Setup logging first
    from src.utils.logger import setup_logging
    
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    setup_logging(
        level="DEBUG",
        file_path="logs/test_wallet.log",
        console_output=True
    )
    
    # Load config
    from src.utils.config import config_manager
    config_manager.load_all()
    
    # Initialize connection manager
    from src.core.connection_manager import connection_manager
    await connection_manager.initialize()
    
    # Initialize wallet tracker
    from src.monitoring.wallet_tracker import initialize_wallet_tracker
    wallet_tracker = initialize_wallet_tracker()
    
    print("✓ Wallet tracker initialized")
    print(f"✓ Tracking wallets: {list(wallet_tracker.tracked_wallets)}")
    
    # Start tracking
    await wallet_tracker.start()
    print("✓ Wallet tracking started")
    
    # Run for 30 seconds
    print("\\n⏰ Running for 30 seconds to check for transactions...")
    print("Check logs/test_wallet.log for detailed output")
    
    await asyncio.sleep(30)
    
    # Get stats
    stats = wallet_tracker.get_stats()
    print("\\n📊 Statistics:")
    print(f"  Checks performed: {stats['checks_performed']}")
    print(f"  Transactions detected: {stats['transactions_detected']}")
    print(f"  Buys detected: {stats['buys_detected']}")
    print(f"  Errors: {stats['errors']}")
    
    # Stop
    await wallet_tracker.stop()
    await connection_manager.close()
    
    print("\\n✅ Test complete!")
    print(f"Check the log file at: {Path('logs/test_wallet.log').absolute()}")

if __name__ == "__main__":
    asyncio.run(test_wallet_tracking())
'''
    
    write_file('test_wallet_tracking.py', content)

def main():
    """Run all fixes."""
    print("="*60)
    print("🔧 Solana Pump Bot - Complete Fix Patch")
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
    
    # Apply fixes
    print("Applying fixes...")
    print()
    
    try:
        # Backup and fix files
        fix_main_py()
        fix_wallet_tracker()
        fix_logger()
        create_test_script()
        
        print()
        print("="*60)
        print("✅ All fixes applied successfully!")
        print("="*60)
        print()
        print("📋 Summary of changes:")
        print("1. ✓ Fixed logging initialization in main.py")
        print("2. ✓ Enhanced wallet_tracker.py with detailed logging")
        print("3. ✓ Fixed logger.py to ensure file writing works")
        print("4. ✓ Created test_wallet_tracking.py for verification")
        print()
        print("🚀 Next steps:")
        print("1. Run the bot: python -m src.main")
        print("2. Check the log file: logs/pump_bot.log")
        print("3. Or run the test: python test_wallet_tracking.py")
        print()
        print("📊 The wallet tracker will now:")
        print("   - Check for transactions every 1 second")
        print("   - Log all pump.fun transactions detected")
        print("   - Show detailed statistics every 30 seconds")
        print("   - Write all logs to the file properly")
        print()
        print("🔍 Monitor the console and log file for:")
        print("   - 🟢💰 [BUY DETECTED] messages")
        print("   - 🔴💸 [SELL DETECTED] messages") 
        print("   - ✨🚀 [CREATE DETECTED] messages")
        print("   - 📊 [STATS] periodic statistics")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error applying fixes: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
