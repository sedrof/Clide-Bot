"""
Enhanced wallet tracking for the Solana pump.fun sniping bot.
Monitors specific wallets for transactions and mimics their buying behavior.
Fixed version with proper WebSocket configuration.
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
        
        # Start WebSocket monitoring for each wallet
        for wallet_address in self.tracked_wallets:
            task = asyncio.create_task(self._monitor_wallet(wallet_address))
            self.websocket_tasks.append(task)
        
    async def stop(self) -> None:
        """Stop tracking wallets."""
        self.running = False
        logger.info("Stopping wallet tracker")
        
        # Cancel all WebSocket tasks
        for task in self.websocket_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.websocket_tasks, return_exceptions=True)
        self.websocket_tasks.clear()
        
        # Close WebSocket if open
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
            self.websocket = None
    
    async def _monitor_wallet(self, wallet_address: str) -> None:
        """Monitor a specific wallet using WebSocket subscriptions."""
        retry_count = 0
        max_retries = 5
        
        while self.running and retry_count < max_retries:
            try:
                logger.info(f"Connecting to WebSocket for wallet {wallet_address[:8]}...")
                
                async with websockets.connect(self.websocket_url) as websocket:
                    self.websocket = websocket
                    logger.info("WebSocket connection established for wallet tracking")
                    
                    # Subscribe to account changes
                    account_sub_id = await self._subscribe_account(websocket, wallet_address)
                    
                    # Disable global logs subscription to prevent spam
                    # Only monitor account changes and fetch transactions on demand
                    logger.info("📌 Note: Global logs subscription disabled to prevent spam")
                    logger.info("📌 Monitoring account changes and fetching transactions on demand")
                    
                    # Process messages
                    await self._process_messages_account_only(websocket, wallet_address)
                    
            except asyncio.CancelledError:
                logger.info(f"Monitoring cancelled for wallet {wallet_address[:8]}...")
                break
            except Exception as e:
                retry_count += 1
                logger.error(
                    f"Error monitoring wallet {wallet_address[:8]}... (attempt {retry_count}/{max_retries}): {str(e)}",
                    exc_info=True
                )
                if retry_count < max_retries:
                    await asyncio.sleep(5 * retry_count)  # Exponential backoff
                else:
                    logger.error(f"Max retries reached for wallet {wallet_address[:8]}...")
    
    async def _subscribe_account(self, websocket, wallet_address: str) -> Optional[int]:
        """Subscribe to account changes for a wallet."""
        try:
            subscribe_msg = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "accountSubscribe",
                "params": [
                    wallet_address,
                    {
                        "encoding": "jsonParsed",
                        "commitment": "confirmed"
                    }
                ]
            }
            
            await websocket.send(json.dumps(subscribe_msg))
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            result = json.loads(response)
            
            if "result" in result:
                sub_id = result["result"]
                self.subscriptions[sub_id] = f"account_{wallet_address}"
                logger.info(f"Subscribed to account {wallet_address[:8]}... with ID: {sub_id}")
                return sub_id
            else:
                logger.error(f"Failed to subscribe to account: {result}")
                return None
                
        except asyncio.TimeoutError:
            logger.error("Timeout waiting for account subscription response")
            return None
        except Exception as e:
            logger.error(f"Error subscribing to account: {str(e)}", exc_info=True)
            return None
    
    async def _process_messages_account_only(self, websocket, wallet_address: str) -> None:
        """Process incoming WebSocket messages - account notifications only."""
        while self.running:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                data = json.loads(message)
                
                # Handle subscription confirmations
                if "id" in data and "result" in data:
                    logger.debug(f"Subscription confirmed: {data}")
                    continue
                
                # Handle account notifications
                method = data.get("method")
                if method == "accountNotification":
                    logger.info(f"Account changed for wallet {wallet_address[:8]}...")
                    await self._handle_account_notification(data, wallet_address)
                    
                    # When account changes, check for new pump.fun transactions
                    await self._check_pump_transactions_for_wallet(wallet_address)
                    
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.ping()
                except:
                    break
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed")
                break
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}", exc_info=True)
    
    async def _handle_account_notification(self, data: Dict, wallet_address: str) -> None:
        """Handle account change notifications."""
        try:
            logger.info(f"Processing update for wallet {wallet_address[:8]}...")
            
            # Extract the value from notification
            params = data.get("params", {})
            result = params.get("result", {})
            
            # When account changes, fetch recent transactions
            await self._check_recent_transactions(wallet_address)
            
        except Exception as e:
            logger.error(f"Error handling account notification: {str(e)}", exc_info=True)
    
    async def _check_recent_transactions(self, wallet_address: str) -> None:
        """Check recent transactions for a wallet."""
        try:
            # FIX: Properly await the async get_rpc_client() call
            client = await connection_manager.get_rpc_client()
            if not client:
                logger.error("No RPC client available")
                return
            
            # Get recent signatures
            response = await client.get_signatures_for_address(
                PublicKey.from_string(wallet_address),
                limit=5
            )
            
            if not response or not response.value:
                return
            
            for sig_info in response.value:
                signature = str(sig_info.signature)
                
                if signature in self.processed_signatures:
                    continue
                
                self.processed_signatures.add(signature)
                
                # Fetch and analyze transaction
                tx_response = await client.get_transaction(
                    sig_info.signature,
                    encoding="jsonParsed",
                    commitment=Confirmed,
                    max_supported_transaction_version=0
                )
                
                if tx_response and tx_response.value:
                    await self._analyze_transaction(tx_response.value, wallet_address, signature)
                    
        except Exception as e:
            logger.error(f"Error checking recent transactions: {str(e)}", exc_info=True)
            self.stats["errors"] += 1
    
    async def _check_pump_transactions_for_wallet(self, wallet_address: str) -> None:
        """Check recent transactions for pump.fun operations when wallet changes."""
        try:
            # FIX: Properly await the async get_rpc_client() call
            client = await connection_manager.get_rpc_client()
            if not client:
                logger.error("No RPC client available")
                return
            
            # Get the last few transactions
            response = await client.get_signatures_for_address(
                PublicKey.from_string(wallet_address),
                limit=3  # Check last 3 transactions
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
                    # Handle solders object - convert to JSON
                    tx_json = tx_response.value.to_json()
                    tx_data = json.loads(tx_json)
                    
                    # Check if it's a pump.fun transaction
                    if self._is_pump_fun_transaction(tx_data):
                        self.processed_signatures.add(signature)
                        logger.info(f"Found pump.fun transaction: {signature[:8]}...")
                        self.stats["transactions_detected"] += 1
                        
                        # Analyze and process the transaction
                        await self._analyze_transaction(tx_data, wallet_address, signature)
                        
        except Exception as e:
            logger.error(f"Error checking pump transactions: {str(e)}", exc_info=True)
            self.stats["errors"] += 1
    
    def _is_pump_fun_transaction(self, tx_data: dict) -> bool:
        """Check if a transaction involves pump.fun program."""
        try:
            transaction = tx_data.get("transaction", {})
            message = transaction.get("message", {})
            instructions = message.get("instructions", [])
            
            pump_program_str = str(self.pump_program_id)
            
            for instruction in instructions:
                if instruction.get("programId") == pump_program_str:
                    return True
                    
            return False
        except:
            return False
    
    async def _analyze_transaction(self, tx_data: Dict, wallet_address: str, signature: str) -> None:
        """Analyze a transaction for pump.fun operations."""
        try:
            # Handle both dictionary and solders object formats
            if hasattr(tx_data, 'to_json'):
                tx_json = tx_data.to_json()
                tx_data = json.loads(tx_json)
            
            meta = tx_data.get("meta", {})
            if meta.get("err"):
                return  # Skip failed transactions
            
            transaction = tx_data.get("transaction", {})
            message = transaction.get("message", {})
            instructions = message.get("instructions", [])
            
            for instruction in instructions:
                # Check if it's a pump.fun instruction
                program_id = instruction.get("programId")
                if program_id == str(self.pump_program_id):
                    # Parse the instruction
                    tx_info = self.parser.parse_instruction(instruction, wallet_address, signature)
                    if tx_info:
                        await self._process_pump_transaction(tx_info)
                        
        except Exception as e:
            logger.error(f"Error analyzing transaction: {str(e)}", exc_info=True)
            self.stats["errors"] += 1
    
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
                f"🟢 BUY detected: Wallet {wallet[:8]}... bought token {token[:8]}... for {amount_sol:.4f} SOL"
            )
            
            # Trigger buy callbacks
            for callback in self.buy_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(wallet, token, amount_sol)
                    else:
                        callback(wallet, token, amount_sol)
                except Exception as e:
                    logger.error(f"Error in buy callback: {str(e)}", exc_info=True)
                    
        elif operation == "sell":
            self.stats["sells_detected"] += 1
            logger.info(
                f"🔴 SELL detected: Wallet {wallet[:8]}... sold token {token[:8]}... for {amount_sol:.4f} SOL"
            )
            
        elif operation == "create":
            self.stats["creates_detected"] += 1
            logger.info(
                f"✨ CREATE detected: Wallet {wallet[:8]}... created token {token[:8]}..."
            )
    
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
                task = asyncio.create_task(self._monitor_wallet(wallet_address))
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
    
    def parse_logs(self, logs: List[str], signature: str) -> Optional[Dict]:
        """Parse pump.fun transaction from logs."""
        try:
            # Look for pump.fun specific logs
            for log in logs:
                if "Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P invoke" in log:
                    # This is a pump.fun transaction
                    result = {"signature": signature}
                    
                    # Look for operation indicators in logs
                    logs_str = " ".join(logs).lower()
                    
                    if "instruction: buy" in logs_str:
                        result["operation"] = "buy"
                    elif "instruction: sell" in logs_str:
                        result["operation"] = "sell"
                    elif "instruction: create" in logs_str or "initialize" in logs_str:
                        result["operation"] = "create"
                    else:
                        # Try to infer from other log patterns
                        if "swap" in logs_str and "sol" in logs_str:
                            # Could be buy or sell, need more context
                            if "transfer" in logs_str and "to" in logs_str:
                                result["operation"] = "buy"
                            else:
                                result["operation"] = "sell"
                        else:
                            result["operation"] = "unknown"
                    
                    return result
                    
            return None
        except Exception as e:
            logger.error(f"Error parsing logs: {str(e)}")
            return None
    
    def parse_instruction(self, instruction: Dict, wallet: str, signature: str) -> Optional[Dict]:
        """Parse pump.fun instruction."""
        try:
            # Get instruction data
            data = instruction.get("data")
            if not data:
                return None
            
            # Try different data formats
            operation = "unknown"
            token = "unknown"
            amount_sol = 0.0
            
            # Check if it's parsed instruction
            parsed = instruction.get("parsed")
            if parsed:
                # Extract info from parsed instruction
                info = parsed.get("info", {})
                inst_type = parsed.get("type", "").lower()
                
                if "transfer" in inst_type or "swap" in inst_type:
                    operation = "buy"  # Simplified - would need more context
                    amount_sol = info.get("lamports", 0) / 1e9 if "lamports" in info else 0
            
            else:
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


# Global wallet tracker instance
wallet_tracker = None

def initialize_wallet_tracker():
    """Initialize the global wallet tracker instance."""
    global wallet_tracker
    wallet_tracker = EnhancedWalletTracker()
    return wallet_tracker