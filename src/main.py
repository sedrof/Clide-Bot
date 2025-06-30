"""
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
from src.core.connection_manager import connection_manager
from src.core.wallet_manager import wallet_manager
from src.monitoring.pump_monitor import pump_monitor, initialize_pump_monitor
from src.monitoring.price_tracker import price_tracker, initialize_price_tracker
from src.monitoring.volume_analyzer import volume_analyzer, initialize_volume_analyzer
from src.monitoring.wallet_tracker import wallet_tracker, initialize_wallet_tracker
from src.monitoring.event_processor import event_processor, initialize_event_processor
from src.trading.strategy_engine import strategy_engine, initialize_strategy_engine
from src.ui.cli import bot_cli, initialize_bot_cli

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
        
        # Initialize strategy engine AFTER config is loaded
        initialize_strategy_engine()
        logger.info("Strategy engine initialized")
        
        # Initialize transaction builder if it uses lazy init
        try:
            from src.core.transaction_builder import initialize_transaction_builder
            initialize_transaction_builder()
            logger.info("Transaction builder initialized")
        except ImportError:
            # If no lazy init, assume it's already initialized
            pass
        
        # Initialize connection manager
        await connection_manager.initialize()
        logger.info("Connection manager initialized")
        
        # Initialize wallet manager with RPC client
        rpc_client = await connection_manager.get_rpc_client()
        if not rpc_client:
            raise RuntimeError("Failed to get RPC client")
        await wallet_manager.initialize(rpc_client)
        balance = await wallet_manager.get_balance()
        logger.info(f"Wallet initialized. Balance: {balance} SOL")
        
        # Initialize UI first so callbacks can be registered
        initialize_bot_cli()
        logger.info("CLI UI initialized")
        
        # Initialize monitoring components
        initialize_pump_monitor()
        initialize_price_tracker()
        initialize_volume_analyzer()
        initialize_wallet_tracker()
        logger.info("Monitoring components initialized")
        
        # Initialize event processor
        initialize_event_processor()
        logger.info("Event processor initialized")
        
        # Register callbacks before starting components
        event_processor.register_new_token_callback(strategy_engine.evaluate_new_token)
        event_processor.register_price_update_callback(strategy_engine.evaluate_price_update)
        event_processor.register_volume_spike_callback(strategy_engine.evaluate_volume_spike)
        logger.info("Event callbacks registered")
        
        # UI callbacks will be registered when UI starts
        logger.info("UI callbacks will be registered on start")
        
        # Start all monitoring components
        await pump_monitor.start()
        await price_tracker.start()
        await volume_analyzer.start()
        await wallet_tracker.start()  # Start wallet tracking
        await event_processor.start()
        logger.info("All monitoring components started")
        
        # Start strategy engine
        await strategy_engine.start()
        logger.info("Strategy engine started")
        
        # Start UI (this will block until stopped)
        logger.info("Solana pump.fun sniping bot started successfully")
        await bot_cli.start()
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        raise


async def stop_bot():
    """Stop the bot gracefully."""
    try:
        logger.info("Stopping Solana pump.fun sniping bot")
        
        # Stop strategy engine first
        if strategy_engine:
            await strategy_engine.stop()
        
        # Stop event processor
        if event_processor:
            await event_processor.stop()
        
        # Stop monitoring components
        if pump_monitor:
            await pump_monitor.stop()
        if price_tracker:
            await price_tracker.stop()
        if volume_analyzer:
            await volume_analyzer.stop()
        if wallet_tracker:
            await wallet_tracker.stop()
        
        # Stop UI
        if bot_cli:
            bot_cli.stop()
        
        # Close connections
        if connection_manager:
            await connection_manager.close_all()
        
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