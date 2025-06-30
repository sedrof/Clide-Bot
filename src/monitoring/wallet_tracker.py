"""
Wallet tracking for the Solana pump.fun sniping bot.
Monitors specific wallets for transactions and mimics their buying behavior.
"""
# File Location: src/monitoring/wallet_tracker.py

import asyncio
from typing import Dict, Any, Optional, Callable, List, Set
import json
from datetime import datetime
from solders.pubkey import Pubkey as PublicKey
from solana.rpc.websocket_api import connect as ws_connect
from solders.pubkey import Pubkey
import websockets
import base58
import struct

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.core.connection_manager import connection_manager
from src.core.wallet_manager import wallet_manager
from src.core.transaction_builder import transaction_builder
from src.trading.strategy_engine import strategy_engine
from src.monitoring.pump_monitor import TokenInfo

logger = get_logger("wallet_tracker")


class WalletTransaction:
    """Stores information about a wallet transaction."""
    
    def __init__(self, data: Dict[str, Any], signature: str, timestamp: float):
        self.signature: str = signature
        self.timestamp: float = timestamp
        self.token_address: Optional[str] = None
        self.amount_sol: float = 0.0
        self.is_buy: bool = False
        self.is_sell: bool = False
        self.is_create: bool = False
        
        # Extract relevant information from transaction data
        self._parse_transaction_data(data)
    
    def _parse_transaction_data(self, data: Dict[str, Any]) -> None:
        """Parse transaction data to extract token address and amount."""
        try:
            # Log the full transaction data for debugging
            logger.debug(f"Parsing transaction data for signature {self.signature[:8]}...: {json.dumps(data, indent=2)[:1000]}... (truncated)")
            # Check if it's a pump.fun transaction
            PUMP_FUN_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
            BUY_DISCRIMINATOR = bytes([102, 6, 61, 18, 1, 218, 235, 234])
            SELL_DISCRIMINATOR = bytes([51, 230, 133, 164, 1, 127, 131, 173])
            
            instructions = data.get("transaction", {}).get("message", {}).get("instructions", [])
            logs = data.get("meta", {}).get("logMessages", [])
            
            if not instructions and not logs:
                logger.info(f"No instructions or logs found in transaction data for {self.signature[:8]}...")
                return
                
            logger.info(f"Found {len(instructions)} instructions and {len(logs)} log messages for transaction {self.signature[:8]}...")
            
            # Check for pump.fun program ID in instructions
            for instruction in instructions:
                program_id = instruction.get("programId", "")
                if program_id == PUMP_FUN_PROGRAM_ID:
                    data_str = instruction.get("data", "")
                    if data_str:
                        try:
                            data_bytes = base58.b58decode(data_str)
                            discriminator = data_bytes[:8]
                            if discriminator == BUY_DISCRIMINATOR:
                                self.is_buy = True
                                logger.info(f"Buy transaction detected for {self.signature[:8]}... with pump.fun program")
                                # Extract token address and SOL amount
                                accounts = instruction.get("accounts", [])
                                if len(accounts) > 2:
                                    self.token_address = accounts[2]
                                    logger.info(f"Token address extracted for buy {self.signature[:8]}...: {self.token_address[:8]}...")
                                if len(data_bytes) >= 24:
                                    max_sol_cost = struct.unpack('<Q', data_bytes[16:24])[0]
                                    self.amount_sol = max_sol_cost / 1e9  # Convert lamports to SOL
                                    logger.info(f"SOL amount extracted for buy {self.signature[:8]}...: {self.amount_sol}")
                                break
                            elif discriminator == SELL_DISCRIMINATOR:
                                self.is_sell = True
                                logger.info(f"Sell transaction detected for {self.signature[:8]}... with pump.fun program")
                                accounts = instruction.get("accounts", [])
                                if len(accounts) > 2:
                                    self.token_address = accounts[2]
                                    logger.info(f"Token address extracted for sell {self.signature[:8]}...: {self.token_address[:8]}...")
                                break
                        except Exception as e:
                            logger.error(f"Error decoding instruction data for {self.signature[:8]}...: {e}")
            
            # Check logs for create instruction if not already categorized
            if not self.is_buy and not self.is_sell:
                for i, log in enumerate(logs):
                    logger.debug(f"Log {i} for {self.signature[:8]}...: {log}")
                    if "Program log: Instruction: Create" in log:
                        self.is_create = True
                        logger.info(f"Create transaction detected for {self.signature[:8]}...")
                        break
                    elif "buy" in log.lower() or "swap" in log.lower():
                        self.is_buy = True
                        logger.info(f"Buy/Swap keyword found in log for transaction {self.signature[:8]}...: {log[:100]}...")
                        # Extract token address (placeholder logic)
                        parts = log.split()
                        for part in parts:
                            if len(part) == 44:  # Typical length of Solana address
                                self.token_address = part
                                logger.info(f"Token address extracted for {self.signature[:8]}...: {part[:8]}...")
                                break
                        # Extract SOL amount (placeholder logic)
                        for part in parts:
                            if "SOL" in part:
                                try:
                                    self.amount_sol = float(part.split("SOL")[0])
                                    logger.info(f"SOL amount extracted for {self.signature[:8]}...: {self.amount_sol}")
                                except ValueError:
                                    logger.info(f"Could not parse SOL amount from {part} for {self.signature[:8]}...")
                                    pass
                        break
            
            if not self.is_buy and not self.is_sell and not self.is_create:
                logger.info(f"No buy/sell/create keywords or discriminators found for transaction {self.signature[:8]}...")
        except Exception as e:
            logger.error(f"Error parsing transaction data for {self.signature[:8]}...: {e}")


