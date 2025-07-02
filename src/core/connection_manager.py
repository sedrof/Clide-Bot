"""
Connection management for the Solana pump.fun sniping bot.
Handles RPC endpoint connections and failover.
"""

import asyncio
from typing import List, Optional, Dict, Any
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment, Confirmed
import time

from src.utils.config import config_manager
from src.utils.logger import get_logger

logger = get_logger("connection")


class ConnectionManager:
    """Manages connections to Solana RPC endpoints with failover support."""
    
    def __init__(self):
        self.rpc_endpoints: List[str] = []
        self.rpc_clients: List[AsyncClient] = []
        self.active_client_index: int = 0
        self.active_client: Optional[AsyncClient] = None
        self._initialized: bool = False
        self.commitment: Commitment = Confirmed
        self.timeout: int = 30
    
    async def initialize(self) -> None:
        """Initialize connection manager with configured endpoints."""
        if self._initialized:
            logger.info("Connection manager already initialized")
            return
            
        settings = config_manager.get_settings()
        self.rpc_endpoints = settings.solana.rpc_endpoints
        self.commitment = Commitment(settings.solana.commitment)
        self.timeout = settings.solana.timeout
        
        # Create RPC clients
        for endpoint in self.rpc_endpoints:
            client = AsyncClient(
                endpoint,
                commitment=self.commitment,
                timeout=self.timeout
            )
            self.rpc_clients.append(client)
        
        logger.info(f"Created {len(self.rpc_clients)} RPC client(s)")
        
        # Connect to first available endpoint
        await self._connect_to_endpoint()
        self._initialized = True
    
    async def _connect_to_endpoint(self) -> bool:
        """Try to connect to an RPC endpoint."""
        for i, client in enumerate(self.rpc_clients):
            try:
                endpoint = self.rpc_endpoints[i]
                logger.info(f"Attempting to connect to: {endpoint}")
                
                # Test connection
                result = await client.get_health()
                if result:
                    self.active_client = client
                    self.active_client_index = i
                    logger.info(f"✅ Successfully connected to RPC: {endpoint}")
                    return True
                    
            except Exception as e:
                logger.error(f"Failed to connect to endpoint {i}: {e}")
                continue
        
        logger.error("❌ Could not connect to any RPC endpoint")
        return False
    
    async def get_client(self) -> Optional[AsyncClient]:
        """Get the active RPC client with automatic failover."""
        if not self._initialized:
            await self.initialize()
            
        if self.active_client:
            return self.active_client
            
        # Try to reconnect
        if await self._connect_to_endpoint():
            return self.active_client
            
        return None
    
    async def get_rpc_client(self) -> Optional[AsyncClient]:
        """Alias for get_client() for backward compatibility."""
        return await self.get_client()
    
    async def close_all(self) -> None:
        """Close all RPC connections."""
        try:
            for client in self.rpc_clients:
                try:
                    await client.close()
                except:
                    pass
            logger.info("All connections closed")
        except Exception as e:
            logger.error(f"Error closing connections: {e}")
    
    def is_connected(self) -> bool:
        """Check if we have an active connection."""
        return self.active_client is not None


# Global connection manager instance
connection_manager = ConnectionManager()
