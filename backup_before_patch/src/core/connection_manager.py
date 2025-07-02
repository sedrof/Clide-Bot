"""
Connection management for the Solana pump.fun sniping bot.
Handles Solana RPC connections and WebSocket subscriptions.
"""

import asyncio
import random
from typing import List, Optional, Dict, Any, Callable
import aiohttp
import websockets
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solana.rpc.websocket_api import connect as ws_connect
from solders.pubkey import Pubkey
import structlog
import json

from src.utils.config import config_manager
from src.utils.logger import get_logger

logger = get_logger("connection")


class ConnectionManager:
    """Manages connections to Solana RPC endpoints and WebSocket services."""
    
    def __init__(self):
        self.rpc_clients: List[AsyncClient] = []
        self.active_client: Optional[AsyncClient] = None
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.pump_ws: Optional[websockets.WebSocketClientProtocol] = None
        self.rpc_endpoints: List[str] = []
        self.websocket_endpoint: str = ""
        self.commitment: Commitment = Commitment("confirmed")
        self.timeout: int = 30
        self.pump_api_endpoint: str = ""
        self.pump_ws_endpoint: str = ""
        self._connection_attempts: int = 0
        self._max_retries: int = 5
        self._retry_delay: float = 2.0
        self._subscription_callbacks: Dict[int, Callable] = {}
        self._request_queue: List[Callable] = []
        self._processing_queue: bool = False
        self._request_count: int = 0
        self._reset_time: float = 0
        self._max_requests_per_minute: int = 100  # Adjusted for 120,000 CUs/min limit (~100 requests/sec)
        self._window_ms: int = 60000  # 1 minute window
        
    async def initialize(self) -> None:
        """Initialize connection manager with configuration."""
        settings = config_manager.get_settings()
        
        self.rpc_endpoints = settings.solana.rpc_endpoints
        self.websocket_endpoint = settings.solana.websocket_endpoint
        self.commitment = Commitment(settings.solana.commitment)
        self.timeout = settings.solana.timeout
        self.pump_api_endpoint = settings.pump_fun.api_endpoint
        self.pump_ws_endpoint = settings.pump_fun.websocket_endpoint
        
        # Create RPC clients for each endpoint
        self.rpc_clients = [
            AsyncClient(endpoint, commitment=self.commitment, timeout=self.timeout)
            for endpoint in self.rpc_endpoints
        ]
        
        logger.info(f"Connection manager initialized with {len(self.rpc_clients)} RPC endpoints")
        
        # Connect to first available client
        await self.connect_rpc()
        # Initialize request rate limiting
        self._reset_time = asyncio.get_event_loop().time() + (self._window_ms / 1000)
        
    async def connect_rpc(self) -> Optional[AsyncClient]:
        """
        Connect to an RPC endpoint, rotating through available endpoints if needed.
        
        Returns:
            Connected AsyncClient or None if connection fails
        """
        if not self.rpc_clients:
            logger.error("No RPC clients available")
            return None
        
        # If we already have an active client, use it
        if self.active_client and await self.test_connection(self.active_client):
            return self.active_client
        
        # Try each endpoint until successful connection
        for i, client in enumerate(self.rpc_clients):
            endpoint = self.rpc_endpoints[i]
            try:
                if not await client.is_connected():
                    await client.connect()
                
                if await self.test_connection(client):
                    self.active_client = client
                    logger.info(f"Connected to RPC endpoint: {endpoint}")
                    self._connection_attempts = 0
                    return client
                
            except Exception as e:
                logger.error(f"Failed to connect to {endpoint}: {e}")
                await client.close()
                continue
        
        # If we get here, no endpoints worked
        self._connection_attempts += 1
        if self._connection_attempts < self._max_retries:
            delay = self._retry_delay * (2 ** self._connection_attempts)
            logger.warning(f"All RPC connections failed. Retrying in {delay:.1f} seconds... (Attempt {self._connection_attempts}/{self._max_retries})")
            await asyncio.sleep(delay)
            return await self.connect_rpc()
        else:
            logger.error("Maximum retry attempts reached. Could not connect to any RPC endpoint.")
            self._connection_attempts = 0
            return None
    
    async def test_connection(self, client: AsyncClient) -> bool:
        """
        Test if an RPC connection is working.
        
        Args:
            client: RPC client to test
            
        Returns:
            True if connection is working
        """
        try:
            # Simple test - get slot
            await client.get_slot()
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    async def get_rpc_client(self) -> Optional[AsyncClient]:
        """
        Get an active RPC client, reconnecting if needed.
        
        Returns:
            Active AsyncClient or None if no connection available
        """
        if self.active_client and await self.test_connection(self.active_client):
            return self.active_client
        
        return await self.connect_rpc()
    
    async def connect_websocket(self) -> Optional[websockets.WebSocketClientProtocol]:
        """
        Connect to Solana WebSocket endpoint for real-time data.
        
        Returns:
            WebSocket connection or None if failed
        """
        if self.websocket and not self.websocket.closed:
            return self.websocket
        
        try:
            self.websocket = await ws_connect(self.websocket_endpoint)
            logger.info("Connected to Solana WebSocket")
            # Start listening for messages if there are subscriptions
            if self._subscription_callbacks:
                asyncio.create_task(self._listen_for_messages(self.websocket))
            return self.websocket
        except Exception as e:
            logger.error(f"Failed to connect to Solana WebSocket: {e}")
            self.websocket = None
            return None
    
    async def subscribe_account(self, account: str, callback: Callable[[Any], None]) -> int:
        """
        Subscribe to account changes via WebSocket with real-time transaction fetching.
        
        Args:
            account: Account address to subscribe to
            callback: Callback function for updates
            
        Returns:
            Subscription ID
        """
        try:
            ws = await self.connect_websocket()
            if not ws:
                raise ValueError("WebSocket not connected")
            
            subscription_id = await ws.account_subscribe(
                Pubkey.from_string(account),
                commitment=self.commitment,
                encoding="base64"
            )
            # Store callback for this subscription
            self._subscription_callbacks[subscription_id] = callback
            # Start listening for messages if not already doing so
            if len(self._subscription_callbacks) == 1:
                asyncio.create_task(self._listen_for_messages(ws))
            
            logger.info(f"Subscribed to account: {account[:8]}...", subscription_id=subscription_id)
            return subscription_id
        except Exception as e:
            logger.error(f"Failed to subscribe to account {account[:8]}...: {e}")
            raise
            
    async def _listen_for_messages(self, ws: websockets.WebSocketClientProtocol) -> None:
        """
        Listen for incoming WebSocket messages and dispatch to callbacks.
        
        Args:
            ws: WebSocket connection
        """
        try:
            while not ws.closed:
                message = await ws.recv()
                if message:
                    try:
                        # Handle different message formats
                        data = None
                        if isinstance(message, (str, bytes, bytearray)):
                            if isinstance(message, str):
                                data = json.loads(message)
                            else:
                                data = json.loads(message.decode('utf-8'))
                        elif isinstance(message, list):
                            logger.debug(f"Received list data, passing as-is: {str(message)[:100]}...")
                            data = {"raw_data": message}
                        else:
                            logger.error(f"Unexpected message type: {type(message)}")
                            continue
                        
                        # Extract subscription ID if available
                        subscription_id = None
                        if isinstance(data, dict):
                            subscription_id = data.get("params", {}).get("subscription", -1)
                        elif isinstance(data, dict) and "raw_data" in data:
                            # Handle raw data case if needed
                            subscription_id = -1
                        
                        if subscription_id is not None and subscription_id in self._subscription_callbacks:
                            callback = self._subscription_callbacks[subscription_id]
                            if callable(callback):
                                if asyncio.iscoroutinefunction(callback):
                                    await callback(data)
                                else:
                                    callback(data)
                            else:
                                logger.error(f"Callback for subscription {subscription_id} is not callable")
                        else:
                            logger.debug(f"No callback found for subscription {subscription_id if subscription_id is not None else 'unknown'}")
                    except json.JSONDecodeError:
                        logger.error("Failed to decode WebSocket message")
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {e}")
        except Exception as e:
            logger.error(f"WebSocket listener error: {e}")
    
    async def subscribe_program(self, program_id: str, callback: Callable[[Any], None]) -> int:
        """
        Subscribe to program events via WebSocket.
        
        Args:
            program_id: Program ID to subscribe to
            callback: Callback function for updates
            
        Returns:
            Subscription ID
        """
        try:
            ws = await self.connect_websocket()
            if not ws:
                raise ValueError("WebSocket not connected")
            
            subscription_id = await ws.program_subscribe(
                Pubkey.from_string(program_id),
                commitment=self.commitment,
                encoding="base64",
                filters=[]
            )
            # Store callback for this subscription
            self._subscription_callbacks[subscription_id] = callback
            logger.info(f"Subscribed to program: {program_id[:8]}...", subscription_id=subscription_id)
            return subscription_id
        except Exception as e:
            logger.error(f"Failed to subscribe to program {program_id[:8]}...: {e}")
            raise
    
    async def unsubscribe(self, subscription_id: int) -> None:
        """
        Unsubscribe from a WebSocket subscription.
        
        Args:
            subscription_id: ID of subscription to cancel
        """
        try:
            if self.websocket and not self.websocket.closed:
                await self.websocket.unsubscribe(subscription_id)
                if subscription_id in self._subscription_callbacks:
                    del self._subscription_callbacks[subscription_id]
                logger.info(f"Unsubscribed from ID: {subscription_id}")
        except Exception as e:
            logger.error(f"Failed to unsubscribe from {subscription_id}: {e}")
    
    async def connect_pump_websocket(self) -> Optional[websockets.WebSocketClientProtocol]:
        """
        Connect to pump.fun WebSocket for new token detection.
        
        Returns:
            WebSocket connection or None if failed
        """
        if self.pump_ws and not self.pump_ws.closed:
            return self.pump_ws
        
        try:
            self.pump_ws = await websockets.connect(self.pump_ws_endpoint)
            logger.info("Connected to pump.fun WebSocket")
            
            # Subscribe to new token events
            subscription_msg = {
                "method": "subscribeNewToken",
                "params": {}
            }
            await self.pump_ws.send(json.dumps(subscription_msg))
            logger.info("Subscribed to pump.fun new token events")
            
            return self.pump_ws
        except Exception as e:
            logger.error(f"Failed to connect to pump.fun WebSocket: {e}")
            self.pump_ws = None
            return None
    
    async def receive_pump_events(self, callback: Callable[[Any], None]) -> None:
        """
        Receive events from pump.fun WebSocket.
        
        Args:
            callback: Callback function for new token events
        """
        try:
            ws = await self.connect_pump_websocket()
            if not ws:
                raise ValueError("pump.fun WebSocket not connected")
            
            while True:
                try:
                    message = await ws.recv()
                    data = json.loads(message)
                    await callback(data)
                except websockets.ConnectionClosed:
                    logger.warning("pump.fun WebSocket connection closed. Reconnecting...")
                    ws = await self.connect_pump_websocket()
                    if not ws:
                        raise ValueError("Failed to reconnect to pump.fun WebSocket")
                except Exception as e:
                    logger.error(f"Error receiving pump.fun event: {e}")
                    await asyncio.sleep(1)
                    
        except Exception as e:
            logger.error(f"Failed to receive pump.fun events: {e}")
            raise
    
    async def fetch_pump_token_data(self, token_address: str) -> Dict[str, Any]:
        """
        Fetch detailed token data from pump.fun API with rate limiting.
        
        Args:
            token_address: Token address to query
            
        Returns:
            Token data dictionary
        """
        async def perform_request():
            async with aiohttp.ClientSession() as session:
                url = f"{self.pump_api_endpoint}/tokens/{token_address}"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.debug(f"Fetched token data for {token_address[:8]}...")
                        return data
                    else:
                        logger.error(f"Failed to fetch token data: HTTP {response.status}")
                        return {}
        
        try:
            return await self._rate_limited_request(perform_request)
        except Exception as e:
            logger.error(f"Error fetching token data for {token_address[:8]}...: {e}")
            return {}
    
    async def get_signatures_for_address(self, address: str, limit: int = 10) -> List[Any]:
        """
        Fetch recent transaction signatures for an address with rate limiting.
        
        Args:
            address: Wallet address to fetch signatures for
            limit: Maximum number of signatures to return
            
        Returns:
            List of signature data
        """
        async def perform_request():
            client = await self.get_rpc_client()
            if not client:
                raise ValueError("No RPC client available")
            pubkey = Pubkey.from_string(address)
            signatures = await client.get_signatures_for_address(pubkey, limit=limit)
            logger.debug(f"Fetched {len(signatures.value)} signatures for {address[:8]}...")
            return signatures.value
        
        try:
            return await self._rate_limited_request(perform_request)
        except Exception as e:
            logger.error(f"Error fetching signatures for {address[:8]}...: {e}")
            return []
    
    async def get_transaction(self, signature: str) -> Optional[Any]:
        """
        Fetch full transaction details for a signature with rate limiting.
        
        Args:
            signature: Transaction signature to fetch
            
        Returns:
            Transaction data or None if failed
        """
        async def perform_request():
            client = await self.get_rpc_client()
            if not client:
                raise ValueError("No RPC client available")
            transaction = await client.get_transaction(signature, encoding="jsonParsed", max_supported_transaction_version=0)
            logger.debug(f"Fetched transaction data for {signature[:8]}...")
            return transaction.value
        
        try:
            return await self._rate_limited_request(perform_request)
        except Exception as e:
            logger.error(f"Error fetching transaction {signature[:8]}...: {e}")
            return None
    
    async def _rate_limited_request(self, request_fn: Callable[[], Any]) -> Any:
        """
        Execute an RPC request with rate limiting to stay within CU limits.
        
        Args:
            request_fn: Function to execute the request
            
        Returns:
            Result of the request
        """
        return await asyncio.get_event_loop().create_task(self._enqueue_request(request_fn))
    
    async def _enqueue_request(self, request_fn: Callable[[], Any]) -> Any:
        """
        Enqueue a request for rate limiting.
        
        Args:
            request_fn: Function to execute the request
            
        Returns:
            Result of the request
        """
        future = asyncio.Future()
        self._request_queue.append(lambda: self._execute_request(request_fn, future))
        if not self._processing_queue:
            asyncio.create_task(self._process_queue())
        return await future
    
    async def _execute_request(self, request_fn: Callable[[], Any], future: asyncio.Future) -> None:
        """
        Execute a single request and set the result on the future.
        
        Args:
            request_fn: Function to execute the request
            future: Future to set the result on
        """
        try:
            result = await request_fn()
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
    
    async def _process_queue(self) -> None:
        """
        Process the request queue with rate limiting.
        """
        if self._processing_queue:
            return
        self._processing_queue = True
        
        while self._request_queue:
            current_time = asyncio.get_event_loop().time()
            if current_time > self._reset_time:
                self._request_count = 0
                self._reset_time = current_time + (self._window_ms / 1000)
                logger.debug("Rate limit window reset")
            
            if self._request_count >= self._max_requests_per_minute:
                wait_time = self._reset_time - current_time
                logger.debug(f"Rate limit reached. Waiting {wait_time:.2f} seconds")
                await asyncio.sleep(wait_time)
                continue
            
            request = self._request_queue.pop(0)
            self._request_count += 1
            await request()
            logger.debug(f"Request executed. Count: {self._request_count}/{self._max_requests_per_minute}")
        
        self._processing_queue = False
    
    async def close(self) -> None:
        """Close all connections."""
        try:
            # Close RPC clients
            for client in self.rpc_clients:
                if await client.is_connected():
                    await client.close()
            
            # Close WebSocket connections
            if self.websocket and not self.websocket.closed:
                await self.websocket.close()
            
            if self.pump_ws and not self.pump_ws.closed:
                await self.pump_ws.close()
            
            logger.info("All connections closed")
        except Exception as e:
            logger.error(f"Error closing connections: {e}")


# Global connection manager instance
connection_manager = ConnectionManager()
