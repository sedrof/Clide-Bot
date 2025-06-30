"""
Wallet management for the Solana pump.fun sniping bot.
Handles keypair loading, balance checking, and transaction signing.
"""

import asyncio
from typing import Optional, List
from solders.keypair import Keypair
from solders.pubkey import Pubkey as PublicKey
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solana.rpc.types import TxOpts
from solders.transaction import Transaction
from solders.signature import Signature
import structlog

from src.utils.config import config_manager, WalletConfig
from src.utils.logger import get_logger

logger = get_logger("wallet")


class WalletManager:
    """Manages wallet operations including balance, transactions, and keypair handling."""
    
    def __init__(self):
        self.keypair: Optional[Keypair] = None
        self.public_key: Optional[PublicKey] = None
        self.client: Optional[AsyncClient] = None
        self._balance_cache: Optional[float] = None
        self._last_balance_check: float = 0
        self.balance_cache_duration = 5.0  # Cache balance for 5 seconds
        
    async def initialize(self, client: AsyncClient) -> None:
        """Initialize wallet manager with RPC client and load keypair."""
        self.client = client
        await self.load_keypair()
        logger.info("Wallet manager initialized", public_key=str(self.public_key))
    
    async def load_keypair(self) -> None:
        """Load keypair from configuration."""
        try:
            wallet_config = config_manager.get_wallet()
            
            # Convert list of integers to bytes
            keypair_bytes = bytes(wallet_config.keypair)
            self.keypair = Keypair.from_bytes(keypair_bytes)
            self.public_key = self.keypair.pubkey()
            
            # Verify the public key matches configuration
            if str(self.public_key) != wallet_config.public_key:
                logger.warning(
                    "Public key mismatch between keypair and config",
                    config_key=wallet_config.public_key,
                    derived_key=str(self.public_key)
                )
            
            logger.info("Keypair loaded successfully", public_key=str(self.public_key))
            
        except Exception as e:
            logger.error(f"Failed to load keypair: {e}")
            raise
    
    async def get_balance(self, force_refresh: bool = False) -> float:
        """
        Get SOL balance for the wallet.
        
        Args:
            force_refresh: Force refresh balance cache
            
        Returns:
            Balance in SOL
        """
        import time
        
        current_time = time.time()
        
        # Use cached balance if recent and not forcing refresh
        if (not force_refresh and 
            self._balance_cache is not None and 
            current_time - self._last_balance_check < self.balance_cache_duration):
            return self._balance_cache
        
        try:
            if not self.client or not self.public_key:
                raise ValueError("Wallet not initialized")
            
            response = await self.client.get_balance(self.public_key)
            balance_lamports = response.value
            balance_sol = balance_lamports / 1_000_000_000  # Convert lamports to SOL
            
            # Update cache
            self._balance_cache = balance_sol
            self._last_balance_check = current_time
            
            logger.debug(f"Balance updated: {balance_sol:.6f} SOL")
            return balance_sol
            
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            # Return cached balance if available, otherwise 0
            return self._balance_cache if self._balance_cache is not None else 0.0
    
    async def get_token_balance(self, token_mint: str) -> float:
        """
        Get balance for a specific SPL token.
        
        Args:
            token_mint: Token mint address
            
        Returns:
            Token balance
        """
        try:
            if not self.client or not self.public_key:
                raise ValueError("Wallet not initialized")
            
            mint_pubkey = PublicKey(token_mint)
            
            # Get token accounts for this wallet
            response = await self.client.get_token_accounts_by_owner(
                self.public_key,
                {"mint": mint_pubkey}
            )
            
            if not response.value:
                return 0.0
            
            # Get balance from the first token account
            token_account = response.value[0]
            account_info = await self.client.get_token_account_balance(
                PublicKey(token_account.pubkey)
            )
            
            if account_info.value:
                return float(account_info.value.ui_amount or 0)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to get token balance for {token_mint}: {e}")
            return 0.0
    
    async def sign_transaction(self, transaction: Transaction) -> Transaction:
        """
        Sign a transaction with the wallet keypair.
        
        Args:
            transaction: Transaction to sign
            
        Returns:
            Signed transaction
        """
        try:
            if not self.keypair:
                raise ValueError("Keypair not loaded")
            
            transaction.sign(self.keypair)
            logger.debug("Transaction signed successfully")
            return transaction
            
        except Exception as e:
            logger.error(f"Failed to sign transaction: {e}")
            raise
    
    async def send_transaction(
        self, 
        transaction: Transaction,
        opts: Optional[TxOpts] = None
    ) -> str:
        """
        Send a signed transaction to the network.
        
        Args:
            transaction: Signed transaction
            opts: Transaction options
            
        Returns:
            Transaction signature
        """
        try:
            if not self.client:
                raise ValueError("Client not initialized")
            
            # Default transaction options
            if opts is None:
                opts = TxOpts(
                    skip_preflight=False,
                    preflight_commitment=Commitment("confirmed"),
                    max_retries=3
                )
            
            response = await self.client.send_transaction(transaction, opts)
            signature = str(response.value)
            
            logger.info("Transaction sent", signature=signature)
            return signature
            
        except Exception as e:
            logger.error(f"Failed to send transaction: {e}")
            raise
    
    async def confirm_transaction(
        self, 
        signature: str, 
        commitment: Commitment = Commitment("confirmed"),
        timeout: float = 30.0
    ) -> bool:
        """
        Wait for transaction confirmation.
        
        Args:
            signature: Transaction signature
            commitment: Confirmation commitment level
            timeout: Timeout in seconds
            
        Returns:
            True if confirmed, False if timeout
        """
        try:
            if not self.client:
                raise ValueError("Client not initialized")
            
            sig = Signature.from_string(signature)
            
            # Wait for confirmation with timeout
            start_time = asyncio.get_event_loop().time()
            while True:
                response = await self.client.get_signature_statuses([sig])
                
                if response.value and response.value[0]:
                    status = response.value[0]
                    if status.confirmation_status and status.confirmation_status.value >= commitment.value:
                        logger.info("Transaction confirmed", signature=signature)
                        return True
                    
                    if status.err:
                        logger.error("Transaction failed", signature=signature, error=status.err)
                        return False
                
                # Check timeout
                if asyncio.get_event_loop().time() - start_time > timeout:
                    logger.warning("Transaction confirmation timeout", signature=signature)
                    return False
                
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Failed to confirm transaction {signature}: {e}")
            return False
    
    async def send_and_confirm_transaction(
        self,
        transaction: Transaction,
        commitment: Commitment = Commitment("confirmed"),
        timeout: float = 30.0
    ) -> Optional[str]:
        """
        Send transaction and wait for confirmation.
        
        Args:
            transaction: Transaction to send
            commitment: Confirmation commitment level
            timeout: Timeout in seconds
            
        Returns:
            Transaction signature if successful, None if failed
        """
        try:
            # Sign transaction
            signed_tx = await self.sign_transaction(transaction)
            
            # Send transaction
            signature = await self.send_transaction(signed_tx)
            
            # Wait for confirmation
            confirmed = await self.confirm_transaction(signature, commitment, timeout)
            
            if confirmed:
                return signature
            else:
                logger.error("Transaction not confirmed", signature=signature)
                return None
                
        except Exception as e:
            logger.error(f"Failed to send and confirm transaction: {e}")
            return None
    
    def get_public_key(self) -> Optional[PublicKey]:
        """Get wallet public key."""
        return self.public_key
    
    def get_keypair(self) -> Optional[Keypair]:
        """Get wallet keypair (use with caution)."""
        return self.keypair
    
    async def validate_wallet(self) -> bool:
        """
        Validate wallet configuration and connectivity.
        
        Returns:
            True if wallet is valid and accessible
        """
        try:
            if not self.keypair or not self.public_key or not self.client:
                logger.error("Wallet not properly initialized")
                return False
            
            # Try to get balance to test connectivity
            balance = await self.get_balance(force_refresh=True)
            
            if balance < 0.001:  # Minimum SOL for transactions
                logger.warning(f"Low SOL balance: {balance:.6f} SOL")
                return False
            
            logger.info(f"Wallet validation passed. Balance: {balance:.6f} SOL")
            return True
            
        except Exception as e:
            logger.error(f"Wallet validation failed: {e}")
            return False


# Global wallet manager instance
wallet_manager = WalletManager()
