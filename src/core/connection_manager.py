"""
Connection management for the Solana pump.fun sniping bot.
Fixed to use proper AsyncClient methods and ensure reliable connections.
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
        self._max_requests_per_minute: int = 100
        self._window_ms: int = 60000
        
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
        
        logger.info(f"Created {len(self.rpc_clients)} RPC client(s)")
        
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
        
        # Try each endpoint until successful connection
        for i, client in enumerate(self.rpc_clients):
            try:
                endpoint = self.rpc_endpoints[i]
                logger.info(f"Attempting to connect to: {endpoint}")
                
                # Test connection with get_slot instead of get_health
                result = await client.get_slot()
                if result:
                    self.active_client = client
                    logger.info(f"✅ Successfully connected to RPC endpoint {i}: {endpoint}")
                    self._connection_attempts = 0
                    return client
                    
            except Exception as e:
                logger.error(f"Failed to connect to endpoint {i}: {str(e)} | error_count={i+1}")
                continue
        
        # If we get here, no endpoints worked
        self._connection_attempts += 1
        logger.error(f"❌ Could not connect to any RPC endpoint | error_count={len(self.rpc_clients)}")
        
        if self._connection_attempts < self._max_retries:
            delay = self._retry_delay * (2 ** self._connection_attempts)
            logger.warning(f"Retrying in {delay:.1f} seconds... (Attempt {self._connection_attempts}/{self._max_retries})")
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
            # Simple test - get slot (not get_health which doesn't exist)
            await client.get_slot()
            return True
        except Exception as e:
            logger.debug(f"Connection test failed: {e}")
            return False
    
    async def get_rpc_client(self) -> Optional[AsyncClient]:
        """
        Get an active RPC client, reconnecting if needed.
        
        Returns:
            Active AsyncClient or None if no connection available
        """
        if self.active_client and await self.test_connection(self.active_client):
            return self.active_client
        
        logger.info("Active client not available, attempting to reconnect...")
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
            # Remove 'https://' and add 'wss://' for WebSocket
            ws_endpoint = self.websocket_endpoint
            if ws_endpoint.startswith('https://'):
                ws_endpoint = ws_endpoint.replace('https://', 'wss://')
            elif not ws_endpoint.startswith('wss://'):
                ws_endpoint = f'wss://{ws_endpoint}'
                
            self.websocket = await websockets.connect(ws_endpoint)
            logger.info("Connected to Solana WebSocket")
            
            # Start listening for messages if there are subscriptions
            if self._subscription_callbacks:
                asyncio.create_task(self._listen_for_messages(self.websocket))
            return self.websocket
        except Exception as e:
            logger.error(f"Failed to connect to Solana WebSocket: {e}")
            self.websocket = None
            return None
    
    async def subscribe_account(self, account: str, callback: Callable[[Any], None]) -> Optional[int]:
        """
        Subscribe to account changes via WebSocket.
        
        Args:
            account: Account address to subscribe to
            callback: Callback function for updates
            
        Returns:
            Subscription ID or None if failed
        """
        try:
            ws = await self.connect_websocket()
            if not ws:
                logger.warning("WebSocket not available, skipping subscription")
                return None
            
            # Create subscription request
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "accountSubscribe",
                "params": [
                    account,
                    {
                        "encoding": "base64",
                        "commitment": self.commitment.value
                    }
                ]
            }
            
            await ws.send(json.dumps(request))
            
            # Wait for subscription response
            response = await ws.recv()
            data = json.loads(response)
            
            if "result" in data:
                subscription_id = data["result"]
                self._subscription_callbacks[subscription_id] = callback
                
                # Start listening for messages if not already doing so
                if len(self._subscription_callbacks) == 1:
                    asyncio.create_task(self._listen_for_messages(ws))
                
                logger.info(f"Subscribed to account: {account[:8]}...", subscription_id=subscription_id)
                return subscription_id
            else:
                logger.error(f"Failed to subscribe to account: {data}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to subscribe to account {account[:8]}...: {e}")
            return None
            
    async def _listen_for_messages(self, ws: websockets.WebSocketClientProtocol) -> None:
        """
        Listen for incoming WebSocket messages and dispatch to callbacks.
        
        Args:
            ws: WebSocket connection to listen on
        """
        try:
            while not ws.closed:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    data = json.loads(message)
                    
                    # Check if this is a subscription notification
                    if "method" in data and data["method"] == "accountNotification":
                        subscription_id = data["params"]["subscription"]
                        if subscription_id in self._subscription_callbacks:
                            callback = self._subscription_callbacks[subscription_id]
                            asyncio.create_task(callback(data["params"]["result"]))
                            
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    await ws.ping()
                except Exception as e:
                    logger.error(f"Error processing WebSocket message: {e}")
                    
        except Exception as e:
            logger.error(f"WebSocket listener error: {e}")
            self.websocket = None
    
    async def get_recent_signatures(self, address: str, limit: int = 10) -> List[Any]:
        """
        Fetch recent transaction signatures for a wallet address.
        
        Args:
            address: Wallet address to fetch signatures for
            limit: Maximum number of signatures to return
            
        Returns:
            List of signature data
        """
        try:
            client = await self.get_rpc_client()
            if not client:
                logger.error("No RPC client available")
                return []
                
            pubkey = Pubkey.from_string(address)
            signatures = await client.get_signatures_for_address(pubkey, limit=limit)
            
            if signatures and signatures.value:
                logger.debug(f"Fetched {len(signatures.value)} signatures for {address[:8]}...")
                return signatures.value
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error fetching signatures for {address[:8]}...: {e}")
            return []
    
    async def get_transaction(self, signature: str) -> Optional[Any]:
        """
        Fetch full transaction details for a signature.
        
        Args:
            signature: Transaction signature to fetch
            
        Returns:
            Transaction data or None if failed
        """
        try:
            client = await self.get_rpc_client()
            if not client:
                logger.error("No RPC client available")
                return None
                
            transaction = await client.get_transaction(
                signature, 
                encoding="jsonParsed", 
                max_supported_transaction_version=0
            )
            
            if transaction and transaction.value:
                logger.debug(f"Fetched transaction data for {signature[:8]}...")
                return transaction.value
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error fetching transaction {signature[:8]}...: {e}")
            return None
    
    async def close(self) -> None:
        """Close all connections."""
        try:
            # Close RPC clients
            for client in self.rpc_clients:
                try:
                    await client.close()
                except:
                    pass
            
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
