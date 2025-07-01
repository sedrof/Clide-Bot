"""
Transaction builder with multi-DEX support.
Supports Jupiter, Raydium, and Pump.fun for copy trading.
"""

from typing import Optional, Dict, Any, List
from solders.transaction import Transaction
from solders.pubkey import Pubkey as PublicKey

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.core.wallet_manager import wallet_manager
from src.core.connection_manager import connection_manager
from src.integrations.dex_interface import dex_router
from src.integrations.jupiter_dex import jupiter_dex
from src.integrations.raydium_dex import raydium_dex
from src.integrations.pumpfun_dex import pumpfun_dex

logger = get_logger("transaction")


class TransactionBuilder:
    """Builds transactions for token trading on multiple DEXs."""
    
    def __init__(self):
        self.settings = config_manager.get_settings()
        
        # Token constants
        self.WSOL_MINT = "So11111111111111111111111111111111111111112"
        
        # DEX preferences (can be configured)
        self.dex_priority = ["Jupiter", "Raydium", "Pump.fun"]
        
        self._initialized = False
    
    async def initialize(self):
        """Initialize DEX integrations."""
        if self._initialized:
            return
        
        # Initialize all DEXs
        await jupiter_dex.initialize()
        await raydium_dex.initialize()
        await pumpfun_dex.initialize()
        
        # Register with router
        dex_router.register_dex("Jupiter", jupiter_dex)
        dex_router.register_dex("Raydium", raydium_dex)
        dex_router.register_dex("Pump.fun", pumpfun_dex)
        
        self._initialized = True
        logger.info("Transaction builder initialized with all DEXs")
    
    async def build_and_execute_buy_transaction(
        self,
        token_address: str,
        amount_sol: float,
        slippage_tolerance: float = 0.01,
        priority_fee: Optional[int] = None,
        preferred_dex: Optional[str] = None
    ) -> Optional[str]:
        """
        Build and execute a buy transaction using the best available DEX.
        
        Args:
            token_address: Token mint address to buy
            amount_sol: Amount of SOL to spend
            slippage_tolerance: Slippage tolerance (0.01 = 1%)
            priority_fee: Optional priority fee in microlamports
            preferred_dex: Optional preferred DEX name
            
        Returns:
            Transaction signature if successful
        """
        try:
            logger.info(
                f"Building buy transaction for {token_address[:8]}... "
                f"with {amount_sol} SOL (DEX: {preferred_dex or 'auto'})"
            )
            
            # Validate inputs
            if amount_sol < 0.0001:
                logger.error(f"Amount too small: {amount_sol} SOL")
                return None
            
            # Ensure initialized
            await self.initialize()
            
            # Get wallet
            if not wallet_manager.get_public_key():
                raise ValueError("Wallet not initialized")
            
            # Convert SOL to lamports
            amount_lamports = int(amount_sol * 1_000_000_000)
            
            # Get transaction from DEX router
            transaction = await dex_router.execute_swap(
                input_mint=self.WSOL_MINT,
                output_mint=token_address,
                amount=amount_lamports,
                user_public_key=str(wallet_manager.get_public_key()),
                slippage_bps=int(slippage_tolerance * 10000),
                preferred_dex=preferred_dex
            )
            
            if not transaction:
                logger.error("Failed to build swap transaction")
                return None
            
            # Send and confirm transaction
            signature = await wallet_manager.send_and_confirm_transaction(transaction)
            
            if signature:
                logger.info(f"Buy transaction successful: {signature}")
                return signature
            else:
                logger.error("Failed to send buy transaction")
                return None
                
        except Exception as e:
            logger.error(f"Error building/executing buy transaction: {e}", exc_info=True)
            return None
    
    async def build_and_execute_sell_transaction(
        self,
        token_address: str,
        amount_tokens: float,
        slippage_tolerance: float = 0.01,
        priority_fee: Optional[int] = None,
        preferred_dex: Optional[str] = None
    ) -> Optional[str]:
        """
        Build and execute a sell transaction using the best available DEX.
        Same logic applies for all platforms - find best price and execute.
        
        Args:
            token_address: Token mint address to sell
            amount_tokens: Amount of tokens to sell
            slippage_tolerance: Slippage tolerance (0.01 = 1%)
            priority_fee: Optional priority fee in microlamports
            preferred_dex: Optional preferred DEX name
            
        Returns:
            Transaction signature if successful
        """
        try:
            logger.info(
                f"Building sell transaction for {token_address[:8]}... "
                f"with {amount_tokens} tokens (DEX: {preferred_dex or 'auto'})"
            )
            
            # Ensure initialized
            await self.initialize()
            
            # Get token decimals (assuming 9 for now, should fetch from chain)
            decimals = 9
            amount_smallest_unit = int(amount_tokens * (10 ** decimals))
            
            # Get transaction from DEX router
            transaction = await dex_router.execute_swap(
                input_mint=token_address,
                output_mint=self.WSOL_MINT,
                amount=amount_smallest_unit,
                user_public_key=str(wallet_manager.get_public_key()),
                slippage_bps=int(slippage_tolerance * 10000),
                preferred_dex=preferred_dex
            )
            
            if not transaction:
                logger.error("Failed to build sell transaction")
                return None
            
            # Send and confirm transaction
            signature = await wallet_manager.send_and_confirm_transaction(transaction)
            
            if signature:
                logger.info(f"Sell transaction successful: {signature}")
                return signature
            else:
                logger.error("Failed to send sell transaction")
                return None
                
        except Exception as e:
            logger.error(f"Error building/executing sell transaction: {e}", exc_info=True)
            return None
    
    async def get_best_price(
        self,
        input_mint: str,
        output_mint: str,
        amount: int
    ) -> Optional[Dict[str, Any]]:
        """Get best price across all DEXs."""
        await self.initialize()
        
        best_dex, best_quote = await dex_router.find_best_route(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount
        )
        
        if best_quote:
            return {
                "dex": best_dex,
                "quote": best_quote,
                "input_amount": amount,
                "output_amount": best_quote.get("outputAmount", 0)
            }
        
        return None


# Global transaction builder instance
transaction_builder = None

def initialize_transaction_builder():
    """Initialize the global transaction builder instance."""
    global transaction_builder
    transaction_builder = TransactionBuilder()
    return transaction_builder
