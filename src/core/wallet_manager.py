"""
Wallet management for the Solana pump.fun sniping bot.
Enhanced with precise balance reporting and correct imports.
"""

import asyncio
from typing import Optional, Dict, Any
from solders.keypair import Keypair
from solders.pubkey import Pubkey as PublicKey
from solders.transaction import Transaction
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.core.connection_manager import connection_manager

logger = get_logger("wallet")


class WalletManager:
    """Manages wallet operations including balance checks and transaction signing."""
    
    def __init__(self):
        self.keypair: Optional[Keypair] = None
        self.public_key: Optional[PublicKey] = None
        self._balance_cache: float = 0.0
        self._balance_cache_time: float = 0
        self._balance_cache_duration: float = 5.0  # Cache for 5 seconds
        
    def initialize(self) -> None:
        """Initialize wallet from configuration."""
        try:
            wallet_data = config_manager.get_wallet_data()
            
            # Load keypair from array
            if "keypair" in wallet_data:
                keypair_bytes = bytes(wallet_data["keypair"])
                self.keypair = Keypair.from_bytes(keypair_bytes)
                self.public_key = self.keypair.pubkey()
                logger.info(f"Loaded wallet: {self.public_key}")
            else:
                raise ValueError("No keypair found in wallet configuration")
                
        except Exception as e:
            logger.error(f"Failed to initialize wallet: {e}")
            raise
    
    async def get_balance(self, force_refresh: bool = False) -> float:
        """
        Get wallet SOL balance with proper precision.
        
        Args:
            force_refresh: Force refresh balance even if cached
            
        Returns:
            Balance in SOL with full precision
        """
        import time
        
        # Check cache
        current_time = time.time()
        if not force_refresh and (current_time - self._balance_cache_time) < self._balance_cache_duration:
            return self._balance_cache
        
        try:
            client = await connection_manager.get_client()
            if not client or not self.public_key:
                logger.error("No RPC client or wallet not initialized")
                return 0.0
            
            # Get balance in lamports
            response = await client.get_balance(self.public_key)
            balance_lamports = response.value
            
            # Convert to SOL with full precision (1 SOL = 1e9 lamports)
            balance_sol = balance_lamports / 1_000_000_000
            
            # Update cache
            self._balance_cache = balance_sol
            self._balance_cache_time = current_time
            
            # Log with full precision
            logger.info(f"Wallet balance: {balance_sol:.9f} SOL ({balance_lamports:,} lamports)")
            
            return balance_sol
            
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return self._balance_cache  # Return cached value on error
    
    async def sign_transaction(self, transaction: Transaction) -> Transaction:
        """
        Sign a transaction with the wallet keypair.
        
        Args:
            transaction: Transaction to sign
            
        Returns:
            Signed transaction
        """
        if not self.keypair:
            raise ValueError("Wallet not initialized")
            
        # For solders Transaction, we need to use partial_sign
        transaction.partial_sign([self.keypair])
        return transaction
    
    async def get_token_balance(self, token_mint: str) -> float:
        """
        Get balance of a specific SPL token.
        
        Args:
            token_mint: Token mint address
            
        Returns:
            Token balance
        """
        try:
            # This would need proper SPL token account lookup
            # For now, return 0
            return 0.0
        except Exception as e:
            logger.error(f"Failed to get token balance: {e}")
            return 0.0
    
    def get_public_key(self) -> Optional[str]:
        """Get the wallet's public key as a string."""
        if self.public_key:
            return str(self.public_key)
        return None
    
    async def check_sufficient_balance(self, required_sol: float) -> bool:
        """
        Check if wallet has sufficient balance for a transaction.
        
        Args:
            required_sol: Required amount in SOL
            
        Returns:
            True if sufficient balance, False otherwise
        """
        balance = await self.get_balance()
        has_sufficient = balance >= required_sol
        
        if not has_sufficient:
            logger.warning(
                f"Insufficient balance. Required: {required_sol:.9f} SOL, "
                f"Available: {balance:.9f} SOL"
            )
        
        return has_sufficient


# Global wallet manager instance
wallet_manager = WalletManager()
