#!/usr/bin/env python3
"""
Patch script to fix all initialization issues in the Solana pump.fun sniping bot.
Run this from the project root: C:/Users/JJ/Desktop/Clide-Bot
Usage: python patch_bot.py
"""

import os
import shutil
from pathlib import Path

def backup_file(filepath):
    """Create a backup of the file before modifying."""
    backup_path = f"{filepath}.backup"
    if not os.path.exists(backup_path):
        shutil.copy2(filepath, backup_path)
        print(f"Backed up: {filepath}")

def write_file(filepath, content):
    """Write content to file with backup."""
    backup_file(filepath)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Updated: {filepath}")

def patch_event_processor():
    """Fix event_processor.py initialization issues."""
    content = '''"""
Event processor for the Solana pump.fun sniping bot.
Coordinates monitoring components and triggers strategy actions.
"""
# File Location: src/monitoring/event_processor.py

import asyncio
from typing import Dict, Any, Optional, Callable, List
import time

from src.utils.config import config_manager
from src.utils.logger import get_logger

logger = get_logger("event_processor")


class EventProcessor:
    """Coordinates monitoring components and processes events."""
    
    def __init__(self):
        self.settings = config_manager.get_settings()
        self.running: bool = False
        
        # Event callbacks
        self.new_token_callbacks: List[Callable] = []
        self.price_update_callbacks: List[Callable] = []
        self.volume_spike_callbacks: List[Callable] = []
        
        # Event tracking
        self.events_processed = 0
        self.last_event_time = time.time()
        
    async def start(self) -> None:
        """Start the event processor and register strategy callbacks."""
        if self.running:
            logger.warning("Event processor already running")
            return
            
        self.running = True
        logger.info("Starting event processor")
        
        # Register strategy engine with wallet tracker for copy trading
        # Import here to avoid circular import
        from src.trading.strategy_engine import strategy_engine
        from src.monitoring.wallet_tracker import wallet_tracker
        
        if strategy_engine and wallet_tracker:
            strategy_engine.register_with_wallet_tracker()
            logger.info("Registered strategy engine with wallet tracker for copy trading")
        
        # Register callbacks with monitoring components
        self._register_monitor_callbacks()
        
        # Start event processing loop
        asyncio.create_task(self._process_events())
    
    async def stop(self) -> None:
        """Stop the event processor."""
        self.running = False
        logger.info("Stopping event processor")
    
    def _register_monitor_callbacks(self) -> None:
        """Register callbacks with monitoring components."""
        from src.monitoring.pump_monitor import pump_monitor
        from src.monitoring.price_tracker import price_tracker
        from src.monitoring.volume_analyzer import volume_analyzer
        
        # Register with pump monitor for new tokens
        if pump_monitor:
            pump_monitor.register_new_token_callback(self._handle_new_token)
            logger.info("Registered new token callback with pump monitor")
        
        # Register with price tracker for price updates
        if price_tracker:
            price_tracker.register_price_update_callback(self._handle_price_update)
            logger.info("Registered price update callback with price tracker")
        
        # Register with volume analyzer for volume spikes
        if volume_analyzer:
            volume_analyzer.register_volume_spike_callback(self._handle_volume_spike)
            logger.info("Registered volume spike callback with volume analyzer")
    
    async def _process_events(self) -> None:
        """Main event processing loop."""
        while self.running:
            try:
                # Log status periodically
                if time.time() - self.last_event_time > 60:  # Every minute
                    logger.info(f"Event processor status: {self.events_processed} events processed")
                    self.last_event_time = time.time()
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in event processing loop: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def _handle_new_token(self, token_info) -> None:
        """Handle new token detection."""
        try:
            logger.info(
                f"Processing new token event: {token_info.symbol} ({token_info.address[:8]}...)",
                token=token_info.address
            )
            
            self.events_processed += 1
            
            # Notify all registered callbacks
            for callback in self.new_token_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(token_info)
                    else:
                        callback(token_info)
                except Exception as e:
                    logger.error(f"Error in new token callback: {e}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"Error handling new token event: {e}", exc_info=True)
    
    async def _handle_price_update(self, token_address: str, price: float, price_change_percent: float) -> None:
        """Handle price update event."""
        try:
            logger.debug(
                f"Processing price update: {token_address[:8]}... = {price:.6f} SOL ({price_change_percent:+.2f}%)",
                token=token_address
            )
            
            self.events_processed += 1
            
            # Notify all registered callbacks
            for callback in self.price_update_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(token_address, price, price_change_percent)
                    else:
                        callback(token_address, price, price_change_percent)
                except Exception as e:
                    logger.error(f"Error in price update callback: {e}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"Error handling price update event: {e}", exc_info=True)
    
    async def _handle_volume_spike(self, token_address: str, volume_spike_ratio: float) -> None:
        """Handle volume spike event."""
        try:
            logger.info(
                f"Processing volume spike: {token_address[:8]}... spike ratio = {volume_spike_ratio:.2f}x",
                token=token_address
            )
            
            self.events_processed += 1
            
            # Notify all registered callbacks
            for callback in self.volume_spike_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(token_address, volume_spike_ratio)
                    else:
                        callback(token_address, volume_spike_ratio)
                except Exception as e:
                    logger.error(f"Error in volume spike callback: {e}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"Error handling volume spike event: {e}", exc_info=True)
    
    def register_new_token_callback(self, callback) -> None:
        """Register callback for new token events."""
        self.new_token_callbacks.append(callback)
        logger.info(f"Registered new token callback. Total: {len(self.new_token_callbacks)}")
    
    def register_price_update_callback(self, callback) -> None:
        """Register callback for price update events."""
        self.price_update_callbacks.append(callback)
        logger.info(f"Registered price update callback. Total: {len(self.price_update_callbacks)}")
    
    def register_volume_spike_callback(self, callback) -> None:
        """Register callback for volume spike events."""
        self.volume_spike_callbacks.append(callback)
        logger.info(f"Registered volume spike callback. Total: {len(self.volume_spike_callbacks)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event processor statistics."""
        return {
            'events_processed': self.events_processed,
            'new_token_callbacks': len(self.new_token_callbacks),
            'price_update_callbacks': len(self.price_update_callbacks),
            'volume_spike_callbacks': len(self.volume_spike_callbacks),
            'is_running': self.running
        }


# Global event processor instance
event_processor = None

def initialize_event_processor():
    """Initialize the global event processor instance."""
    global event_processor
    event_processor = EventProcessor()
    logger.info("Event processor instance created")
    return event_processor
'''
    
    write_file('src/monitoring/event_processor.py', content)

