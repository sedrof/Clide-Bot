"""
Enhanced wallet tracking with improved timing and detection speed.
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
    Enhanced wallet tracker with faster polling for pump.fun and DEX transactions.
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
        
        # IMPROVED: Faster polling interval (0.5 seconds)
        self.POLL_INTERVAL = 0.2  # Optimized to 200ms for faster detection  # Optimized to 200ms for faster detection
        
        # Statistics
        self.stats = {
            "transactions_detected": 0,
            "buys_detected": 0,
            "sells_detected": 0,
            "dex_swaps_detected": 0,
            "errors": 0,
            "checks_performed": 0,
            "last_check": time.time(),
            "last_detection_time": 0,
            "average_detection_delay": 0,
            "detection_delays": []
        }
        
        logger.info(f"WalletTracker initialized - tracking {len(self.tracked_wallets)} wallet(s)")
        logger.info(f"Polling interval: {self.POLL_INTERVAL}s (200ms) for competitive detection speed")
        
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
        """Monitor a wallet for transactions with fast polling."""
        logger.info(f"Starting fast monitoring for wallet: {wallet_address}")
        
        consecutive_errors = 0
        
        while self.running:
            try:
                await self._check_wallet_transactions(wallet_address)
                self.stats["checks_performed"] += 1
                consecutive_errors = 0  # Reset on success
                await asyncio.sleep(self.POLL_INTERVAL)  # Fast polling
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error monitoring wallet {wallet_address}: {e}")
                self.stats["errors"] += 1
                
                # Exponential backoff on errors
                wait_time = min(self.POLL_INTERVAL * (2 ** consecutive_errors), 10)
                await asyncio.sleep(wait_time)
    
    async def _check_wallet_transactions(self, wallet_address: str) -> None:
        """Check recent transactions for a wallet."""
        try:
            client = await connection_manager.get_rpc_client()
            if not client:
                return
            
            # Get recent signatures (check last 3 for faster detection)
            response = await client.get_signatures_for_address(
                PublicKey.from_string(wallet_address),
                limit=3  # Reduced for faster processing
            )
            
            if not response or not response.value:
                return
            
            # Process new transactions
            for sig_info in response.value:
                signature = str(sig_info.signature)
                
                if signature in self.processed_signatures:
                    continue
                
                # Mark as processed immediately
                self.processed_signatures.add(signature)
                
                # Calculate detection delay
                if sig_info.block_time:
                    detection_delay = time.time() - sig_info.block_time
                    self.stats["detection_delays"].append(detection_delay)
                    # Keep only last 100 delays
                    if len(self.stats["detection_delays"]) > 100:
                        self.stats["detection_delays"].pop(0)
                    self.stats["average_detection_delay"] = sum(self.stats["detection_delays"]) / len(self.stats["detection_delays"])
                    
                    logger.info(f"[TIMING] Transaction detected {detection_delay:.2f}s after block time")
                
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
            self.stats["last_detection_time"] = time.time()
            
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
                    f"TX: {signature[:32]}... | "
                    f"Avg Detection Delay: {self.stats['average_detection_delay']:.2f}s"
                )
                
                # Trigger callbacks immediately
                await self._trigger_buy_callbacks(wallet_address, token_address, amount_sol)
                        
        except Exception as e:
            logger.error(f"Error analyzing transaction: {e}")
            self.stats["errors"] += 1
    
    async def _trigger_buy_callbacks(self, wallet_address: str, token_address: str, amount_sol: float):
        """Trigger buy callbacks asynchronously for speed."""
        for callback in self.buy_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    # Don't await - run in background for speed
                    asyncio.create_task(callback(wallet_address, token_address, amount_sol))
                else:
                    callback(wallet_address, token_address, amount_sol)
            except Exception as e:
                logger.error(f"Error in buy callback: {e}")
    
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
            
            # Parse logs for swap details - improved detection
            logs_str = " ".join(logs).lower()
            
            # Detect buy operations with more patterns
            buy_patterns = [
                "buy", "swap executed", "buyexactin", "buy_exact_in",
                "swap sol for", "swapping sol to", "purchasing"
            ]
            
            if any(pattern in logs_str for pattern in buy_patterns):
                is_buy = True
            
            # Extract amounts from logs
            for log in logs:
                # Look for various amount patterns
                if any(keyword in log.lower() for keyword in ["amount_in:", "input_amount:", "sol_amount:"]):
                    try:
                        # Extract numeric value
                        parts = log.split(":")
                        if len(parts) > 1:
                            amount_str = parts[-1].strip().split()[0].replace(",", "")
                            # Handle both raw lamports and formatted SOL
                            if "." in amount_str:
                                amount_sol = float(amount_str)
                            else:
                                amount_sol = float(amount_str) / 1e9
                    except:
                        pass
            
            # Extract token address from instructions with improved logic
            for instruction in instructions:
                accounts = instruction.get("accounts", [])
                # Check different account positions based on DEX
                if dex_name == "Raydium Launchpad" and len(accounts) >= 6:
                    # For Raydium, token mint is often at position 5
                    potential_token = accounts[5] if isinstance(accounts[5], str) else None
                elif len(accounts) >= 4:
                    # Common pattern: check accounts 2-4 for token mint
                    for idx in [2, 3, 4]:
                        if idx < len(accounts) and isinstance(accounts[idx], str):
                            potential_token = accounts[idx]
                            # Skip SOL mint
                            if potential_token != "So11111111111111111111111111111111111111112":
                                token_address = potential_token
                                break
            
            if is_buy and (amount_sol > 0 or token_address != "Unknown"):
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
            
            avg_delay = self.stats['average_detection_delay']
            logger.info(
                f"📊 STATS | Checks: {self.stats['checks_performed']} | "
                f"TX: {self.stats['transactions_detected']} | "
                f"Buys: {self.stats['buys_detected']} | "
                f"DEX Swaps: {self.stats['dex_swaps_detected']} | "
                f"Errors: {self.stats['errors']} | "
                f"Avg Detection Delay: {avg_delay:.2f}s"
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
