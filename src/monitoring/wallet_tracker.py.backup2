"""
Enhanced wallet tracking for the Solana pump.fun sniping bot.
Monitors specific wallets for transactions and mimics their buying behavior.
Fixed version with proper pump.fun transaction detection.
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
    Enhanced wallet tracker with robust WebSocket monitoring for pump.fun transactions.
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
            "errors": 0
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
        logger.info(f"Starting enhanced wallet tracker for {len(self.tracked_wallets)} wallets")
        
        # Start monitoring with periodic transaction checks
        for wallet_address in self.tracked_wallets:
            task = asyncio.create_task(self._monitor_wallet_transactions(wallet_address))
            self.websocket_tasks.append(task)
        
    async def stop(self) -> None:
        """Stop tracking wallets."""
        self.running = False
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
        
        while self.running:
            try:
                await self._check_recent_transactions(wallet_address)
                await asyncio.sleep(2)  # Check every 2 seconds
                
            except asyncio.CancelledError:
                logger.info(f"Monitoring cancelled for wallet {wallet_address[:8]}...")
                break
            except Exception as e:
                logger.error(f"Error monitoring wallet {wallet_address[:8]}...: {str(e)}")
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
                limit=10  # Check last 10 transactions
            )
            
            if not response or not response.value:
                return
            
            for sig_info in response.value:
                signature = str(sig_info.signature)
                
                if signature in self.processed_signatures:
                    continue
                
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
                    
        except Exception as e:
            logger.error(f"Error checking recent transactions: {str(e)}")
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
                return  # Skip failed transactions
            
            transaction = tx_data.get("transaction", {})
            message = transaction.get("message", {})
            instructions = message.get("instructions", [])
            logs = meta.get("logMessages", [])
            
            # Check each instruction
            for instruction in instructions:
                program_id = instruction.get("programId")
                
                # Check if it's a pump.fun instruction
                if program_id == str(self.pump_program_id):
                    self.processed_signatures.add(signature)
                    logger.info(f"Found pump.fun transaction: {signature[:8]}...")
                    self.stats["transactions_detected"] += 1
                    
                    # Parse the instruction
                    tx_info = await self._parse_pump_instruction(instruction, logs, wallet_address, signature)
                    if tx_info:
                        await self._process_pump_transaction(tx_info)
                        
        except Exception as e:
            logger.error(f"Error analyzing transaction: {str(e)}")
            self.stats["errors"] += 1
    
    async def _parse_pump_instruction(self, instruction: Dict, logs: List[str], wallet: str, signature: str) -> Optional[Dict]:
        """Parse pump.fun instruction to determine operation type."""
        try:
            # Get instruction data
            data = instruction.get("data")
            if not data:
                return None
            
            operation = "unknown"
            token = "unknown"
            amount_sol = 0.0
            
            # Try to decode base58 data
            try:
                if isinstance(data, str):
                    decoded = base58.b58decode(data)
                    if len(decoded) >= 8:
                        discriminator = decoded[:8]
                        
                        if discriminator == self.BUY_DISCRIMINATOR:
                            operation = "buy"
                        elif discriminator == self.SELL_DISCRIMINATOR:
                            operation = "sell"
                        elif discriminator == self.CREATE_DISCRIMINATOR:
                            operation = "create"
            except:
                pass
            
            # If we couldn't determine from discriminator, check logs
            if operation == "unknown" and logs:
                logs_str = " ".join(logs).lower()
                if "buy" in logs_str or "swap executed" in logs_str:
                    operation = "buy"
                elif "sell" in logs_str:
                    operation = "sell"
                elif "create" in logs_str or "initialize" in logs_str:
                    operation = "create"
            
            # Try to extract token address from accounts
            accounts = instruction.get("accounts", [])
            if len(accounts) > 2:
                # Usually the token mint is in the accounts
                token = accounts[2] if isinstance(accounts[2], str) else token
            
            # Try to extract amount from logs
            for log in logs:
                if "amount:" in log.lower():
                    try:
                        # Extract number after "amount:"
                        parts = log.lower().split("amount:")
                        if len(parts) > 1:
                            amount_str = parts[1].strip().split()[0]
                            amount_sol = float(amount_str) / 1e9  # Convert lamports to SOL
                    except:
                        pass
            
            return {
                "operation": operation,
                "wallet": wallet,
                "signature": signature,
                "token": token,
                "amount_sol": amount_sol
            }
            
        except Exception as e:
            logger.error(f"Error parsing instruction: {str(e)}")
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
                f"🟢 BUY detected: Wallet {wallet[:8]}... bought token {token[:8]}... "
                f"for {amount_sol:.4f} SOL (tx: {signature[:8]}...)"
            )
            
            # Trigger buy callbacks
            for callback in self.buy_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(wallet, token, amount_sol)
                    else:
                        callback(wallet, token, amount_sol)
                except Exception as e:
                    logger.error(f"Error in buy callback: {str(e)}")
                    
        elif operation == "sell":
            self.stats["sells_detected"] += 1
            logger.info(
                f"🔴 SELL detected: Wallet {wallet[:8]}... sold token {token[:8]}... "
                f"for {amount_sol:.4f} SOL (tx: {signature[:8]}...)"
            )
            
        elif operation == "create":
            self.stats["creates_detected"] += 1
            logger.info(
                f"✨ CREATE detected: Wallet {wallet[:8]}... created token {token[:8]}... "
                f"(tx: {signature[:8]}...)"
            )
            
            # Treat create as a buy signal
            for callback in self.buy_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(wallet, token, 0.1)  # Default amount for creates
                    else:
                        callback(wallet, token, 0.1)
                except Exception as e:
                    logger.error(f"Error in buy callback for create: {str(e)}")
    
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
        return self.stats.copy()


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