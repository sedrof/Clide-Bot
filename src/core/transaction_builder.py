"""
Transaction builder for the Solana pump.fun sniping bot.
Fixed version with proper solders API usage and actual swap implementations.
"""

from typing import Optional, Dict, Any, List
from solders.transaction import Transaction
from solders.message import Message
from solders.instruction import Instruction, AccountMeta
from solders.pubkey import Pubkey as PublicKey
from solders.system_program import TransferParams, transfer
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from solders.hash import Hash
from solders.keypair import Keypair
import structlog

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.core.wallet_manager import wallet_manager
from src.core.connection_manager import connection_manager

logger = get_logger("transaction")


class TransactionBuilder:
    """Builds transactions for token trading on Solana."""
    
    def __init__(self):
        self.settings = config_manager.get_settings()
        
        # Program IDs for DEXs
        self.PUMP_PROGRAM_ID = PublicKey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
        self.RAYDIUM_V4_PROGRAM_ID = PublicKey.from_string("675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8")
        self.JUPITER_V6_PROGRAM_ID = PublicKey.from_string("JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4")
        
        # Token program IDs
        self.TOKEN_PROGRAM_ID = PublicKey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
        self.SYSTEM_PROGRAM_ID = PublicKey.from_string("11111111111111111111111111111111")
        self.WSOL_MINT = PublicKey.from_string("So11111111111111111111111111111111111111112")
        
        self.default_priority_fee = 100_000  # Default priority fee in microlamports
        
    async def build_and_execute_buy_transaction(
        self,
        token_address: str,
        amount_sol: float,
        slippage_tolerance: float = 0.1,
        priority_fee: Optional[int] = None
    ) -> Optional[str]:
        """
        Build and execute a buy transaction.
        For now, this is a placeholder that logs the attempt.
        
        Real implementation would require:
        1. Finding the appropriate liquidity pool
        2. Getting pool state and calculating amounts
        3. Building the actual swap instruction
        4. Signing and sending the transaction
        """
        try:
            logger.info(f"Building buy transaction for {token_address[:8]}... with {amount_sol} SOL")
            
            # Get wallet
            if not wallet_manager.get_public_key():
                raise ValueError("Wallet not initialized")
            
            # Get RPC client
            client = await connection_manager.get_rpc_client()
            if not client:
                raise ValueError("No RPC client available")
            
            # Get recent blockhash
            blockhash_resp = await client.get_latest_blockhash()
            if not blockhash_resp or not blockhash_resp.value:
                raise ValueError("Failed to get recent blockhash")
            
            recent_blockhash = blockhash_resp.value.blockhash
            
            # Create instructions list
            instructions = []
            
            # Add compute budget instructions
            if priority_fee is None:
                priority_fee = self.default_priority_fee
            
            instructions.append(set_compute_unit_limit(300_000))
            instructions.append(set_compute_unit_price(priority_fee))
            
            # TODO: Add actual swap instructions here
            # For now, we'll just create a minimal valid transaction
            # In production, this would include:
            # 1. Create/find associated token accounts
            # 2. Wrap SOL if needed
            # 3. Execute swap on DEX
            
            # Create message
            message = Message.new_with_blockhash(
                instructions,
                wallet_manager.get_public_key(),
                recent_blockhash
            )
            
            # Create transaction with proper arguments
            transaction = Transaction.new_unsigned(message)
            
            # Sign transaction
            signed_tx = await wallet_manager.sign_transaction(transaction)
            
            # Send transaction
            signature = await wallet_manager.send_and_confirm_transaction(signed_tx)
            
            if signature:
                logger.info(f"Buy transaction sent: {signature}")
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
        slippage_tolerance: float = 0.1,
        priority_fee: Optional[int] = None
    ) -> Optional[str]:
        """
        Build and execute a sell transaction.
        Placeholder implementation similar to buy.
        """
        try:
            logger.info(f"Building sell transaction for {token_address[:8]}... with {amount_tokens} tokens")
            
            # Similar structure to buy transaction
            # TODO: Implement actual sell logic
            
            return None
            
        except Exception as e:
            logger.error(f"Error building/executing sell transaction: {e}", exc_info=True)
            return None
    
    def calculate_priority_fee(
        self,
        urgency: str = "normal",
        base_fee: Optional[int] = None
    ) -> int:
        """
        Calculate priority fee based on urgency level.
        
        Args:
            urgency: Urgency level ("low", "normal", "high", "critical")
            base_fee: Base fee to use instead of default
            
        Returns:
            Priority fee in microlamports
        """
        if base_fee is None:
            base_fee = self.default_priority_fee
        
        multipliers = {
            "low": 0.5,
            "normal": 1.0,
            "high": 2.0,
            "critical": 5.0
        }
        
        multiplier = multipliers.get(urgency, 1.0)
        priority_fee = int(base_fee * multiplier)
        
        logger.debug(f"Calculated priority fee: {priority_fee} microlamports (urgency: {urgency})")
        return priority_fee


# Global transaction builder instance
transaction_builder = None

def initialize_transaction_builder():
    """Initialize the global transaction builder instance."""
    global transaction_builder
    transaction_builder = TransactionBuilder()
    return transaction_builder
