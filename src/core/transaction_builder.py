"""
Transaction builder for the Solana pump.fun sniping bot.
Fixed version with proper async transaction execution.
"""

from typing import Optional, Dict, Any, List
from solders.transaction import Transaction
from solders.instruction import Instruction, AccountMeta
from solders.pubkey import Pubkey as PublicKey
from solders.system_program import TransferParams, transfer
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
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
        try:
            # Attempt to create PublicKey from string or fallback to zero bytes
            program_id_str = self.settings.pump_fun.program_id
            if isinstance(program_id_str, str):
                self.pump_program_id = PublicKey.from_string(program_id_str)
            else:
                raise ValueError("Program ID is not a string")
        except Exception as e:
            logger.error(f"Invalid pump program ID: {e}")
            # Fallback to a valid zero public key (system program ID)
            self.pump_program_id = PublicKey.from_bytes(bytes(32))
        try:
            program_id_str = self.settings.raydium.program_id
            if isinstance(program_id_str, str):
                self.raydium_program_id = PublicKey.from_string(program_id_str)
            else:
                raise ValueError("Program ID is not a string")
        except Exception as e:
            logger.error(f"Invalid Raydium program ID: {e}")
            # Fallback to a valid zero public key (system program ID)
            self.raydium_program_id = PublicKey.from_bytes(bytes(32))
        self.default_priority_fee = 100_000  # Default priority fee in microlamports
        
    async def build_buy_transaction(
        self,
        token_address: str,
        amount_sol: float,
        slippage_tolerance: float = 0.1,
        priority_fee: Optional[int] = None
    ) -> Optional[Transaction]:
        """
        Build a transaction to buy a token on pump.fun or Raydium.
        
        Args:
            token_address: Token to buy
            amount_sol: Amount in SOL to spend
            slippage_tolerance: Acceptable slippage percentage
            priority_fee: Priority fee in microlamports
            
        Returns:
            Transaction object or None if failed
        """
        try:
            if not wallet_manager.get_public_key():
                raise ValueError("Wallet not initialized")
            
            transaction = Transaction()
            
            # Set compute budget and priority fee
            if priority_fee is None:
                priority_fee = self.default_priority_fee
            
            transaction.add(set_compute_unit_limit(800_000))
            transaction.add(set_compute_unit_price(priority_fee))
            
            # Convert SOL to lamports
            amount_lamports = int(amount_sol * 1_000_000_000)
            
            # For pump.fun tokens, we need to interact with the bonding curve
            # This is a placeholder - actual implementation would depend on pump.fun's program
            token_pubkey = PublicKey(token_address)
            wallet_pubkey = wallet_manager.get_public_key()
            
            # Placeholder instruction - would need actual pump.fun program data
            buy_instruction = Instruction(
                program_id=self.pump_program_id,
                accounts=[
                    AccountMeta(pubkey=wallet_pubkey, is_signer=True, is_writable=True),
                    AccountMeta(pubkey=token_pubkey, is_signer=False, is_writable=True),
                ],
                data=b"buy" + amount_lamports.to_bytes(8, byteorder="little")
            )
            
            transaction.add(buy_instruction)
            
            # Set recent blockhash
            client = await connection_manager.get_rpc_client()
            if client:
                blockhash_resp = await client.get_latest_blockhash()
                transaction.recent_blockhash = blockhash_resp.value.blockhash
            
            logger.info(f"Built buy transaction for {token_address[:8]}... with {amount_sol} SOL")
            return transaction
            
        except Exception as e:
            logger.error(f"Failed to build buy transaction for {token_address}: {e}")
            return None
    
    async def build_sell_transaction(
        self,
        token_address: str,
        amount_tokens: float,
        slippage_tolerance: float = 0.1,
        priority_fee: Optional[int] = None
    ) -> Optional[Transaction]:
        """
        Build a transaction to sell a token on Raydium.
        
        Args:
            token_address: Token to sell
            amount_tokens: Amount of tokens to sell (0 for all)
            slippage_tolerance: Acceptable slippage percentage
            priority_fee: Priority fee in microlamports
            
        Returns:
            Transaction object or None if failed
        """
        try:
            if not wallet_manager.get_public_key():
                raise ValueError("Wallet not initialized")
            
            transaction = Transaction()
            
            # Set compute budget and priority fee
            if priority_fee is None:
                priority_fee = self.default_priority_fee
            
            transaction.add(set_compute_unit_limit(800_000))
            transaction.add(set_compute_unit_price(priority_fee))
            
            # If amount_tokens is 0, sell all available tokens
            if amount_tokens == 0:
                amount_tokens = await wallet_manager.get_token_balance(token_address)
                if amount_tokens == 0:
                    logger.error(f"No tokens available to sell for {token_address}")
                    return None
            
            # Convert token amount to smallest unit (assuming 9 decimals for most tokens)
            amount_units = int(amount_tokens * 1_000_000_000)
            
            token_pubkey = PublicKey(token_address)
            wallet_pubkey = wallet_manager.get_public_key()
            
            # Placeholder instruction for Raydium swap (SOL for token)
            sell_instruction = Instruction(
                program_id=self.raydium_program_id,
                accounts=[
                    AccountMeta(pubkey=wallet_pubkey, is_signer=True, is_writable=True),
                    AccountMeta(pubkey=token_pubkey, is_signer=False, is_writable=True),
                ],
                data=b"sell" + amount_units.to_bytes(8, byteorder="little")
            )
            
            transaction.add(sell_instruction)
            
            # Set recent blockhash
            client = await connection_manager.get_rpc_client()
            if client:
                blockhash_resp = await client.get_latest_blockhash()
                transaction.recent_blockhash = blockhash_resp.value.blockhash
            
            logger.info(f"Built sell transaction for {token_address[:8]}... with amount {amount_tokens}")
            return transaction
            
        except Exception as e:
            logger.error(f"Failed to build sell transaction for {token_address}: {e}")
            return None
    
    async def build_transfer_transaction(
        self,
        recipient_address: str,
        amount_sol: float
    ) -> Optional[Transaction]:
        """
        Build a simple SOL transfer transaction.
        
        Args:
            recipient_address: Recipient address
            amount_sol: Amount in SOL to transfer
            
        Returns:
            Transaction object or None if failed
        """
        try:
            if not wallet_manager.get_public_key():
                raise ValueError("Wallet not initialized")
            
            transaction = Transaction()
            
            # Convert SOL to lamports
            amount_lamports = int(amount_sol * 1_000_000_000)
            
            # Build transfer instruction
            transfer_params = TransferParams(
                from_pubkey=wallet_manager.get_public_key(),
                to_pubkey=PublicKey(recipient_address),
                lamports=amount_lamports
            )
            transfer_instruction = transfer(transfer_params)
            transaction.add(transfer_instruction)
            
            # Set recent blockhash
            client = await connection_manager.get_rpc_client()
            if client:
                blockhash_resp = await client.get_latest_blockhash()
                transaction.recent_blockhash = blockhash_resp.value.blockhash
            
            logger.info(f"Built transfer transaction of {amount_sol} SOL to {recipient_address[:8]}...")
            return transaction
            
        except Exception as e:
            logger.error(f"Failed to build transfer transaction to {recipient_address}: {e}")
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
    
    async def estimate_transaction_cost(
        self,
        transaction: Transaction
    ) -> Optional[int]:
        """
        Estimate the cost of a transaction in lamports.
        
        Args:
            transaction: Transaction to estimate
            
        Returns:
            Estimated cost in lamports or None if failed
        """
        try:
            client = await connection_manager.get_rpc_client()
            if not client:
                raise ValueError("No RPC client available")
            
            # Sign the transaction temporarily for estimation
            signed_tx = await wallet_manager.sign_transaction(transaction)
            
            response = await client.get_fee_for_message(signed_tx.message)
            if response.value is not None:
                return response.value
            
            logger.warning("Could not estimate transaction cost")
            return None
            
        except Exception as e:
            logger.error(f"Failed to estimate transaction cost: {e}")
            return None
    
    async def build_and_execute_buy_transaction(
        self,
        token_address: str,
        amount_sol: float
    ) -> Optional[str]:
        """
        Build and execute a buy transaction.
        
        Args:
            token_address: Token to buy
            amount_sol: Amount in SOL to spend
            
        Returns:
            Transaction signature if successful, None otherwise
        """
        try:
            logger.info(f"Building and executing buy transaction for {token_address[:8]}...")
            
            # Build the transaction
            tx = await self.build_buy_transaction(token_address, amount_sol)
            if not tx:
                logger.error("Failed to build buy transaction")
                return None
            
            # Send and confirm transaction
            signature = await wallet_manager.send_and_confirm_transaction(tx)
            
            if signature:
                logger.info(f"Buy transaction executed successfully: {signature}")
                return signature
            else:
                logger.error("Buy transaction failed to confirm")
                return None
                
        except Exception as e:
            logger.error(f"Error executing buy transaction: {e}")
            return None
    
    async def build_and_execute_sell_transaction(
        self,
        token_address: str,
        amount_tokens: float
    ) -> Optional[str]:
        """
        Build and execute a sell transaction.
        
        Args:
            token_address: Token to sell
            amount_tokens: Amount of tokens to sell
            
        Returns:
            Transaction signature if successful, None otherwise
        """
        try:
            logger.info(f"Building and executing sell transaction for {token_address[:8]}...")
            
            # Build the transaction
            tx = await self.build_sell_transaction(token_address, amount_tokens)
            if not tx:
                logger.error("Failed to build sell transaction")
                return None
            
            # Send and confirm transaction
            signature = await wallet_manager.send_and_confirm_transaction(tx)
            
            if signature:
                logger.info(f"Sell transaction executed successfully: {signature}")
                return signature
            else:
                logger.error("Sell transaction failed to confirm")
                return None
                
        except Exception as e:
            logger.error(f"Error executing sell transaction: {e}")
            return None


# Global transaction builder instance (will be initialized later)
transaction_builder = None

def initialize_transaction_builder():
    """Initialize the global transaction builder instance."""
    global transaction_builder
    transaction_builder = TransactionBuilder()
    return transaction_builder
