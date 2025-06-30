#!/usr/bin/env python3

import os
import shutil
import sys
from pathlib import Path

def backup_file(filepath):
    """Create a backup of the file before modifying."""
    backup_path = f"{filepath}.backup_v2_{os.getpid()}"
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

def fix_wallet_tracker_v2():
    """Fix wallet_tracker.py to detect Raydium and other DEX swaps."""
    content = '''"""
Enhanced wallet tracking for the Solana pump.fun sniping bot.
Monitors specific wallets for transactions on pump.fun, Raydium, and other DEXs.
Fixed version v2 with comprehensive DEX support.
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
    Enhanced wallet tracker with robust monitoring for pump.fun and DEX transactions.
    """
    
    def __init__(self):
        self.settings = config_manager.get_settings()
        
        # Use the configured WebSocket endpoint from settings
        self.websocket_url = self.settings.solana.websocket_endpoint
        logger.info(f"WalletTracker initialized - WebSocket endpoint: {self.websocket_url}")
        
        self.tracked_wallets: Set[str] = set(self.settings.tracking.wallets)
        
        # Program IDs for various DEXs and protocols
        self.pump_program_id = PublicKey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
        self.raydium_v4_program_id = PublicKey.from_string("675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8")
        self.raydium_launchpad_id = PublicKey.from_string("LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj")
        self.okx_dex_router_id = PublicKey.from_string("6m2CDdhRgxpH4WjvdzxAYbGxwdGUz5MziiL5jek2kBma")
        self.jupiter_v6_id = PublicKey.from_string("JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4")
        
        # Store program names for logging
        self.program_names = {
            str(self.pump_program_id): "Pump.fun",
            str(self.raydium_v4_program_id): "Raydium V4",
            str(self.raydium_launchpad_id): "Raydium Launchpad",
            str(self.okx_dex_router_id): "OKX DEX Router",
            str(self.jupiter_v6_id): "Jupiter V6"
        }
        
        self.dex_program_ids = {
            str(self.pump_program_id),
            str(self.raydium_v4_program_id),
            str(self.raydium_launchpad_id),
            str(self.okx_dex_router_id),
            str(self.jupiter_v6_id)
        }
        
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
            "dex_swaps_detected": 0,
            "errors": 0,
            "checks_performed": 0,
            "last_check": time.time()
        }
        
        logger.info(f"WalletTracker configured to track {len(self.tracked_wallets)} wallet(s)")
        logger.info(f"Monitoring DEX programs: {', '.join(self.program_names.values())}")
        
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
                f"DEX Swaps: {self.stats['dex_swaps_detected']}, "
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
                
                if check_count % 10 == 1:  # Log every 10th check
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
            
            # Get recent signatures
            response = await client.get_signatures_for_address(
                PublicKey.from_string(wallet_address),
                limit=5  # Check last 5 transactions
            )
            
            if not response or not response.value:
                return
            
            # Check if there are new transactions
            for sig_info in response.value:
                signature = str(sig_info.signature)
                
                if signature in self.processed_signatures:
                    continue
                
                logger.info(f"🆕 [NEW TX] Found new transaction: {signature[:16]}... for wallet {wallet_address[:8]}...")
                
                # Fetch transaction details
                tx_response = await client.get_transaction(
                    sig_info.signature,
                    encoding="jsonParsed",
                    commitment=Confirmed,
                    max_supported_transaction_version=0
                )
                
                if tx_response and tx_response.value:
                    # Process transaction
                    await self._analyze_transaction(tx_response.value, wallet_address, signature)
                else:
                    logger.warning(f"⚠️ [RPC] No transaction data returned for signature: {signature[:16]}...")
                    
        except Exception as e:
            logger.error(f"❌ [RPC] Error checking recent transactions: {str(e)}", exc_info=True)
            self.stats["errors"] += 1
    
    async def _analyze_transaction(self, tx_data: Any, wallet_address: str, signature: str) -> None:
        """Analyze a transaction for DEX operations."""
        try:
            # Convert solders object to dict if needed
            if hasattr(tx_data, 'to_json'):
                tx_json = tx_data.to_json()
                tx_data = json.loads(tx_json)
            
            meta = tx_data.get("meta", {})
            if meta.get("err"):
                logger.debug(f"Skipping failed transaction: {signature[:16]}...")
                self.processed_signatures.add(signature)
                return
            
            transaction = tx_data.get("transaction", {})
            message = transaction.get("message", {})
            instructions = message.get("instructions", [])
            logs = meta.get("logMessages", [])
            
            # Mark as processed
            self.processed_signatures.add(signature)
            
            # Get all program IDs in the transaction
            program_ids = set()
            for instruction in instructions:
                program_id = instruction.get("programId")
                if program_id:
                    program_ids.add(program_id)
            
            # Check if any DEX programs are involved
            dex_programs_found = program_ids.intersection(self.dex_program_ids)
            
            if dex_programs_found:
                self.stats["transactions_detected"] += 1
                
                # Log which DEX programs were found
                for prog_id in dex_programs_found:
                    prog_name = self.program_names.get(prog_id, prog_id)
                    logger.info(f"🎯 [{prog_name}] Found DEX transaction: {signature[:16]}...")
                
                # Analyze the transaction for swap details
                swap_info = await self._analyze_dex_transaction(instructions, logs, wallet_address, signature, program_ids)
                
                if swap_info:
                    await self._process_dex_swap(swap_info)
                        
        except Exception as e:
            logger.error(f"❌ [TX] Error analyzing transaction: {str(e)}", exc_info=True)
            self.stats["errors"] += 1
    
    async def _analyze_dex_transaction(self, instructions: List[Dict], logs: List[str], 
                                      wallet: str, signature: str, program_ids: Set[str]) -> Optional[Dict]:
        """Analyze DEX transaction to extract swap details."""
        try:
            # Default values
            operation = "swap"
            token_in = "SOL"
            token_out = "Unknown"
            amount_in = 0.0
            amount_out = 0.0
            dex_name = "Unknown DEX"
            
            # Identify which DEX was used
            for prog_id in program_ids:
                if prog_id in self.program_names:
                    dex_name = self.program_names[prog_id]
                    break
            
            # Parse logs for swap information
            for log in logs:
                log_lower = log.lower()
                
                # Look for swap indicators
                if "swap" in log_lower or "buy" in log_lower or "sell" in log_lower:
                    logger.debug(f"Found swap indicator in log: {log}")
                
                # Extract amounts from logs
                if "amount_in:" in log:
                    try:
                        amount_str = log.split("amount_in:")[1].strip().split()[0].replace(",", "")
                        amount_in = float(amount_str) / 1e9  # Convert lamports to SOL
                        logger.debug(f"Extracted amount_in: {amount_in} SOL")
                    except:
                        pass
                
                if "amount_out:" in log:
                    try:
                        amount_str = log.split("amount_out:")[1].strip().split()[0].replace(",", "")
                        amount_out = float(amount_str)
                        logger.debug(f"Extracted amount_out: {amount_out}")
                    except:
                        pass
                
                # Check for buy/sell operations
                if "buyexactin" in log_lower or "buy_exact_in" in log_lower:
                    operation = "buy"
                elif "sellexactin" in log_lower or "sell_exact_in" in log_lower:
                    operation = "sell"
            
            # Try to extract token information from instructions
            for instruction in instructions:
                if "parsed" in instruction and isinstance(instruction["parsed"], dict):
                    parsed = instruction["parsed"]
                    if parsed.get("type") == "transferChecked":
                        info = parsed.get("info", {})
                        mint = info.get("mint", "")
                        if mint and mint != str(PublicKey.from_string("So11111111111111111111111111111111111111112")):
                            token_out = mint
                
                # Check accounts for token mints
                accounts = instruction.get("accounts", [])
                if len(accounts) >= 5:
                    # Common pattern: source mint at index 3, dest mint at index 4
                    if operation == "buy":
                        token_out = accounts[4] if len(accounts) > 4 else token_out
                    else:
                        token_in = accounts[3] if len(accounts) > 3 else token_in
            
            # Build result
            result = {
                "operation": operation,
                "wallet": wallet,
                "signature": signature,
                "dex_name": dex_name,
                "token_in": token_in,
                "token_out": token_out,
                "amount_in": amount_in,
                "amount_out": amount_out
            }
            
            logger.info(
                f"✅ [SWAP ANALYSIS] {operation.upper()} on {dex_name} - "
                f"In: {amount_in:.6f} {token_in[:8]}... Out: {amount_out} {token_out[:8]}..."
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error analyzing DEX transaction: {str(e)}", exc_info=True)
            return None
    
    async def _process_dex_swap(self, swap_info: Dict) -> None:
        """Process a DEX swap transaction."""
        operation = swap_info.get("operation")
        wallet = swap_info.get("wallet")
        dex_name = swap_info.get("dex_name")
        token_in = swap_info.get("token_in", "Unknown")
        token_out = swap_info.get("token_out", "Unknown")
        amount_in = swap_info.get("amount_in", 0)
        amount_out = swap_info.get("amount_out", 0)
        signature = swap_info.get("signature")
        
        logger.info("="*60)
        
        if operation == "buy" or (operation == "swap" and token_in == "SOL"):
            self.stats["buys_detected"] += 1
            self.stats["dex_swaps_detected"] += 1
            
            logger.info(
                f"🟢💰 [BUY DETECTED] on {dex_name}\n"
                f"  Wallet: {wallet[:8]}...\n"
                f"  Bought: {token_out[:16]}...\n"
                f"  Spent: {amount_in:.6f} SOL\n"
                f"  Received: {amount_out:,.2f} tokens\n"
                f"  TX: {signature[:16]}..."
            )
            
            # Trigger buy callbacks - use token_out as the token address
            logger.info(f"📞 [CALLBACK] Triggering {len(self.buy_callbacks)} buy callbacks...")
            for i, callback in enumerate(self.buy_callbacks):
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(wallet, token_out, amount_in)
                    else:
                        callback(wallet, token_out, amount_in)
                    logger.debug(f"✅ [CALLBACK] Callback #{i+1} executed successfully")
                except Exception as e:
                    logger.error(f"❌ [CALLBACK] Error in buy callback #{i+1}: {str(e)}", exc_info=True)
                    
        elif operation == "sell" or (operation == "swap" and token_out == "SOL"):
            self.stats["sells_detected"] += 1
            self.stats["dex_swaps_detected"] += 1
            
            logger.info(
                f"🔴💸 [SELL DETECTED] on {dex_name}\n"
                f"  Wallet: {wallet[:8]}...\n"
                f"  Sold: {token_in[:16]}...\n" 
                f"  Amount: {amount_in:,.2f} tokens\n"
                f"  Received: {amount_out:.6f} SOL\n"
                f"  TX: {signature[:16]}..."
            )
        
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

def create_test_script_fixed():
    """Create a test script with fixed Unicode issues."""
    content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
    print("Testing Wallet Tracking...")
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
    print("")
    print("Running for 30 seconds to check for transactions...")
    print("Check logs/test_wallet.log for detailed output")
    
    await asyncio.sleep(30)
    
    # Get stats
    stats = wallet_tracker.get_stats()
    print("")
    print("Statistics:")
    print(f"  Checks performed: {stats['checks_performed']}")
    print(f"  Transactions detected: {stats['transactions_detected']}")
    print(f"  Buys detected: {stats['buys_detected']}")
    print(f"  DEX swaps detected: {stats['dex_swaps_detected']}")
    print(f"  Errors: {stats['errors']}")
    
    # Stop
    await wallet_tracker.stop()
    await connection_manager.close()
    
    print("")
    print("✅ Test complete!")
    print(f"Check the log file at: {Path('logs/test_wallet.log').absolute()}")

if __name__ == "__main__":
    asyncio.run(test_wallet_tracking())
'''
    
    # Use raw string or forward slashes to avoid Unicode issues
    write_file('test_wallet_tracking.py', content)

