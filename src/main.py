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