def patch_main():
    """Fix main.py initialization order."""
    content = '''"""
Main entry point for the Solana pump.fun sniping bot.
Initializes and coordinates all bot components.
"""
# File Location: src/main.py

import asyncio
import signal
import sys
from typing import Optional

from src.utils.config import config_manager
from src.utils.logger import get_logger

logger = get_logger("main")

# Global shutdown flag
shutdown_event = asyncio.Event()


async def start_bot():
    """Start the Solana pump.fun sniping bot with all components."""
    try:
        logger.info("Starting Solana pump.fun sniping bot")
        
        # Load configurations FIRST
        config_manager.load_all()
        logger.info("Configurations loaded successfully")
        
        # Import and initialize components AFTER config is loaded
        from src.core.connection_manager import connection_manager
        from src.core.wallet_manager import wallet_manager
        from src.trading.strategy_engine import initialize_strategy_engine
        from src.core.transaction_builder import initialize_transaction_builder
        from src.monitoring.pump_monitor import initialize_pump_monitor
        from src.monitoring.price_tracker import initialize_price_tracker
        from src.monitoring.volume_analyzer import initialize_volume_analyzer
        from src.monitoring.wallet_tracker import initialize_wallet_tracker
        from src.monitoring.event_processor import initialize_event_processor
        from src.ui.cli import initialize_bot_cli
        
        # Initialize strategy engine
        strategy_engine = initialize_strategy_engine()
        logger.info("Strategy engine initialized")
        
        # Initialize transaction builder
        transaction_builder = initialize_transaction_builder()
        logger.info("Transaction builder initialized")
        
        # Initialize connection manager
        await connection_manager.initialize()
        logger.info("Connection manager initialized")
        
        # Initialize wallet manager
        await wallet_manager.initialize()
        balance = await wallet_manager.get_balance()
        logger.info(f"Wallet initialized. Balance: {balance} SOL")
        
        # Initialize UI
        bot_cli = initialize_bot_cli()
        logger.info("CLI UI initialized")
        
        # Initialize monitoring components
        pump_monitor = initialize_pump_monitor()
        price_tracker = initialize_price_tracker()
        volume_analyzer = initialize_volume_analyzer()
        wallet_tracker = initialize_wallet_tracker()
        logger.info("Monitoring components initialized")
        
        # Initialize event processor
        event_processor = initialize_event_processor()
        logger.info("Event processor initialized")
        
        # Import components again to ensure they're available
        from src.trading.strategy_engine import strategy_engine
        from src.monitoring.event_processor import event_processor
        from src.monitoring.pump_monitor import pump_monitor
        from src.monitoring.price_tracker import price_tracker
        from src.monitoring.volume_analyzer import volume_analyzer
        from src.monitoring.wallet_tracker import wallet_tracker
        from src.ui.cli import bot_cli
        
        # Register callbacks
        if event_processor and strategy_engine:
            event_processor.register_new_token_callback(strategy_engine.evaluate_new_token)
            event_processor.register_price_update_callback(strategy_engine.evaluate_price_update)
            event_processor.register_volume_spike_callback(strategy_engine.evaluate_volume_spike)
            logger.info("Event callbacks registered")
        else:
            logger.error("Failed to register callbacks: event_processor or strategy_engine is None")
        
        # Start all monitoring components
        if pump_monitor:
            await pump_monitor.start()
        if price_tracker:
            await price_tracker.start()
        if volume_analyzer:
            await volume_analyzer.start()
        if wallet_tracker:
            await wallet_tracker.start()
        if event_processor:
            await event_processor.start()
        logger.info("All monitoring components started")
        
        # Start strategy engine
        if strategy_engine:
            await strategy_engine.start()
            logger.info("Strategy engine started")
        
        # Start UI (this will block until stopped)
        logger.info("Solana pump.fun sniping bot started successfully")
        if bot_cli:
            await bot_cli.start()
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        raise


async def stop_bot():
    """Stop the bot gracefully."""
    try:
        logger.info("Stopping Solana pump.fun sniping bot")
        
        # Import components
        try:
            from src.trading.strategy_engine import strategy_engine
            from src.monitoring.event_processor import event_processor
            from src.monitoring.pump_monitor import pump_monitor
            from src.monitoring.price_tracker import price_tracker
            from src.monitoring.volume_analyzer import volume_analyzer
            from src.monitoring.wallet_tracker import wallet_tracker
            from src.ui.cli import bot_cli
            from src.core.connection_manager import connection_manager
        except ImportError:
            logger.warning("Some components could not be imported for shutdown")
        
        # Stop components in reverse order
        try:
            if 'strategy_engine' in locals() and strategy_engine:
                await strategy_engine.stop()
        except:
            pass
            
        try:
            if 'event_processor' in locals() and event_processor:
                await event_processor.stop()
        except:
            pass
        
        try:
            if 'pump_monitor' in locals() and pump_monitor:
                await pump_monitor.stop()
        except:
            pass
            
        try:
            if 'price_tracker' in locals() and price_tracker:
                await price_tracker.stop()
        except:
            pass
            
        try:
            if 'volume_analyzer' in locals() and volume_analyzer:
                await volume_analyzer.stop()
        except:
            pass
            
        try:
            if 'wallet_tracker' in locals() and wallet_tracker:
                await wallet_tracker.stop()
        except:
            pass
        
        try:
            if 'bot_cli' in locals() and bot_cli:
                bot_cli.stop()
        except:
            pass
        
        try:
            if 'connection_manager' in locals() and connection_manager:
                await connection_manager.close_all()
        except:
            pass
        
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
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
'''
    
    write_file('src/main.py', content)

