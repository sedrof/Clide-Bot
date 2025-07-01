"""
Unified DEX interface for all swap operations.
Provides a common interface for Jupiter, Raydium, and Pump.fun.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
from solders.transaction import Transaction

from src.utils.logger import get_logger

logger = get_logger("dex")


class DEXInterface(ABC):
    """Abstract base class for DEX integrations."""
    
    @abstractmethod
    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50
    ) -> Optional[Dict[str, Any]]:
        """Get a swap quote."""
        pass
    
    @abstractmethod
    async def build_swap_transaction(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        user_public_key: str,
        slippage_bps: int = 50
    ) -> Optional[Transaction]:
        """Build a swap transaction."""
        pass
    
    @abstractmethod
    async def get_pool_info(self, token_mint: str) -> Optional[Dict[str, Any]]:
        """Get pool information for a token."""
        pass


class DEXRouter:
    """Routes swap requests to appropriate DEX based on liquidity and price."""
    
    def __init__(self):
        self.dexes: Dict[str, DEXInterface] = {}
        self._initialized = False
    
    def register_dex(self, name: str, dex: DEXInterface):
        """Register a DEX implementation."""
        self.dexes[name] = dex
        logger.info(f"Registered DEX: {name}")
    
    async def find_best_route(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Find the best DEX route for a swap.
        
        Returns:
            Tuple of (dex_name, quote)
        """
        best_dex = None
        best_quote = None
        best_output = 0
        
        # Check all DEXes for best price
        for dex_name, dex in self.dexes.items():
            try:
                quote = await dex.get_quote(
                    input_mint=input_mint,
                    output_mint=output_mint,
                    amount=amount,
                    slippage_bps=slippage_bps
                )
                
                if quote:
                    output_amount = int(quote.get("outputAmount", 0))
                    if output_amount > best_output:
                        best_output = output_amount
                        best_quote = quote
                        best_dex = dex_name
                        
            except Exception as e:
                logger.error(f"Error getting quote from {dex_name}: {e}")
        
        if best_dex and best_quote:
            logger.info(
                f"Best route: {best_dex} - "
                f"{amount / 1e9:.6f} -> {best_output / 1e9:.6f}"
            )
            return best_dex, best_quote
        
        return None, None
    
    async def execute_swap(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        user_public_key: str,
        slippage_bps: int = 50,
        preferred_dex: Optional[str] = None
    ) -> Optional[Transaction]:
        """
        Execute a swap using the best available DEX.
        
        Args:
            input_mint: Input token mint
            output_mint: Output token mint
            amount: Amount in smallest unit
            user_public_key: User's public key
            slippage_bps: Slippage in basis points
            preferred_dex: Optional preferred DEX
            
        Returns:
            Transaction if successful
        """
        if preferred_dex and preferred_dex in self.dexes:
            # Use preferred DEX if specified
            dex = self.dexes[preferred_dex]
            return await dex.build_swap_transaction(
                input_mint=input_mint,
                output_mint=output_mint,
                amount=amount,
                user_public_key=user_public_key,
                slippage_bps=slippage_bps
            )
        
        # Find best route
        best_dex, _ = await self.find_best_route(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount,
            slippage_bps=slippage_bps
        )
        
        if best_dex:
            dex = self.dexes[best_dex]
            return await dex.build_swap_transaction(
                input_mint=input_mint,
                output_mint=output_mint,
                amount=amount,
                user_public_key=user_public_key,
                slippage_bps=slippage_bps
            )
        
        logger.error("No DEX available for swap")
        return None


# Global DEX router instance
dex_router = DEXRouter()
