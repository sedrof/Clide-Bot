"""
Jupiter integration for token swaps on Solana.
Provides real swap functionality using Jupiter aggregator.
"""

import aiohttp
import asyncio
from typing import Optional, Dict, Any, List
from solders.pubkey import Pubkey as PublicKey
from solders.keypair import Keypair
from solders.transaction import Transaction
from solders.message import Message
from solders.instruction import Instruction, AccountMeta
import base64
import json

from src.utils.logger import get_logger

logger = get_logger("jupiter")


class JupiterClient:
    """Client for interacting with Jupiter aggregator API."""
    
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
            logger.info("Jupiter client initialized")
    
    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,  # Amount in smallest unit (lamports for SOL)
        slippage_bps: int = 50,  # 0.5% default slippage
        only_direct_routes: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get a swap quote from Jupiter.
        
        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address  
            amount: Amount to swap in smallest unit
            slippage_bps: Slippage tolerance in basis points
            only_direct_routes: Whether to use only direct routes
            
        Returns:
            Quote data if successful
        """
        try:
            if not self.session:
                await self.initialize()
            
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippageBps": slippage_bps,
                "onlyDirectRoutes": str(only_direct_routes).lower()
            }
            
            async with self.session.get(f"{self.api_url}/quote", params=params) as response:
                if response.status == 200:
                    quote = await response.json()
                    logger.info(
                        f"Got quote: {amount / 1e9:.6f} {input_mint[:8]}... -> "
                        f"{int(quote.get('outAmount', 0)) / 1e9:.6f} {output_mint[:8]}..."
                    )
                    return quote
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get quote: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting quote: {e}")
            return None
    
    async def get_swap_transaction(
        self,
        quote: Dict[str, Any],
        user_public_key: str,
        wrap_unwrap_sol: bool = True,
        fee_account: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the swap transaction from Jupiter.
        
        Args:
            quote: Quote data from get_quote
            user_public_key: User's public key
            wrap_unwrap_sol: Whether to wrap/unwrap SOL automatically
            fee_account: Optional fee account
            
        Returns:
            Transaction data if successful
        """
        try:
            if not self.session:
                await self.initialize()
            
            body = {
                "quoteResponse": quote,
                "userPublicKey": user_public_key,
                "wrapAndUnwrapSol": wrap_unwrap_sol,
                "dynamicComputeUnitLimit": True,
                "prioritizationFeeLamports": "auto"
            }
            
            if fee_account:
                body["feeAccount"] = fee_account
            
            headers = {"Content-Type": "application/json"}
            
            async with self.session.post(
                f"{self.api_url}/swap",
                json=body,
                headers=headers
            ) as response:
                if response.status == 200:
                    swap_data = await response.json()
                    logger.info("Got swap transaction from Jupiter")
                    return swap_data
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get swap transaction: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting swap transaction: {e}")
            return None
    
    async def swap_tokens(
        self,
        input_mint: str,
        output_mint: str,
        amount_lamports: int,
        user_public_key: str,
        slippage_bps: int = 50
    ) -> Optional[str]:
        """
        High-level method to perform a token swap.
        
        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount_lamports: Amount to swap in lamports
            user_public_key: User's public key
            slippage_bps: Slippage tolerance in basis points
            
        Returns:
            Serialized transaction if successful
        """
        try:
            # Get quote
            quote = await self.get_quote(
                input_mint=input_mint,
                output_mint=output_mint,
                amount=amount_lamports,
                slippage_bps=slippage_bps
            )
            
            if not quote:
                logger.error("Failed to get quote")
                return None
            
            # Log the quote details
            out_amount = int(quote.get("outAmount", 0))
            price_impact = float(quote.get("priceImpactPct", 0))
            logger.info(
                f"Quote received: {amount_lamports / 1e9:.6f} SOL -> "
                f"{out_amount / 1e9:.6f} tokens, "
                f"price impact: {price_impact:.2f}%"
            )
            
            # Check for high price impact
            if price_impact > 5.0:  # 5% threshold
                logger.warning(f"High price impact detected: {price_impact:.2f}%")
                # Could add confirmation logic here
            
            # Get swap transaction
            swap_data = await self.get_swap_transaction(
                quote=quote,
                user_public_key=user_public_key,
                wrap_unwrap_sol=True
            )
            
            if not swap_data:
                logger.error("Failed to get swap transaction")
                return None
            
            # Return the serialized transaction
            return swap_data.get("swapTransaction")
            
        except Exception as e:
            logger.error(f"Error performing swap: {e}")
            return None
    
    async def get_token_price(self, token_mint: str, vs_token: str = None) -> Optional[float]:
        """
        Get token price using Jupiter price API.
        
        Args:
            token_mint: Token mint address
            vs_token: Token to price against (default: USDC)
            
        Returns:
            Price if successful
        """
        try:
            if not vs_token:
                vs_token = self.USDC
                
            # Get a small quote to determine price
            quote = await self.get_quote(
                input_mint=token_mint,
                output_mint=vs_token,
                amount=1_000_000_000,  # 1 token (assuming 9 decimals)
                slippage_bps=100
            )
            
            if quote:
                out_amount = int(quote.get("outAmount", 0))
                # Convert to price (assuming USDC has 6 decimals)
                price = out_amount / 1_000_000
                return price
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting token price: {e}")
            return None


# Global Jupiter client instance
jupiter_client = JupiterClient()


async def initialize_jupiter():
    """Initialize the Jupiter client."""
    await jupiter_client.initialize()
    return jupiter_client