class EnhancedWalletTracker:
    """Tracks transactions of specified wallets to mimic their buying behavior with enhanced WebSocket subscriptions."""
    
    def __init__(self):
        self.settings = config_manager.get_settings()
        self.websocket_url = self.settings.connection.websocket_url if hasattr(self.settings.connection, 'websocket_url') else "wss://api.mainnet-beta.solana.com"
        self.tracked_wallets: Set[str] = set(self.settings.tracking.wallets)
        self.pump_program_id = PublicKey("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
        self.subscriptions: Dict[int, str] = {}
        self.transaction_cache: Set[str] = set()  # Prevent duplicate processing
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running: bool = False
        self.buy_callbacks: List[Callable[[str, str, float], None]] = []
        self.processed_signatures: Set[str] = set()
        
        # Instruction discriminators for pump.fun
        self.BUY_DISCRIMINATOR = bytes([102, 6, 61, 18, 1, 218, 235, 234])
        self.SELL_DISCRIMINATOR = bytes([51, 230, 133, 164, 1, 127, 131, 173])
        
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
        
        # Connect to Solana WebSocket for wallet tracking
        await self._connect_and_subscribe()
        
    async def stop(self) -> None:
        """Stop tracking wallets."""
        self.running = False
        logger.info("Stopping wallet tracker")
        
        # Unsubscribe from all subscriptions
        for subscription_id in list(self.subscriptions.keys()):
            try:
                await connection_manager.unsubscribe(subscription_id)
                del self.subscriptions[subscription_id]
            except Exception as e:
                logger.error(f"Error unsubscribing from subscription {subscription_id}: {e}")
        
        # Close WebSocket connection if open
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
            self.websocket = None
    
    async def _connect_and_subscribe(self) -> None:
        """Connect to Solana WebSocket and subscribe to wallet transactions and program logs."""
        try:
            # Connect to Solana WebSocket
            self.websocket = await connection_manager.connect_websocket()
            if not self.websocket:
                raise ValueError("Failed to connect to Solana WebSocket")
            
            logger.info("WebSocket connection established for wallet tracking")
            
            # Subscribe to each wallet and pump.fun program logs
            for wallet_address in self.tracked_wallets:
                try:
                    # Define callbacks for this wallet
                    callbacks = {
                        'on_wallet_update': lambda data: asyncio.create_task(self._handle_wallet_update(wallet_address, data)),
                        'on_pump_transaction': lambda data: asyncio.create_task(self._handle_pump_transaction(wallet_address, data)),
                        'on_new_signature': lambda sig: asyncio.create_task(self._handle_new_signature(wallet_address, sig))
                    }
                    
                    # Subscribe to wallet and program logs
                    asyncio.create_task(self._subscribe_to_wallet_and_program(wallet_address, callbacks))
                except Exception as e:
                    logger.error(f"Failed to subscribe to wallet {wallet_address[:8]}...: {e}")
            
            # Start a task to log WebSocket status periodically
            asyncio.create_task(self._log_websocket_status())
            
        except Exception as e:
            logger.error(f"Error connecting to Solana WebSocket for wallet tracking: {e}")
            if self.running:
                logger.info("Reconnecting to Solana WebSocket for wallet tracking...")
                await asyncio.sleep(5)
                await self._connect_and_subscribe()
    
    async def _log_websocket_status(self):
        """Periodically log the status of the WebSocket connection."""
        while self.running and self.websocket:
            if self.websocket.closed:
                logger.warning("WebSocket connection for wallet tracking is closed")
                break
            else:
                logger.debug("WebSocket connection for wallet tracking is active")
            await asyncio.sleep(10)
    
    async def _subscribe_to_wallet_and_program(self, wallet_address: str, callbacks: Dict[str, Callable]) -> None:
        """
        Subscribe to both wallet account changes AND pump.fun program logs.
        This dual subscription ensures we catch all relevant transactions.
        """
        try:
            async with ws_connect(self.websocket_url) as websocket:
                # 1. Subscribe to wallet account changes
                wallet_sub_id = await self._subscribe_to_account(
                    websocket, 
                    wallet_address,
                    callbacks.get('on_wallet_update')
                )
                
                # 2. Subscribe to pump.fun program logs
                logs_sub_id = await self._subscribe_to_program_logs(
                    websocket,
                    callbacks.get('on_pump_transaction')
                )
                
                # 3. Subscribe to specific wallet signatures
                signature_sub_id = await self._subscribe_to_wallet_signatures(
                    websocket,
                    wallet_address,
                    callbacks.get('on_new_signature')
                )
                
                # Keep connection alive and process messages
                await self._process_websocket_messages(websocket, callbacks)
        except Exception as e:
            logger.error(f"Error in subscription for wallet {wallet_address[:8]}...: {e}")
            if self.running:
                await asyncio.sleep(5)
                await self._subscribe_to_wallet_and_program(wallet_address, callbacks)
    
    async def _subscribe_to_account(self, websocket, address: str, callback: Callable) -> int:
        """
        Subscribe to account changes - catches balance updates and token account changes.
        """
        subscribe_message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "accountSubscribe",
            "params": [
                address,
                {
                    "encoding": "jsonParsed",
                    "commitment": "confirmed"
                }
            ]
        }
        
        await websocket.send(json.dumps(subscribe_message))
        response = await websocket.recv()
        result = json.loads(response)
        
        subscription_id = result.get('result')
        self.subscriptions[subscription_id] = f"account_{address}"
        
        logger.info(f"Subscribed to account {address[:8]}... with ID: {subscription_id}")
        return subscription_id
    
    async def _subscribe_to_program_logs(self, websocket, callback: Callable) -> int:
        """
        Subscribe to pump.fun program logs - this catches ALL pump.fun transactions
        including those from tracked wallets.
        """
        subscribe_message = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "logsSubscribe",
            "params": [
                {
                    "mentions": [str(self.pump_program_id)]
                },
                {
                    "commitment": "confirmed"
                }
            ]
        }
        
        await websocket.send(json.dumps(subscribe_message))
        response = await websocket.recv()
        result = json.loads(response)
        
        subscription_id = result.get('result')
        self.subscriptions[subscription_id] = "pump_program_logs"
        
        logger.info(f"Subscribed to pump.fun program logs with ID: {subscription_id}")
        return subscription_id
    
    async def _subscribe_to_wallet_signatures(self, websocket, wallet_address: str, callback: Callable) -> Optional[int]:
        """
        Subscribe to new signatures for a specific wallet.
        This provides real-time transaction notifications.
        """
        subscribe_message = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "signatureSubscribe",
            "params": [
                wallet_address,
                {
                    "commitment": "confirmed",
                    "enableReceivedNotification": False
                }
            ]
        }
        
        # Note: signatureSubscribe might not be available on all RPC providers
        # Use accountSubscribe as primary method
        try:
            await websocket.send(json.dumps(subscribe_message))
            response = await websocket.recv()
            result = json.loads(response)
            subscription_id = result.get('result', None)
            if subscription_id:
                self.subscriptions[subscription_id] = f"signature_{wallet_address}"
                logger.info(f"Subscribed to signatures for wallet {wallet_address[:8]}... with ID: {subscription_id}")
            else:
                logger.warning("Signature subscription not available, relying on account and logs subscriptions")
            return subscription_id
        except Exception as e:
            logger.warning(f"Signature subscription not available for {wallet_address[:8]}...: {e}")
            return None
    
    async def _process_websocket_messages(self, websocket, callbacks):
        """
        Main message processing loop with proper error handling.
        """
        while self.running:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                
                # Handle subscription confirmations
                if 'id' in data and 'result' in data:
                    logger.info(f"Subscription confirmed: {data}")
                    continue
                    
                # Handle notifications
                if data.get('method') == 'accountNotification':
                    await self._handle_account_notification(data, callbacks)
                    
                elif data.get('method') == 'logsNotification':
                    await self._handle_logs_notification(data, callbacks)
                    
                elif data.get('method') == 'signatureNotification':
                    await self._handle_signature_notification(data, callbacks)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                await asyncio.sleep(1)
    
    async def _handle_account_notification(self, data: Dict, callbacks):
        """Process account notification for wallet updates."""
        params = data.get('params', {})
        result = params.get('result', {})
        logger.info(f"Account notification received: {result}")
        if callbacks.get('on_wallet_update'):
            await callbacks['on_wallet_update'](result)
    
    async def _handle_logs_notification(self, data: Dict, callbacks):
        """
        Process logs notification - this is where pump.fun transactions are detected.
        """
        params = data.get('params', {})
        result = params.get('result', {})
        
        # Extract log data
        log_data = {
            'signature': result.get('value', {}).get('signature'),
            'logs': result.get('value', {}).get('logs', []),
            'err': result.get('value', {}).get('err'),
            'slot': result.get('context', {}).get('slot')
        }
        
        # Check if signature is already processed
        if log_data['signature'] in self.transaction_cache:
            return
            
        self.transaction_cache.add(log_data['signature'])
        
        # Trigger callback
        if callbacks.get('on_pump_transaction'):
            await callbacks['on_pump_transaction'](log_data)
    
    async def _handle_signature_notification(self, data: Dict, callbacks):
        """Process signature notification for new transactions."""
        params = data.get('params', {})
        result = params.get('result', {})
        signature = result.get('value', {}).get('signature')
        logger.info(f"New signature notification: {signature[:8]}...")
        if callbacks.get('on_new_signature'):
            await callbacks['on_new_signature'](signature)
    
    async def _handle_wallet_update(self, wallet_address: str, data: Any) -> None:
        """
        Process updates for a tracked wallet with immediate transaction fetching.
        """
        try:
            logger.info(f"Processing update for wallet {wallet_address[:8]}...")
            # Log the raw data for debugging
            logger.debug(f"Raw update data for wallet {wallet_address[:8]}...: {data}")
            
            # Handle different data formats
            if isinstance(data, list):
                logger.debug(f"Received list data for wallet {wallet_address[:8]}..., cannot process directly")
                return
            elif not isinstance(data, dict):
                logger.error(f"Unexpected data type for wallet update: {type(data)}")
                return
            
            # Fetch recent signatures immediately upon account change
            signatures = await connection_manager.get_signatures_for_address(wallet_address, limit=1)
            if not signatures:
                logger.info(f"No new signatures in update for {wallet_address[:8]}...")
                return
            
            latest_signature = signatures[0].signature
            if latest_signature in self.processed_signatures:
                logger.debug(f"Signature {latest_signature[:8]}... already processed for {wallet_address[:8]}...")
                return
            
            self.processed_signatures.add(latest_signature)
            logger.info(f"Fetching transaction for new signature {latest_signature[:8]}... for wallet {wallet_address[:8]}...")
            
            transaction_data = await connection_manager.get_transaction(latest_signature)
            if not transaction_data:
                logger.error(f"Failed to fetch transaction data for {latest_signature[:8]}...")
                return
            
            import time
            timestamp = time.time()
            transaction = WalletTransaction(transaction_data, latest_signature, timestamp)
            
            if transaction.is_buy and transaction.token_address:
                logger.info(
                    f"Buy transaction detected for wallet {wallet_address[:8]}...: {transaction.token_address[:8]}...",
                    amount_sol=transaction.amount_sol
                )
                
                # Notify callbacks about buy transaction
                for callback in self.buy_callbacks:
                    try:
                        callback(wallet_address, transaction.token_address, transaction.amount_sol)
                    except Exception as e:
                        logger.error(f"Error in buy callback for wallet {wallet_address[:8]}...: {e}")
                
                # Mimic the buy behavior
                asyncio.create_task(self._mimic_buy(wallet_address, transaction.token_address, transaction.amount_sol))
            elif transaction.is_sell and transaction.token_address:
                logger.info(
                    f"Sell transaction detected for wallet {wallet_address[:8]}...: {transaction.token_address[:8]}..."
                )
            elif transaction.is_create:
                logger.info(
                    f"Create transaction detected for wallet {wallet_address[:8]}..."
                )
            else:
                logger.info(f"No buy/sell/create transaction detected for {wallet_address[:8]}... in update with signature {latest_signature[:8]}...")
            
        except Exception as e:
            logger.error(f"Error processing wallet update for {wallet_address[:8]}...: {e}")
    
    async def _handle_pump_transaction(self, wallet_address: str, log_data: Dict) -> None:
        """
        Handle pump.fun transaction from logs.
        This is where most detections will come from.
        """
        try:
            # Parse transaction from logs using the parser
            parser = PumpFunTransactionParser()
            parsed = parser.parse_transaction_from_logs(log_data)
            
            if not parsed:
                return
                
            # Enrich with wallet info
            parsed['tracked_wallet'] = wallet_address
            
            # Route to appropriate action based on type
            if parsed['type'] == 'buy':
                logger.info(f"🟢 BUY detected from wallet {wallet_address[:8]}... - {parsed['signature'][:8]}...")
                # Extract token address and amount if available, otherwise fetch full details
                if 'mint' in parsed and 'max_sol_cost_ui' in parsed:
                    token_address = parsed['mint']
                    amount_sol = parsed['max_sol_cost_ui']
                    for callback in self.buy_callbacks:
                        try:
                            callback(wallet_address, token_address, amount_sol)
                        except Exception as e:
                            logger.error(f"Error in buy callback for wallet {wallet_address[:8]}...: {e}")
                    asyncio.create_task(self._mimic_buy(wallet_address, token_address, amount_sol))
            elif parsed['type'] == 'sell':
                logger.info(f"🔴 SELL detected from wallet {wallet_address[:8]}... - {parsed['signature'][:8]}...")
            elif parsed['type'] == 'create':
                logger.info(f"🚀 TOKEN CREATE detected from wallet {wallet_address[:8]}... - {parsed['signature'][:8]}...")
                
        except Exception as e:
            logger.error(f"Error handling pump transaction for wallet {wallet_address[:8]}...: {e}")
    
    async def _handle_new_signature(self, wallet_address: str, signature: str) -> None:
        """Handle new signature notification for a wallet."""
        try:
            logger.info(f"New signature for wallet {wallet_address[:8]}...: {signature[:8]}...")
            if signature in self.processed_signatures:
                logger.debug(f"Signature {signature[:8]}... already processed for {wallet_address[:8]}...")
                return
                
            self.processed_signatures.add(signature)
            transaction_data = await connection_manager.get_transaction(signature)
            if not transaction_data:
                logger.error(f"Failed to fetch transaction data for {signature[:8]}...")
                return
                
            import time
            timestamp = time.time()
            transaction = WalletTransaction(transaction_data, signature, timestamp)
            
            if transaction.is_buy and transaction.token_address:
                logger.info(
                    f"Buy transaction detected for wallet {wallet_address[:8]}...: {transaction.token_address[:8]}...",
                    amount_sol=transaction.amount_sol
                )
                
                for callback in self.buy_callbacks:
                    try:
                        callback(wallet_address, transaction.token_address, transaction.amount_sol)
                    except Exception as e:
                        logger.error(f"Error in buy callback for wallet {wallet_address[:8]}...: {e}")
                
                asyncio.create_task(self._mimic_buy(wallet_address, transaction.token_address, transaction.amount_sol))
            elif transaction.is_sell and transaction.token_address:
                logger.info(
                    f"Sell transaction detected for wallet {wallet_address[:8]}...: {transaction.token_address[:8]}..."
                )
            elif transaction.is_create:
                logger.info(
                    f"Create transaction detected for wallet {wallet_address[:8]}..."
                )
        except Exception as e:
            logger.error(f"Error handling new signature for wallet {wallet_address[:8]}...: {e}")
    
    async def _mimic_buy(self, wallet_address: str, token_address: str, amount_sol: float) -> None:
        """
        Mimic buy behavior of tracked wallet.
        
        Args:
            wallet_address: Wallet that made the purchase
            token_address: Token that was bought
            amount_sol: Amount in SOL that was spent
        """
        try:
            # Check if we have capacity to buy
            if len(strategy_engine.active_positions) >= strategy_engine.max_positions:
                logger.warning(
                    f"Cannot mimic buy for {token_address[:8]}... from wallet {wallet_address[:8]}... - max positions reached",
                    max_positions=strategy_engine.max_positions
                )
                return
            
            # Check balance
            balance = await wallet_manager.get_balance()
            buy_amount = min(amount_sol, strategy_engine.max_buy_amount_sol)
            if balance < buy_amount * 1.2:  # Add 20% buffer for fees
                logger.warning(
                    f"Insufficient SOL balance to mimic buy for {token_address[:8]}...: {balance:.4f} SOL",
                    required=buy_amount * 1.2
                )
                return
            
            # Fetch token details
            token_data = await connection_manager.fetch_pump_token_data(token_address)
            if not token_data:
                logger.error(f"Failed to fetch token data for {token_address[:8]}...")
                return
            
            token_info = TokenInfo(token_data)
            
            # Execute buy
            logger.info(
                f"Mimicking buy for {token_info.symbol} from wallet {wallet_address[:8]}... with {buy_amount} SOL",
                token=token_address
            )
            
            success = await strategy_engine.execute_buy(token_info)
            if success:
                logger.info(
                    f"Successfully mimicked buy for {token_info.symbol} from wallet {wallet_address[:8]}...",
                    token=token_address,
                    amount_sol=buy_amount
                )
            else:
                logger.error(
                    f"Failed to mimic buy for {token_info.symbol} from wallet {wallet_address[:8]}...",
                    token=token_address
                )
                
        except Exception as e:
            logger.error(f"Error mimicking buy for token {token_address[:8]}... from wallet {wallet_address[:8]}...: {e}")
    
    def register_buy_callback(self, callback: Callable[[str, str, float], None]) -> None:
        """
        Register a callback for buy transactions from tracked wallets.
        
        Args:
            callback: Function to call when buy detected (params: wallet_address, token_address, amount_sol)
        """
        self.buy_callbacks.append(callback)
        logger.info(f"Registered wallet buy callback. Total callbacks: {len(self.buy_callbacks)}")
    
    def add_tracked_wallet(self, wallet_address: str) -> None:
        """
        Add a wallet to track.
        
        Args:
            wallet_address: Wallet address to track
        """
        if wallet_address not in self.tracked_wallets:
            self.tracked_wallets.add(wallet_address)
            logger.info(f"Added wallet to track: {wallet_address[:8]}...")
            
            # If already running, subscribe to this wallet
            if self.running:
                asyncio.create_task(self._subscribe_to_wallet_and_program(wallet_address, {
                    'on_wallet_update': lambda data: asyncio.create_task(self._handle_wallet_update(wallet_address, data)),
                    'on_pump_transaction': lambda data: asyncio.create_task(self._handle_pump_transaction(wallet_address, data)),
                    'on_new_signature': lambda sig: asyncio.create_task(self._handle_new_signature(wallet_address, sig))
                }))
    
    def remove_tracked_wallet(self, wallet_address: str) -> None:
        """
        Remove a wallet from tracking.
        
        Args:
            wallet_address: Wallet address to stop tracking
        """
        if wallet_address in self.tracked_wallets:
            self.tracked_wallets.remove(wallet_address)
            logger.info(f"Removed wallet from tracking: {wallet_address[:8]}...")
            
            # Unsubscribe if we have a subscription
            for subscription_id, desc in list(self.subscriptions.items()):
                if desc.startswith(f"account_{wallet_address}") or desc.startswith(f"signature_{wallet_address}"):
                    asyncio.create_task(connection_manager.unsubscribe(subscription_id))
                    del self.subscriptions[subscription_id]


