"""
Main entry point for the Solana pump.fun sniping bot.
Initializes and coordinates all bot components.
"""
# File Location: src/main.py

import asyncio
import signal
import sys
from typing import Optional
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# CRITICAL: Setup logging FIRST before any imports that use logging
from src.utils.logger import setup_logging

# Initialize logging immediately
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)
setup_logging(
    level="INFO",  # Set to INFO for production, DEBUG for troubleshooting
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
        from src.core.wallet_manager import wallet_manager
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
        
        await connection_manager.initialize()
        logger.info("✓ Connection manager initialized")
        
        await wallet_manager.initialize()
        balance = await wallet_manager.get_balance()
        logger.info(f"✓ Wallet initialized. Balance: {balance:.6f} SOL")
        
        # Monitoring components
        pump_monitor = initialize_pump_monitor()
        price_tracker = initialize_price_tracker()
        volume_analyzer = initialize_volume_analyzer()
        wallet_tracker = initialize_wallet_tracker()
        logger.info("✓ Monitoring components initialized")
        
        # Event processor
        event_processor = initialize_event_processor()
        logger.info("✓ Event processor initialized")
        
        # UI
        bot_cli = initialize_bot_cli()
        logger.info("✓ CLI UI initialized")
        
        # Import components to ensure they're available
        from src.trading.strategy_engine import strategy_engine
        from src.monitoring.event_processor import event_processor
        from src.monitoring.pump_monitor import pump_monitor
        from src.monitoring.price_tracker import price_tracker
        from src.monitoring.volume_analyzer import volume_analyzer
        from src.monitoring.wallet_tracker import wallet_tracker
        from src.ui.cli import bot_cli
        
        # Register callbacks
        logger.info("Registering callbacks...")
        
        if event_processor and strategy_engine:
            event_processor.register_new_token_callback(strategy_engine.evaluate_new_token)
            event_processor.register_price_update_callback(strategy_engine.evaluate_price_update)
            event_processor.register_volume_spike_callback(strategy_engine.evaluate_volume_spike)
            logger.info("✓ Event callbacks registered")
        
        # Start all monitoring components
        logger.info("Starting monitoring components...")
        
        if pump_monitor:
            await pump_monitor.start()
            logger.info("✓ Pump monitor started")
            
        if price_tracker:
            await price_tracker.start()
            logger.info("✓ Price tracker started")
            
        if volume_analyzer:
            await volume_analyzer.start()
            logger.info("✓ Volume analyzer started")
            
        if wallet_tracker:
            await wallet_tracker.start()
            logger.info("✓ Wallet tracker started")
            tracked_wallets = list(wallet_tracker.tracked_wallets)
            logger.info(f"  Tracking {len(tracked_wallets)} wallet(s): {tracked_wallets}")
            
        if event_processor:
            await event_processor.start()
            logger.info("✓ Event processor started")
        
        # Start strategy engine
        if strategy_engine:
            await strategy_engine.start()
            logger.info("✓ Strategy engine started")
        
        logger.info("="*60)
        logger.info("Bot started successfully! Monitoring for transactions...")
        logger.info("="*60)
        
        # Start UI (this will block until stopped)
        if bot_cli:
            await bot_cli.start()
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        raise


async def stop_bot():
    """Stop the bot gracefully."""
    try:
        logger.info("="*60)
        logger.info("Stopping Solana pump.fun sniping bot...")
        
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
        except ImportError as e:
            logger.warning(f"Some components could not be imported for shutdown: {e}")
        
        # Stop components in reverse order
        components = [
            ("UI", 'bot_cli'),
            ("Strategy Engine", 'strategy_engine'),
            ("Event Processor", 'event_processor'),
            ("Wallet Tracker", 'wallet_tracker'),
            ("Volume Analyzer", 'volume_analyzer'),
            ("Price Tracker", 'price_tracker'),
            ("Pump Monitor", 'pump_monitor'),
            ("Connection Manager", 'connection_manager')
        ]
        
        for name, var_name in components:
            try:
                if var_name in locals():
                    component = locals()[var_name]
                    if component:
                        if var_name == 'bot_cli':
                            component.stop()
                        elif var_name == 'connection_manager':
                            await component.close()
                        else:
                            await component.stop()
                        logger.info(f"✓ {name} stopped")
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")
        
        logger.info("Bot stopped successfully")
        logger.info("="*60)
        
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
    print("Press Ctrl+C to stop\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot terminated by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
