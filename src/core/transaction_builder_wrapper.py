"""
Transaction builder wrapper to ensure compatibility
This fixes any method name mismatches
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.transaction_builder import TransactionBuilder as OriginalTransactionBuilder
from src.utils.logger import get_logger

logger = get_logger("transaction_wrapper")


class TransactionBuilderWrapper(OriginalTransactionBuilder):
    """Wrapper that ensures all expected methods exist."""
    
    async def build_and_execute_buy_transaction(
        self,
        token_address: str,
        amount_sol: float,
        slippage_tolerance: float = 0.01,
        priority_fee = None,
        preferred_dex = None
    ):
        """
        Universal buy method that routes to the correct implementation.
        """
        logger.info(f"Wrapper: Executing buy for {token_address[:8]}... on {preferred_dex or 'auto'}")
        
        # Check if the parent class has the method
        if hasattr(super(), 'build_and_execute_buy_transaction'):
            return await super().build_and_execute_buy_transaction(
                token_address=token_address,
                amount_sol=amount_sol,
                slippage_tolerance=slippage_tolerance,
                priority_fee=priority_fee,
                preferred_dex=preferred_dex
            )
        
        # If not, check for platform-specific methods
        if preferred_dex and preferred_dex.lower() == "pump.fun":
            if hasattr(self, 'build_pump_buy_transaction'):
                return await self.build_pump_buy_transaction(
                    token_address=token_address,
                    amount_sol=amount_sol,
                    slippage_tolerance=slippage_tolerance
                )
        
        # Fallback: Create a simple implementation
        logger.warning("No specific buy method found, using fallback implementation")
        
        # For now, just log and return None
        logger.error(f"Buy transaction not implemented for {preferred_dex or 'auto'}")
        return None
    
    async def build_and_execute_sell_transaction(
        self,
        token_address: str,
        amount_tokens: float,
        slippage_tolerance: float = 0.01,
        priority_fee = None,
        preferred_dex = None
    ):
        """
        Universal sell method that routes to the correct implementation.
        """
        logger.info(f"Wrapper: Executing sell for {token_address[:8]}...")
        
        # Check if the parent class has the method
        if hasattr(super(), 'build_and_execute_sell_transaction'):
            return await super().build_and_execute_sell_transaction(
                token_address=token_address,
                amount_tokens=amount_tokens,
                slippage_tolerance=slippage_tolerance,
                priority_fee=priority_fee,
                preferred_dex=preferred_dex
            )
        
        # Fallback
        logger.error(f"Sell transaction not implemented")
        return None


# Create wrapped instance
_original_builder = OriginalTransactionBuilder()
transaction_builder = TransactionBuilderWrapper()

# Copy attributes from original
transaction_builder.settings = _original_builder.settings
transaction_builder.WSOL_MINT = _original_builder.WSOL_MINT
transaction_builder.dex_priority = _original_builder.dex_priority
