"""
Jupiter DEX integration for token swaps.
Implements the DEX interface for Jupiter aggregator.
"""

import aiohttp
import asyncio
from typing import Optional, Dict, Any
from solders.pubkey import Pubkey as PublicKey
from solders.transaction import Transaction
import base64

from src.integrations.dex_interface import DEXInterface
from src.utils.logger import get_logger

logger = get_logger("jupiter")


class JupiterDEX(DEXInterface):
    """Jupiter aggregator implementation."""
    
    def __init__(self):
        self.api_url = "https://quote-api.jup.ag/v6"
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Token addresses
        self.WSOL = "So11111111111111111111111111111111111111112"
        self.USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    
    async def initialize(self):
        """Initialize the HTTP session."""
        if not self.session:
            self.session = aiohttp.ClientSession()
            logger.info("Jupiter DEX initialized")
    
    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50
    ) -> Optional[Dict[str, Any]]:
        """Get a swap quote from Jupiter."""
        try:
            if not self.session:
                await self.initialize()
            
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippageBps": slippage_bps,
                "onlyDirectRoutes": "false"
            }
            
            async with self.session.get(f"{self.api_url}/quote", params=params) as response:
                if response.status == 200:
                    quote = await response.json()
                    # Add outputAmount field for consistency
                    quote["outputAmount"] = quote.get("outAmount", 0)
                    return quote
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get Jupiter quote: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting Jupiter quote: {e}")
            return None
    
    async def build_swap_transaction(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        user_public_key: str,
        slippage_bps: int = 50
    ) -> Optional[Transaction]:
        """Build a swap transaction using Jupiter."""
        try:
            # Get quote first
            quote = await self.get_quote(
                input_mint=input_mint,
                output_mint=output_mint,
                amount=amount,
                slippage_bps=slippage_bps
            )
            
            if not quote:
                return None
            
            # Get swap transaction
            body = {
                "quoteResponse": quote,
                "userPublicKey": user_public_key,
                "wrapAndUnwrapSol": True,
                "dynamicComputeUnitLimit": True,
                "prioritizationFeeLamports": "auto"
            }
            
            headers = {"Content-Type": "application/json"}
            
            async with self.session.post(
                f"{self.api_url}/swap",
                json=body,
                headers=headers
            ) as response:
                if response.status == 200:
                    swap_data = await response.json()
                    serialized_tx = swap_data.get("swapTransaction")
                    if serialized_tx:
                        tx_bytes = base64.b64decode(serialized_tx)
                        return Transaction.from_bytes(tx_bytes)
                    return None
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get Jupiter swap tx: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error building Jupiter swap transaction: {e}")
            return None
    
    async def get_pool_info(self, token_mint: str) -> Optional[Dict[str, Any]]:
        """Get pool information for a token."""
        # Jupiter is an aggregator, return basic info
        return {
            "dex": "Jupiter",
            "type": "aggregator",
            "token_mint": token_mint
        }


# Global Jupiter instance
jupiter_dex = JupiterDEX()
