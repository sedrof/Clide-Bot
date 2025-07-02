"""
Connection management for the Solana pump.fun sniping bot.
Fixed to ensure reliable RPC connections.
"""
# File Location: src/core/connection_manager.py

import asyncio
from typing import List, Optional, Dict, Any, Callable
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment

from src.utils.config import config_manager
from src.utils.logger import get_logger

logger = get_logger("connection")


class ConnectionManager:
    """Manages connections to Solana RPC endpoints."""
    
    def __init__(self):
        self.rpc_clients: List[AsyncClient] = []
        self.active_client: Optional[AsyncClient] = None
        self.rpc_endpoints: List[str] = []
        self.commitment: Commitment = Commitment("confirmed")
        self.timeout: int = 30
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize connection manager with configuration."""
        if self._initialized:
            logger.info("Connection manager already initialized")
            return
            
        settings = config_manager.get_settings()
        
        self.rpc_endpoints = settings.solana.rpc_endpoints
        self.commitment = Commitment(settings.solana.commitment)
        self.timeout = settings.solana.timeout
        
        # Create RPC clients
        self.rpc_clients = []
        for endpoint in self.rpc_endpoints:
            client = AsyncClient(
                endpoint, 
                commitment=self.commitment,
                timeout=self.timeout
            )
            self.rpc_clients.append(client)
        
        logger.info(f"Created {len(self.rpc_clients)} RPC client(s)")
        
        # Connect to first available
        await self.connect_rpc()
        self._initialized = True
        
    async def connect_rpc(self) -> Optional[AsyncClient]:
        """Connect to an RPC endpoint."""
        if not self.rpc_clients:
            logger.error("No RPC clients available")
            return None
        
        # Try each endpoint
        for i, client in enumerate(self.rpc_clients):
            try:
                endpoint = self.rpc_endpoints[i]
                logger.info(f"Attempting to connect to: {endpoint}")
                
                # Test connection
                result = await client.get_slot()
                if result:
                    self.active_client = client
                    logger.info(f"✅ Successfully connected to RPC: {endpoint}")
                    return client
                    
            except Exception as e:
                logger.error(f"Failed to connect to endpoint {i}: {e}")
                continue
        
        logger.error("❌ Could not connect to any RPC endpoint")
        return None
    
    async def get_rpc_client(self) -> Optional[AsyncClient]:
        """Get an active RPC client."""
        if not self._initialized:
            await self.initialize()
            
        if self.active_client:
            try:
                # Quick test
                await self.active_client.get_slot()
                return self.active_client
            except:
                logger.warning("Active client failed, reconnecting...")
                
        return await self.connect_rpc()
    
    async def close_all(self) -> None:
        """Close all connections."""
        try:
            for client in self.rpc_clients:
                try:
                    await client.close()
                except:
                    pass
            logger.info("All connections closed")
        except Exception as e:
            logger.error(f"Error closing connections: {e}")


# Global connection manager instance
connection_manager = ConnectionManager()
