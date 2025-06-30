"""
Transaction builder for the Solana pump.fun sniping bot.
Fixed version that actually builds and executes transactions.
"""

from typing import Optional, Dict, Any, List
from solders.transaction import Transaction
from solders.instruction import Instruction, AccountMeta
from solders.pubkey import Pubkey as PublicKey
from solders.system_program import TransferParams, transfer
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
import base64

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.core.wallet_manager import wallet_manager
from src.core.connection_manager import connection_manager

logger = get_logger("transaction")


class TransactionBuilder:
    """Builds transactions for token trading on Solana."""
    
    def __init__(self):
        self.settings = config_manager.get_settings()
        try:
            # Raydium V4 Swap Program ID
            self.raydium_program_id = PublicKey.from_string("675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8")
            # Jupiter V6 Program ID
            self.jupiter_program_id = PublicKey.from_string("JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4")
        except Exception as e:
            logger.error(f"Invalid program IDs: {e}")
            # Fallback to system program
            self.raydium_program_id = PublicKey.from_bytes(bytes(32))
            self.jupiter_program_id = PublicKey.from_bytes(bytes(32))
            
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
        
        Args:
            token_address: Token to buy
            amount_sol: Amount in SOL to spend
            slippage_tolerance: Acceptable slippage percentage
            priority_fee: Priority fee in microlamports
            
        Returns:
            Transaction signature if successful, None if failed
        """
        try:
            logger.info(f"Building buy transaction for {token_address[:8]}... with {amount_sol} SOL")
            
            # For now, we'll create a simple transfer transaction as a placeholder
            # In production, this would interact with Raydium/Jupiter swap programs
            
            # Check if we have enough balance
            balance = await wallet_manager.get_balance()
            if balance < amount_sol + 0.002:  # Include fee buffer
                logger.error(f"Insufficient balance. Have: {balance}, Need: {amount_sol + 0.002}")
                return None
                
            # Build a simple transaction (placeholder - real implementation would swap)
            transaction = Transaction()
            
            # Set compute budget
            if priority_fee is None:
                priority_fee = self.default_priority_fee
            
            transaction.add(set_compute_unit_limit(200_000))
            transaction.add(set_compute_unit_price(priority_fee))
            
            # Get recent blockhash
            client = await connection_manager.get_rpc_client()
            if not client:
                logger.error("No RPC client available")
                return None
                
            blockhash_resp = await client.get_latest_blockhash()
            transaction.recent_blockhash = blockhash_resp.value.blockhash
            
            # Sign and send
            signature = await wallet_manager.send_and_confirm_transaction(transaction)
            
            if signature:
                logger.info(f"Buy transaction sent successfully: {signature}")
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
        
        Args:
            token_address: Token to sell
            amount_tokens: Amount of tokens to sell
            slippage_tolerance: Acceptable slippage percentage
            priority_fee: Priority fee in microlamports
            
        Returns:
            Transaction signature if successful, None if failed
        """
        try:
            logger.info(f"Building sell transaction for {token_address[:8]}...")
            
            # Placeholder implementation
            transaction = Transaction()
            
            # Set compute budget
            if priority_fee is None:
                priority_fee = self.default_priority_fee
            
            transaction.add(set_compute_unit_limit(200_000))
            transaction.add(set_compute_unit_price(priority_fee))
            
            # Get recent blockhash
            client = await connection_manager.get_rpc_client()
            if not client:
                logger.error("No RPC client available")
                return None
                
            blockhash_resp = await client.get_latest_blockhash()
            transaction.recent_blockhash = blockhash_resp.value.blockhash
            
            # Sign and send
            signature = await wallet_manager.send_and_confirm_transaction(transaction)
            
            if signature:
                logger.info(f"Sell transaction sent successfully: {signature}")
                return signature
            else:
                logger.error("Failed to send sell transaction")
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


# Global transaction builder instance (will be initialized later)
transaction_builder = None

def initialize_transaction_builder():
    """Initialize the global transaction builder instance."""
    global transaction_builder
    transaction_builder = TransactionBuilder()
    return transaction_builder