class PumpFunTransactionParser:
    """Parser for pump.fun transactions to identify buy/sell/create operations."""
    
    def __init__(self):
        self.pump_program_id = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
        self.BUY_DISCRIMINATOR = bytes([102, 6, 61, 18, 1, 218, 235, 234])
        self.SELL_DISCRIMINATOR = bytes([51, 230, 133, 164, 1, 127, 131, 173])
        
    def parse_transaction_from_logs(self, log_data: Dict) -> Optional[Dict]:
        """
        Parse pump.fun transaction from WebSocket log notification.
        This is the primary method for real-time detection.
        """
        try:
            signature = log_data.get('signature')
            logs = log_data.get('logs', [])
            err = log_data.get('err')
            
            if err:
                return None
                
            # Check if this is a pump.fun transaction
            if not any(self.pump_program_id in log for log in logs):
                return None
                
            # Look for specific pump.fun events in logs
            transaction_type = self._identify_transaction_type_from_logs(logs)
            
            if transaction_type:
                return {
                    'signature': signature,
                    'type': transaction_type,
                    'logs': logs,
                    'timestamp': asyncio.get_event_loop().time()
                }
                
        except Exception as e:
            logger.error(f"Error parsing transaction logs: {e}")
            return None
    
    def _identify_transaction_type_from_logs(self, logs: List[str]) -> Optional[str]:
        """
        Identify transaction type from program logs.
        Pump.fun emits specific log messages for different operations.
        """
        for log in logs:
            if "Program log: Instruction: Buy" in log:
                return "buy"
            elif "Program log: Instruction: Sell" in log:
                return "sell"
            elif "Program log: Instruction: Create" in log:
                return "create"
                
        # If no clear log message, we need to fetch full transaction
        return "unknown"
    
    async def parse_transaction_details(self, connection, signature: str, tracked_wallet: str) -> Optional[Dict]:
        """
        Fetch and parse full transaction details when needed.
        This provides complete information about the transaction.
        """
        try:
            # Fetch transaction with full details
            transaction = await connection.get_transaction(
                signature,
                encoding="jsonParsed",
                max_supported_transaction_version=0
            )
            
            if not transaction or not transaction['result']:
                return None
                
            tx_data = transaction['result']
            meta = tx_data.get('meta', {})
            transaction_message = tx_data.get('transaction', {}).get('message', {})
            
            # Parse instructions to find pump.fun operations
            parsed_info = self._parse_pump_instructions(
                transaction_message,
                meta,
                tracked_wallet
            )
            
            if parsed_info:
                parsed_info['signature'] = signature
                parsed_info['slot'] = tx_data.get('slot')
                parsed_info['blockTime'] = tx_data.get('blockTime')
                
            return parsed_info
            
        except Exception as e:
            logger.error(f"Error fetching transaction {signature}: {e}")
            return None
    
    def _parse_pump_instructions(self, message: Dict, meta: Dict, tracked_wallet: str) -> Optional[Dict]:
        """
        Parse pump.fun instructions from transaction message.
        This identifies the specific operation type and extracts relevant data.
        """
        instructions = message.get('instructions', [])
        account_keys = message.get('accountKeys', [])
        
        for idx, instruction in enumerate(instructions):
            # Check if this is a pump.fun instruction
            program_id = self._get_program_id(instruction, account_keys)
            
            if program_id != self.pump_program_id:
                continue
                
            # Decode instruction data
            instruction_data = self._decode_instruction_data(instruction, account_keys)
            
            if not instruction_data:
                continue
                
            # Check if tracked wallet is involved
            if not self._is_wallet_involved(instruction, account_keys, tracked_wallet):
                continue
                
            return instruction_data
                
        return None
    
    def _get_program_id(self, instruction: Dict, account_keys: List) -> str:
        """Get the program ID for an instruction."""
        program_id_index = instruction.get('programIdIndex')
        if program_id_index is not None and program_id_index < len(account_keys):
            return account_keys[program_id_index]
        return ""
    
    def _decode_instruction_data(self, instruction: Dict, account_keys: List) -> Optional[Dict]:
        """
        Decode pump.fun instruction data to identify operation type.
        """
        try:
            # Get instruction data (base58 encoded)
            data = instruction.get('data')
            if not data:
                return None
                
            # Decode from base58
            decoded_data = base58.b58decode(data)
            
            # Check discriminator (first 8 bytes)
            discriminator = decoded_data[:8]
            
            if discriminator == self.BUY_DISCRIMINATOR:
                return self._parse_buy_instruction(decoded_data, instruction, account_keys)
            elif discriminator == self.SELL_DISCRIMINATOR:
                return self._parse_sell_instruction(decoded_data, instruction, account_keys)
            else:
                # Check for create instruction (different pattern)
                return self._check_for_create_instruction(instruction, account_keys)
                
        except Exception as e:
            logger.error(f"Error decoding instruction: {e}")
            return None
    
    def _parse_buy_instruction(self, data: bytes, instruction: Dict, account_keys: List) -> Dict:
        """
        Parse buy instruction data to extract amounts and token info.
        """
        try:
            # Unpack data (after 8-byte discriminator)
            # Format: discriminator(8) + amount(8) + max_sol_cost(8)
            amount = struct.unpack('<Q', data[8:16])[0]
            max_sol_cost = struct.unpack('<Q', data[16:24])[0]
            
            # Get accounts involved
            accounts = instruction.get('accounts', [])
            
            return {
                'type': 'buy',
                'token_amount': amount,
                'max_sol_cost': max_sol_cost,
                'max_sol_cost_ui': max_sol_cost / 1e9,  # Convert lamports to SOL
                'mint': account_keys[accounts[2]] if len(accounts) > 2 else None,
                'buyer': account_keys[accounts[6]] if len(accounts) > 6 else None,
                'instruction_index': instruction.get('index', 0)
            }
        except Exception as e:
            logger.error(f"Error parsing buy instruction: {e}")
            return {'type': 'buy', 'error': str(e)}
    
    def _parse_sell_instruction(self, data: bytes, instruction: Dict, account_keys: List) -> Dict:
        """
        Parse sell instruction data to extract amounts and token info.
        """
        try:
            # Unpack data (after 8-byte discriminator)
            # Format may vary, extract what we can
            accounts = instruction.get('accounts', [])
            
            return {
                'type': 'sell',
                'mint': account_keys[accounts[2]] if len(accounts) > 2 else None,
                'seller': account_keys[accounts[6]] if len(accounts) > 6 else None,
                'instruction_index': instruction.get('index', 0)
            }
        except Exception as e:
            logger.error(f"Error parsing sell instruction: {e}")
            return {'type': 'sell', 'error': str(e)}
    
    def _check_for_create_instruction(self, instruction: Dict, account_keys: List) -> Optional[Dict]:
        """
        Check if this is a create instruction for a new token.
        """
        # This is a placeholder; actual implementation may vary
        return None
    
    def _is_wallet_involved(self, instruction: Dict, account_keys: List, tracked_wallet: str) -> bool:
        """
        Check if the tracked wallet is involved in this instruction.
        """
        accounts = instruction.get('accounts', [])
        for account_idx in accounts:
            if account_idx < len(account_keys):
                account = account_keys[account_idx]
                if account == tracked_wallet:
                    return True
        return False


# Global wallet tracker instance (will be initialized later)
wallet_tracker = None

def initialize_wallet_tracker():
    """Initialize the global wallet tracker instance."""
    global wallet_tracker
    wallet_tracker = EnhancedWalletTracker()
    return wallet_tracker
</content>
