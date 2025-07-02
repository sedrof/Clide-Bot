#!/usr/bin/env python3

import os
import sys
import shutil
from pathlib import Path

def backup_file(filepath):
    """Create a backup of the file before modifying."""
    backup_path = f"{filepath}.backup_{os.getpid()}"
    if os.path.exists(filepath):
        shutil.copy2(filepath, backup_path)
        print(f"✓ Backed up: {filepath}")
    return backup_path

def write_file(filepath, content):
    """Write content to file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Updated: {filepath}")

def fix_wallet_manager():
    """Fix the wallet manager to ensure proper initialization."""
    content = '''"""
Wallet management for the Solana pump.fun sniping bot.
Fixed to ensure proper initialization and instance creation.
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
import time

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
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize wallet manager with RPC client and load keypair."""
        if self._initialized:
            logger.info("Wallet manager already initialized")
            return
            
        # Import connection_manager here to avoid circular imports
        from src.core.connection_manager import connection_manager
        
        logger.info("Initializing wallet manager...")
        
        # Get RPC client from connection manager
        self.client = await connection_manager.get_rpc_client()
        if not self.client:
            raise RuntimeError("No RPC client available from connection manager")
            
        # Load keypair
        await self.load_keypair()
        
        # Validate wallet
        await self.validate_wallet()
        
        self._initialized = True
        logger.info(f"Wallet manager initialized successfully | public_key={str(self.public_key)}")
    
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
                    f"Public key mismatch | config_key={wallet_config.public_key} | derived_key={str(self.public_key)}"
                )
            
            logger.info(f"Keypair loaded successfully | public_key={str(self.public_key)}")
            
        except Exception as e:
            logger.error(f"Failed to load keypair: {e}")
            raise
    
    async def get_balance(self, force_refresh: bool = False) -> float:
        """
        Get SOL balance for the wallet.
        
        Args:
            force_refresh: Force refresh balance from chain
            
        Returns:
            SOL balance as float
        """
        try:
            # Check cache
            current_time = time.time()
            if not force_refresh and self._balance_cache is not None:
                if current_time - self._last_balance_check < self.balance_cache_duration:
                    return self._balance_cache
            
            if not self.client or not self.public_key:
                raise ValueError("Wallet not initialized")
            
            # Get balance from chain
            response = await self.client.get_balance(self.public_key)
            balance_lamports = response.value
            balance_sol = balance_lamports / 1e9  # Convert lamports to SOL
            
            # Update cache
            self._balance_cache = balance_sol
            self._last_balance_check = current_time
            
            logger.debug(f"Balance refreshed: {balance_sol:.6f} SOL")
            return balance_sol
            
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            # Return cached balance if available
            if self._balance_cache is not None:
                return self._balance_cache
            raise
    
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
            
            # Get recent blockhash if not set
            if not transaction.recent_blockhash:
                if not self.client:
                    raise ValueError("Client not initialized")
                response = await self.client.get_latest_blockhash()
                transaction.recent_blockhash = response.value.blockhash
            
            # Sign the transaction
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
        Send a signed transaction.
        
        Args:
            transaction: Signed transaction to send
            opts: Transaction options
            
        Returns:
            Transaction signature
        """
        try:
            if not self.client:
                raise ValueError("Client not initialized")
            
            if opts is None:
                opts = TxOpts(skip_preflight=False, preflight_commitment=Commitment("confirmed"))
            
            # Send transaction
            response = await self.client.send_raw_transaction(transaction.serialize(), opts)
            signature = str(response.value)
            
            logger.info(f"Transaction sent | signature={signature}")
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
                        logger.info(f"Transaction confirmed | signature={signature}")
                        return True
                    
                    if status.err:
                        logger.error(f"Transaction failed | signature={signature} | error={status.err}")
                        return False
                
                # Check timeout
                if asyncio.get_event_loop().time() - start_time > timeout:
                    logger.warning(f"Transaction confirmation timeout | signature={signature}")
                    return False
                
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Failed to confirm transaction {signature}: {e}")
            return False
    
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
            
            logger.info(f"Wallet validation passed | balance={balance:.6f} SOL")
            return True
            
        except Exception as e:
            logger.error(f"Wallet validation failed: {e}")
            return False
    
    def get_public_key(self) -> Optional[PublicKey]:
        """Get wallet public key."""
        return self.public_key
    
    def get_keypair(self) -> Optional[Keypair]:
        """Get wallet keypair (use with caution)."""
        return self.keypair