def patch_wallet_manager():
    """Fix wallet_manager.py to not require client argument."""
    filepath = 'src/core/wallet_manager.py'
    
    # Read the current file
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found, skipping...")
        return
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if initialize method needs to be fixed
    if 'async def initialize(self, client)' in content or 'async def initialize(self, client:' in content:
        # Replace the initialize method signature
        print(f"Fixing initialize method in {filepath}")
        
        # Simple replacement - change the method signature
        import re
        
        # Pattern to match the initialize method signature
        pattern = r'async def initialize\(self,\s*client[^)]*\)\s*(?:->.*?)?:'
        replacement = 'async def initialize(self) -> None:'
        
        new_content = re.sub(pattern, replacement, content)
        
        # Also ensure it gets client from connection_manager
        if 'await connection_manager.get_rpc_client()' not in new_content:
            # Add the import if not present
            if 'from src.core.connection_manager import connection_manager' not in new_content:
                # Add import after other imports
                import_line = 'from src.core.connection_manager import connection_manager\n'
                
                # Find a good place to add the import
                lines = new_content.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith('from src.') and 'logger' in line:
                        lines.insert(i + 1, import_line)
                        break
                
                new_content = '\n'.join(lines)
            
            # Replace client assignment in initialize method
            new_content = re.sub(
                r'self\.client\s*=\s*client',
                '''self.client = await connection_manager.get_rpc_client()
        if not self.client:
            raise RuntimeError("No RPC client available from connection manager")''',
                new_content
            )
        
        write_file(filepath, new_content)
    else:
        print(f"{filepath} already has correct initialize signature")

