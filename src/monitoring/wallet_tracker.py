"""
Enhanced wallet tracking for the Solana pump.fun sniping bot.
Monitors specific wallets for transactions and mimics their buying behavior.
Fixed version with verbose logging and proper transaction detection.
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
        logger.info(f"Using WebSocket endpoint: {self.websocket_url}")
        
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
            "last_check": time.time()
        }
        
    async def start(self) -> None:
        """Start tracking specified wallets for transactions."""
        if self.running:
            logger.warning("Wallet tracker already running")
            return
            
        if not self.tracked_wallets:
            logger.info("No wallets specified for tracking")
            return
            
        self.running = True
        self.monitoring_active = True
        logger.info(f"Starting enhanced wallet tracker for {len(self.tracked_wallets)} wallets")
        logger.info(f"Tracked wallets: {list(self.tracked_wallets)}")
        
        # Start monitoring with periodic transaction checks
        for wallet_address in self.tracked_wallets:
            logger.info(f"Starting monitoring task for wallet: {wallet_address}")
            task = asyncio.create_task(self._monitor_wallet_transactions(wallet_address))
            self.websocket_tasks.append(task)
        
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
    
    async def _monitor_wallet_transactions(self, wallet_address: str) -> None:
        """Monitor a wallet's transactions periodically."""
        logger.info(f"Starting transaction monitoring for wallet {wallet_address[:8]}...")
        check_count = 0
        
        while self.running:
            try:
                check_count += 1
                logger.debug(f"Check #{check_count} for wallet {wallet_address[:8]}...")
                await self._check_recent_transactions(wallet_address)
                self.stats["last_check"] = time.time()
                await asyncio.sleep(2)  # Check every 2 seconds
                
            except asyncio.CancelledError:
                logger.info(f"Monitoring cancelled for wallet {wallet_address[:8]}...")
                break
            except Exception as e:
                logger.error(f"Error monitoring wallet {wallet_address[:8]}...: {str(e)}", exc_info=True)
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
            
            logger.debug(f"[RPC] Getting signatures for address: {wallet_address}")
            
            # Get recent signatures
            response = await client.get_signatures_for_address(
                PublicKey.from_string(wallet_address),
                limit=10  # Check last 10 transactions
            )
            
            if not response or not response.value:
                logger.debug(f"No transactions found for wallet {wallet_address[:8]}...")
                return
            
            logger.info(f"[RPC] Found {len(response.value)} transactions for wallet {wallet_address[:8]}...")
            
            for sig_info in response.value:
                signature = str(sig_info.signature)
                
                if signature in self.processed_signatures:
                    continue
                
                logger.debug(f"[RPC] Fetching transaction details for: {signature[:8]}...")
                
                # Fetch transaction details
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
                    logger.debug(f"[RPC] No transaction data for signature: {signature[:8]}...")
                    
        except Exception as e:
            logger.error(f"[RPC] Error checking recent transactions: {str(e)}", exc_info=True)
            self.stats["errors"] += 1
    
    async def _analyze_transaction(self, tx_data: Any, wallet_address: str, signature: str) -> None:
        """Analyze a transaction for pump.fun operations."""
        try:
            # Convert solders object to dict if needed
            if hasattr(tx_data, 'to_json'):
                tx_json = tx_data.to_json()
                tx_data = json.loads(tx_json)
            
            meta = tx_data.get("meta", {})
            if meta.get("err"):
                logger.debug(f"Skipping failed transaction: {signature[:8]}...")
                return  # Skip failed transactions
            
            transaction = tx_data.get("transaction", {})
            message = transaction.get("message", {})
            instructions = message.get("instructions", [])
            logs = meta.get("logMessages", [])
            
            logger.debug(f"[TX] Analyzing transaction {signature[:8]}... with {len(instructions)} instructions")
            
            # Check each instruction
            pump_found = False
            for i, instruction in enumerate(instructions):
                program_id = instruction.get("programId")
                
                # Check if it's a pump.fun instruction
                if program_id == str(self.pump_program_id):
                    pump_found = True
                    self.processed_signatures.add(signature)
                    logger.info(f"🎯 [PUMP.FUN] Found pump.fun transaction: {signature[:8]}...")
                    logger.info(f"[PUMP.FUN] Instruction #{i+1} - Program: {program_id}")
                    self.stats["transactions_detected"] += 1
                    
                    # Parse the instruction
                    tx_info = await self._parse_pump_instruction(instruction, logs, wallet_address, signature)
                    if tx_info:
                        await self._process_pump_transaction(tx_info)
            
            if not pump_found:
                logger.debug(f"[TX] No pump.fun instructions in transaction {signature[:8]}...")
                # Mark as processed to avoid checking again
                self.processed_signatures.add(signature)
                        
        except Exception as e:
            logger.error(f"[TX] Error analyzing transaction: {str(e)}", exc_info=True)
            self.stats["errors"] += 1
    
    async def _parse_pump_instruction(self, instruction: Dict, logs: List[str], wallet: str, signature: str) -> Optional[Dict]:
        """Parse pump.fun instruction to determine operation type."""
        try:
            logger.debug(f"[PARSE] Parsing pump.fun instruction for signature {signature[:8]}...")
            
            # Get instruction data
            data = instruction.get("data")
            if not data:
                logger.debug("[PARSE] No instruction data found")
                return None
            
            operation = "unknown"
            token = "unknown"
            amount_sol = 0.0
            
            # Log the raw data for debugging
            logger.debug(f"[PARSE] Raw instruction data: {data[:50]}..." if len(str(data)) > 50 else f"[PARSE] Raw instruction data: {data}")
            
            # Try to decode base58 data
            try:
                if isinstance(data, str):
                    decoded = base58.b58decode(data)
                    if len(decoded) >= 8:
                        discriminator = decoded[:8]
                        logger.debug(f"[PARSE] Discriminator bytes: {discriminator.hex()}")
                        
                        if discriminator == self.BUY_DISCRIMINATOR:
                            operation = "buy"
                            logger.info("[PARSE] ✅ Detected BUY operation from discriminator")
                        elif discriminator == self.SELL_DISCRIMINATOR:
                            operation = "sell"
                            logger.info("[PARSE] ✅ Detected SELL operation from discriminator")
                        elif discriminator == self.CREATE_DISCRIMINATOR:
                            operation = "create"
                            logger.info("[PARSE] ✅ Detected CREATE operation from discriminator")
            except Exception as e:
                logger.debug(f"[PARSE] Could not decode instruction data: {e}")
            
            # If we couldn't determine from discriminator, check logs
            if operation == "unknown" and logs:
                logger.debug(f"[PARSE] Checking {len(logs)} transaction logs...")
                logs_str = " ".join(logs).lower()
                if "buy" in logs_str or "swap executed" in logs_str:
                    operation = "buy"
                    logger.info("[PARSE] ✅ Detected BUY operation from logs")
                elif "sell" in logs_str:
                    operation = "sell"
                    logger.info("[PARSE] ✅ Detected SELL operation from logs")
                elif "create" in logs_str or "initialize" in logs_str:
                    operation = "create"
                    logger.info("[PARSE] ✅ Detected CREATE operation from logs")
            
            # Try to extract token address from accounts
            accounts = instruction.get("accounts", [])
            logger.debug(f"[PARSE] Instruction has {len(accounts)} accounts")
            if len(accounts) > 2:
                # Usually the token mint is in the accounts
                token = accounts[2] if isinstance(accounts[2], str) else token
                logger.debug(f"[PARSE] Extracted token address: {token[:8]}...")
            
            # Try to extract amount from logs
            for log in logs:
                if "amount:" in log.lower():
                    try:
                        # Extract number after "amount:"
                        parts = log.lower().split("amount:")
                        if len(parts) > 1:
                            amount_str = parts[1].strip().split()[0]
                            amount_sol = float(amount_str) / 1e9  # Convert lamports to SOL
                            logger.debug(f"[PARSE] Extracted amount: {amount_sol} SOL")
                    except:
                        pass
            
            result = {
                "operation": operation,
                "wallet": wallet,
                "signature": signature,
                "token": token,
                "amount_sol": amount_sol
            }
            
            logger.info(f"[PARSE] Final result - Operation: {operation}, Token: {token[:8]}..., Amount: {amount_sol} SOL")
            return result
            
        except Exception as e:
            logger.error(f"[PARSE] Error parsing instruction: {str(e)}", exc_info=True)
            return None
    
    async def _process_pump_transaction(self, tx_info: Dict) -> None:
        """Process a pump.fun transaction."""
        operation = tx_info.get("operation")
        wallet = tx_info.get("wallet")
        token = tx_info.get("token", "unknown")
        amount_sol = tx_info.get("amount_sol", 0)
        signature = tx_info.get("signature")
        
        if operation == "buy":
            self.stats["buys_detected"] += 1
            logger.info(
                f"🟢 [BUY] Wallet {wallet[:8]}... bought token {token[:8]}... "
                f"for {amount_sol:.4f} SOL (tx: {signature[:8]}...)"
            )
            
            # Trigger buy callbacks
            logger.info(f"[CALLBACK] Triggering {len(self.buy_callbacks)} buy callbacks...")
            for i, callback in enumerate(self.buy_callbacks):
                try:
                    logger.debug(f"[CALLBACK] Executing callback #{i+1}")
                    if asyncio.iscoroutinefunction(callback):
                        await callback(wallet, token, amount_sol)
                    else:
                        callback(wallet, token, amount_sol)
                    logger.debug(f"[CALLBACK] Callback #{i+1} executed successfully")
                except Exception as e:
                    logger.error(f"[CALLBACK] Error in buy callback #{i+1}: {str(e)}", exc_info=True)
                    
        elif operation == "sell":
            self.stats["sells_detected"] += 1
            logger.info(
                f"🔴 [SELL] Wallet {wallet[:8]}... sold token {token[:8]}... "
                f"for {amount_sol:.4f} SOL (tx: {signature[:8]}...)"
            )
            
        elif operation == "create":
            self.stats["creates_detected"] += 1
            logger.info(
                f"✨ [CREATE] Wallet {wallet[:8]}... created token {token[:8]}... "
                f"(tx: {signature[:8]}...)"
            )
            
            # Treat create as a buy signal
            logger.info(f"[CALLBACK] Triggering {len(self.buy_callbacks)} buy callbacks for CREATE...")
            for i, callback in enumerate(self.buy_callbacks):
                try:
                    logger.debug(f"[CALLBACK] Executing callback #{i+1} for CREATE")
                    if asyncio.iscoroutinefunction(callback):
                        await callback(wallet, token, 0.1)  # Default amount for creates
                    else:
                        callback(wallet, token, 0.1)
                    logger.debug(f"[CALLBACK] Callback #{i+1} executed successfully")
                except Exception as e:
                    logger.error(f"[CALLBACK] Error in buy callback #{i+1} for create: {str(e)}", exc_info=True)
    
    def register_buy_callback(self, callback: Callable[[str, str, float], None]) -> None:
        """Register a callback for buy transactions."""
        self.buy_callbacks.append(callback)
        logger.info(f"Registered wallet buy callback. Total callbacks: {len(self.buy_callbacks)}")
    
    def add_tracked_wallet(self, wallet_address: str) -> None:
        """Add a wallet to track."""
        if wallet_address not in self.tracked_wallets:
            self.tracked_wallets.add(wallet_address)
            logger.info(f"Added wallet to track: {wallet_address[:8]}...")
            
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
    return wallet_tracker