# Create a function to get the wallet manager instance
_wallet_manager_instance = None

def get_wallet_manager() -> WalletManager:
    """Get or create the global wallet manager instance."""
    global _wallet_manager_instance
    if _wallet_manager_instance is None:
        _wallet_manager_instance = WalletManager()
    return _wallet_manager_instance


# For backward compatibility
wallet_manager = get_wallet_manager()
'''
    write_file('src/core/wallet_manager.py', content)

def fix_main_py():
    """Fix main.py to properly handle wallet manager initialization."""
    content = '''"""
Main entry point for the Solana pump.fun sniping bot.
Fixed to properly initialize all components.
"""
# File Location: src/main.py

import asyncio
import signal
import sys
from typing import Optional
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging FIRST
from src.utils.logger import setup_logging

# Initialize logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)
setup_logging(
    level="INFO",
    file_path=os.path.join(log_dir, "pump_bot.log"),
    max_file_size_mb=10,
    backup_count=5,
    console_output=True
)

# Now import everything else
from src.utils.config import config_manager
from src.utils.logger import get_logger

logger = get_logger("main")

# Global shutdown flag
shutdown_event = asyncio.Event()


async def start_bot():
    """Start the Solana pump.fun sniping bot with all components."""
    try:
        logger.info("="*60)
        logger.info("Starting Solana pump.fun sniping bot")
        logger.info("="*60)
        
        # Load configurations FIRST
        config_manager.load_all()
        logger.info("Configurations loaded successfully")
        
        # Import and initialize components AFTER config is loaded
        from src.core.connection_manager import connection_manager
        from src.core.wallet_manager import get_wallet_manager
        from src.trading.strategy_engine import initialize_strategy_engine
        from src.core.transaction_builder import initialize_transaction_builder
        from src.monitoring.pump_monitor import initialize_pump_monitor
        from src.monitoring.price_tracker import initialize_price_tracker
        from src.monitoring.volume_analyzer import initialize_volume_analyzer
        from src.monitoring.wallet_tracker import initialize_wallet_tracker
        from src.monitoring.event_processor import initialize_event_processor
        from src.ui.cli import initialize_bot_cli
        
        # Initialize components in order
        logger.info("Initializing components...")
        
        # Core components
        strategy_engine = initialize_strategy_engine()
        logger.info("✓ Strategy engine initialized")
        
        transaction_builder = initialize_transaction_builder()
        logger.info("✓ Transaction builder initialized")
        
        # Initialize connection manager
        await connection_manager.initialize()
        logger.info("✓ Connection manager initialized")
        
        # Initialize wallet manager
        wallet_manager = get_wallet_manager()
        await wallet_manager.initialize()
        balance = await wallet_manager.get_balance()
        logger.info(f"✓ Wallet initialized. Address: {wallet_manager.get_public_key()}, Balance: {balance:.6f} SOL")
        
        # Initialize monitors
        pump_monitor = initialize_pump_monitor()
        logger.info("✓ Pump monitor initialized")
        
        price_tracker = initialize_price_tracker()
        logger.info("✓ Price tracker initialized")
        
        volume_analyzer = initialize_volume_analyzer()
        logger.info("✓ Volume analyzer initialized")
        
        wallet_tracker = initialize_wallet_tracker()
        logger.info("✓ Wallet tracker initialized")
        
        event_processor = initialize_event_processor()
        logger.info("✓ Event processor initialized")
        
        # Initialize UI
        bot_cli = initialize_bot_cli()
        logger.info("✓ CLI interface initialized")
        
        # Start all monitoring components
        logger.info("Starting monitoring components...")
        
        await pump_monitor.start()
        logger.info("✓ Pump monitor started")
        
        await price_tracker.start()
        logger.info("✓ Price tracker started")
        
        await volume_analyzer.start()
        logger.info("✓ Volume analyzer started")
        
        await wallet_tracker.start()
        logger.info("✓ Wallet tracker started")
        
        # Start strategy engine
        await strategy_engine.start()
        logger.info("✓ Strategy engine started")
        
        # Start CLI interface
        logger.info("="*60)
        logger.info("Bot started successfully! Monitoring for opportunities...")
        logger.info("="*60)
        
        await bot_cli.run()
        
    except Exception as e:
        logger.error(f"Error starting bot: {e} | exc_info=True | error_count=1", exc_info=True)
        raise


