"""
Main application for the Solana pump.fun sniping bot.
Coordinates all components and manages bot lifecycle.
"""
# File Location: src/main.py

import asyncio
import sys
import signal
from typing import Optional

from src.utils.config import config_manager
from src.utils.logger import setup_logging, main_logger
from src.core.connection_manager import connection_manager
from src.core.wallet_manager import wallet_manager
from src.monitoring.pump_monitor import pump_monitor
from src.monitoring.price_tracker import price_tracker
from src.monitoring.volume_analyzer import volume_analyzer
from src.monitoring.event_processor import event_processor
from src.monitoring.wallet_tracker import wallet_tracker
from src.trading.strategy_engine import strategy_engine


class PumpBot:
    """Main bot class coordinating all components."""
    
    def __init__(self):
        self.running: bool = False
        self.global_pump_monitor = None
        self.global_price_tracker = None
        self.global_volume_analyzer = None
        self.global_event_processor = None
        self.global_wallet_tracker = None
        self.global_strategy_engine = None
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._signal_handler)
    
    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        main_logger.info(f"Received shutdown signal: {signum}")
        asyncio.create_task(self.stop())
    
    async def start(self) -> None:
        """Start the bot and all components."""
        if self.running:
            main_logger.warning("Bot already running")
            return
            
        self.running = True
        main_logger.info("Starting Solana pump.fun sniping bot")
        
        try:
            # Load configuration first
            config_manager.load_all()
            
            # Setup logging
            log_config = config_manager.get_settings().logging
            setup_logging(
                level=log_config.level,
                file_path=log_config.file_path,
                max_file_size_mb=log_config.max_file_size_mb,
                backup_count=log_config.backup_count,
                console_output=log_config.console_output
            )
            
            # Validate configuration
            if not config_manager.validate_configuration():
                main_logger.error("Configuration validation failed. Exiting.")
                sys.exit(1)
            
            # Initialize connection manager
            await connection_manager.initialize()
            
            # Get RPC client
            client = await connection_manager.get_rpc_client()
            if not client:
                main_logger.error("Failed to connect to any Solana RPC endpoint. Exiting.")
                sys.exit(1)
            
            # Initialize wallet manager
            await wallet_manager.initialize(client)
            
            # Validate wallet
            if not await wallet_manager.validate_wallet():
                main_logger.error("Wallet validation failed. Please check configuration and balance.")
                sys.exit(1)
            
            # Initialize components and get their instances
            from src.monitoring.pump_monitor import initialize_pump_monitor
            from src.monitoring.price_tracker import initialize_price_tracker
            from src.monitoring.volume_analyzer import initialize_volume_analyzer
            from src.monitoring.event_processor import initialize_event_processor
            from src.monitoring.wallet_tracker import initialize_wallet_tracker
            from src.trading.strategy_engine import initialize_strategy_engine
            
            self.global_pump_monitor = initialize_pump_monitor()
            self.global_price_tracker = initialize_price_tracker()
            self.global_volume_analyzer = initialize_volume_analyzer()
            self.global_event_processor = initialize_event_processor()
            self.global_wallet_tracker = initialize_wallet_tracker()
            self.global_strategy_engine = initialize_strategy_engine()
            from src.core.transaction_builder import initialize_transaction_builder
            initialize_transaction_builder()
            
            # Ensure all components are initialized before starting
            if self.global_pump_monitor and self.global_price_tracker and self.global_volume_analyzer and self.global_event_processor and self.global_wallet_tracker and self.global_strategy_engine:
                # Start monitoring components after initialization
                await self.global_pump_monitor.start()
                await self.global_price_tracker.start()
                await self.global_volume_analyzer.start()
                await self.global_event_processor.start()
                await self.global_wallet_tracker.start()
                await self.global_strategy_engine.start()
            else:
                main_logger.error("One or more components failed to initialize. Exiting.")
                sys.exit(1)
            
            main_logger.info("Solana pump.fun sniping bot started successfully")
            
            # Keep running
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            main_logger.error(f"Error starting bot: {e}", exc_info=True)
            await self.stop()
            sys.exit(1)
    
    async def stop(self) -> None:
        """Stop the bot and all components."""
        if not self.running:
            main_logger.warning("Bot already stopped")
            return
            
        self.running = False
        main_logger.info("Stopping Solana pump.fun sniping bot")
        
        try:
            # Stop all components using the class attributes
            if self.global_strategy_engine:
                await self.global_strategy_engine.stop()
            if self.global_event_processor:
                await self.global_event_processor.stop()
            if self.global_volume_analyzer:
                await self.global_volume_analyzer.stop()
            if self.global_price_tracker:
                await self.global_price_tracker.stop()
            if self.global_wallet_tracker:
                await self.global_wallet_tracker.stop()
            if self.global_pump_monitor:
                await self.global_pump_monitor.stop()
            
            # Close connections
            await connection_manager.close()
            
            main_logger.info("Solana pump.fun sniping bot stopped successfully")
        except Exception as e:
            main_logger.error(f"Error stopping bot: {e}", exc_info=True)


async def main(ui_mode: bool = False) -> None:
    """Main entry point for the bot.
    
    Args:
        ui_mode: If True, run the bot with CLI UI.
    """
    # Load configuration FIRST, before anything else
    config_manager.load_all()
    
    bot = PumpBot()
    
    if ui_mode:
        from src.ui.cli import initialize_bot_cli
        cli = initialize_bot_cli()
        # Start UI in a separate task
        asyncio.create_task(cli.start())
        
    await bot.start()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Solana Pump.fun Sniper Bot")
    parser.add_argument("--ui", action="store_true", help="Run the bot with CLI UI")
    args = parser.parse_args()
    asyncio.run(main(ui_mode=args.ui))