def patch_transaction_builder():
    """Ensure transaction_builder uses lazy initialization."""
    filepath = 'src/core/transaction_builder.py'
    
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found, skipping...")
        return
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if it already has lazy initialization
    if 'def initialize_transaction_builder()' not in content:
        print(f"Adding lazy initialization to {filepath}")
        
        # Remove any direct instantiation at the end
        lines = content.split('\n')
        new_lines = []
        
        for line in lines:
            # Skip direct instantiation lines
            if line.strip() == 'transaction_builder = TransactionBuilder()':
                continue
            new_lines.append(line)
        
        # Add lazy initialization at the end
        lazy_init = '''
# Global transaction builder instance - lazy initialization
transaction_builder = None

def initialize_transaction_builder():
    """Initialize the global transaction builder instance."""
    global transaction_builder
    transaction_builder = TransactionBuilder()
    return transaction_builder
'''
        
        new_content = '\n'.join(new_lines) + '\n' + lazy_init
        write_file(filepath, new_content)
    else:
        print(f"{filepath} already has lazy initialization")

def main():
    """Run all patches."""
    print("=== Solana Pump.fun Sniping Bot Patch Script ===")
    print("This will fix all initialization issues in your bot")
    print()
    
    # Check we're in the right directory
    if not os.path.exists('src/main.py'):
        print("ERROR: This script must be run from the project root directory")
        print("Please cd to C:/Users/JJ/Desktop/Clide-Bot and run again")
        return
    
    print("Applying patches...")
    print()
    
    # Apply all patches
    patch_main()
    patch_event_processor()
    patch_wallet_manager()
    patch_transaction_builder()
    
    print()
    print("=== Patch Complete ===")
    print()
    print("The bot has been patched successfully!")
    print()
    print("To run the bot:")
    print("  python -m src.main")
    print()
    print("If you encounter any issues, restore from backups:")
    print("  - src/main.py.backup")
    print("  - src/monitoring/event_processor.py.backup")
    print("  - src/core/wallet_manager.py.backup")
    print("  - src/core/transaction_builder.py.backup")

if __name__ == "__main__":
    main()