async def stop_bot():
    """Stop all bot components gracefully."""
    logger.info("Stopping Solana pump.fun sniping bot")
    
    try:
        # Import components
        from src.trading.strategy_engine import strategy_engine
        from src.monitoring.pump_monitor import pump_monitor
        from src.monitoring.price_tracker import price_tracker
        from src.monitoring.volume_analyzer import volume_analyzer
        from src.monitoring.wallet_tracker import wallet_tracker
        from src.ui.cli import bot_cli
        from src.core.connection_manager import connection_manager
        
        # Stop UI first
        if bot_cli:
            bot_cli.stop()
            logger.info("✓ CLI interface stopped")
        
        # Stop monitoring components
        if wallet_tracker:
            await wallet_tracker.stop()
            logger.info("✓ Wallet tracker stopped")
        
        if volume_analyzer:
            await volume_analyzer.stop()
            logger.info("✓ Volume analyzer stopped")
        
        if price_tracker:
            await price_tracker.stop()
            logger.info("✓ Price tracker stopped")
        
        if pump_monitor:
            await pump_monitor.stop()
            logger.info("✓ Pump monitor stopped")
        
        # Stop strategy engine
        if strategy_engine:
            await strategy_engine.stop()
            logger.info("✓ Strategy engine stopped")
        
        # Close connections
        if connection_manager:
            await connection_manager.close()
            logger.info("✓ Connections closed")
        
        logger.info("Bot stopped successfully")
        
    except Exception as e:
        logger.error(f"Error stopping bot: {e}", exc_info=True)


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    logger.info(f"Received shutdown signal: {sig}")
    shutdown_event.set()


async def main():
    """Main entry point."""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start the bot
        bot_task = asyncio.create_task(start_bot())
        
        # Wait for shutdown signal
        await shutdown_event.wait()
        
        # Stop the bot
        await stop_bot()
        
        # Cancel the bot task if still running
        if not bot_task.done():
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await stop_bot()
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}", exc_info=True)
        await stop_bot()
        sys.exit(1)


if __name__ == "__main__":
    # Run the bot
    print("🚀 Starting Solana Pump.fun Sniping Bot...")
    print(f"📁 Log file: logs/pump_bot.log")
    print("Press Ctrl+C to stop\\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n👋 Bot terminated by user")
    except Exception as e:
        print(f"\\n❌ Fatal error: {e}")
        sys.exit(1)
'''
    write_file('src/main.py', content)

def main():
    """Apply the wallet manager fix."""
    print("="*60)
    print("🔧 Wallet Manager Initialization Fix")
    print("="*60)
    print()
    
    # Check we're in the right directory
    if not os.path.exists('src/main.py'):
        print("❌ ERROR: This script must be run from the project root directory")
        print("   Please cd to C:\\Users\\JJ\\Desktop\\Clide-Bot and run again")
        return 1
    
    print("📁 Working directory:", os.getcwd())
    print()
    
    try:
        print("Applying fixes...")
        print()
        
        # Backup and fix files
        backup_file('src/core/wallet_manager.py')
        fix_wallet_manager()
        
        backup_file('src/main.py')
        fix_main_py()
        
        print()
        print("="*60)
        print("✅ Wallet manager fix applied successfully!")
        print("="*60)
        print()
        print("📋 What was fixed:")
        print()
        print("1. ✅ Wallet Manager:")
        print("   - Added proper instance creation with get_wallet_manager()")
        print("   - Added initialization check to prevent double init")
        print("   - Improved error handling and logging")
        print("   - Fixed circular import issues")
        print()
        print("2. ✅ Main.py:")
        print("   - Fixed wallet manager import and initialization")
        print("   - Added proper error handling")
        print("   - Improved component initialization order")
        print()
        print("🚀 To run the bot:")
        print("   python -m src.main")
        print()
        print("📊 Expected results:")
        print("   - RPC connection will succeed ✓")
        print("   - Wallet manager will initialize properly ✓")
        print("   - Bot will start monitoring ✓")
        print("   - CLI interface will appear ✓")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error applying fix: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())