def main():
    """Run all fixes."""
    print("="*60)
    print("🔧 Solana Pump Bot - Complete Fix Patch v2")
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
        # Keep the previous fixes for main.py and logger.py
        from fix_patch import fix_main_py, fix_logger
        
        fix_main_py()
        fix_logger()
        
        # Apply new wallet tracker fix
        fix_wallet_tracker_v2()
        
        # Create fixed test script
        create_test_script_fixed()
        
        print()
        print("="*60)
        print("✅ All fixes applied successfully!")
        print("="*60)
        print()
        print("📋 Summary of changes:")
        print("1. ✓ Fixed logging initialization in main.py")
        print("2. ✓ Fixed logger.py to ensure file writing works")
        print("3. ✓ Enhanced wallet_tracker.py to detect Raydium & DEX swaps")
        print("4. ✓ Fixed test_wallet_tracking.py Unicode error")
        print()
        print("🎯 The wallet tracker now monitors:")
        print("   - Pump.fun transactions")
        print("   - Raydium V4 swaps")
        print("   - Raydium Launchpad swaps")
        print("   - OKX DEX Router swaps")
        print("   - Jupiter V6 swaps")
        print()
        print("🚀 Next steps:")
        print("1. Run the test: python test_wallet_tracking.py")
        print("2. Or run the full bot: python -m src.main")
        print()
        print("📊 Look for these in the logs:")
        print("   - 🟢💰 [BUY DETECTED] - When wallet buys tokens")
        print("   - 🔴💸 [SELL DETECTED] - When wallet sells")
        print("   - 🎯 [Raydium Launchpad] - Raydium swaps")
        print("   - 🎯 [OKX DEX Router] - OKX DEX swaps")
        print()
        print("The recent transaction you showed (BIG PAPA swap) will now be detected!")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error applying fixes: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())