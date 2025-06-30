"""
Event processor for the Solana pump.fun sniping bot.
Coordinates events from monitoring components and routes them to the strategy engine.
"""
# File Location: src/monitoring/event_processor.py

import asyncio
from typing import Dict, Any, Optional, Callable
from src.utils.logger import get_logger

logger = get_logger("event_processor")


class EventProcessor:
    """Processes events from various monitoring components and routes them to strategy engine."""
    
    def __init__(self):
        self.running = False
        self.new_token_queue = asyncio.Queue()
        self.price_update_queue = asyncio.Queue()
        self.volume_spike_queue = asyncio.Queue()
        self.buy_queue = asyncio.Queue()
        self.sell_queue = asyncio.Queue()
        self.create_queue = asyncio.Queue()
        
    async def start(self):
        """Start the event processor."""
        if self.running:
            logger.warning("Event processor already running")
            return
            
        self.running = True
        logger.info("Starting event processor")
        
        # Register callbacks with monitoring components
        await self._register_callbacks()
        
        # Start processing events
        asyncio.create_task(self._process_events())
        
    async def stop(self):
        """Stop the event processor."""
        self.running = False
        logger.info("Stopping event processor")
    
    async def _register_callbacks(self) -> None:
        """Register callbacks with monitoring components."""
        try:
            # Import components here to avoid circular imports
            from src.monitoring.pump_monitor import pump_monitor
            from src.monitoring.price_tracker import price_tracker
            from src.monitoring.volume_analyzer import volume_analyzer
            from src.monitoring.wallet_tracker import wallet_tracker
            
            # Register callback for new token detection
            if pump_monitor:
                pump_monitor.register_new_token_callback(self._on_new_token)
                logger.info("Registered new token callback with pump monitor")
            else:
                logger.warning("Pump monitor not available for callback registration")
            
            # Register callback for price updates
            if price_tracker:
                price_tracker.register_price_update_callback(self._on_price_update)
                logger.info("Registered price update callback with price tracker")
            else:
                logger.warning("Price tracker not available for callback registration")
            
            # Register callback for volume spikes
            if volume_analyzer:
                volume_analyzer.register_volume_spike_callback(self._on_volume_spike)
                logger.info("Registered volume spike callback with volume analyzer")
            else:
                logger.warning("Volume analyzer not available for callback registration")
            
            # Register callback for wallet buy events
            if wallet_tracker:
                wallet_tracker.register_buy_callback(self._on_wallet_buy)
                logger.info("Registered wallet buy callback with wallet tracker")
            else:
                logger.warning("Wallet tracker not available for callback registration")
                
        except Exception as e:
            logger.error(f"Error registering callbacks: {str(e)}", exc_info=True)
    
    async def _on_new_token(self, token_info: Any) -> None:
        """Callback for new token detection."""
        await self.new_token_queue.put(token_info)
        logger.info(f"New token detected: {token_info.symbol}", token=token_info.address)
    
    async def _on_price_update(self, token_address: str, price: float, price_change_percent: float) -> None:
        """Callback for price updates."""
        await self.price_update_queue.put({
            "token_address": token_address,
            "price": price,
            "price_change_percent": price_change_percent
        })
        logger.debug(f"Price update for {token_address[:8]}...: {price:.8f} ({price_change_percent:.2f}%)")
    
    async def _on_volume_spike(self, token_address: str, volume: float, volume_change_percent: float) -> None:
        """Callback for volume spikes."""
        await self.volume_spike_queue.put({
            "token_address": token_address,
            "volume": volume,
            "volume_change_percent": volume_change_percent
        })
        logger.info(f"Volume spike detected for {token_address[:8]}...: {volume:.2f} ({volume_change_percent:.2f}%)")
    
    def _on_wallet_buy(self, wallet_address: str, token_address: str, amount_sol: float) -> None:
        """Callback for wallet buy transactions - synchronous version."""
        # Create async task to handle the queue operation
        asyncio.create_task(self._async_on_wallet_buy(wallet_address, token_address, amount_sol))
    
    async def _async_on_wallet_buy(self, wallet_address: str, token_address: str, amount_sol: float) -> None:
        """Async handler for wallet buy transactions."""
        await self.buy_queue.put({
            "wallet_address": wallet_address,
            "token_address": token_address,
            "amount_sol": amount_sol
        })
        logger.info(f"Wallet buy detected: {wallet_address[:8]}... bought {token_address[:8]}... for {amount_sol:.2f} SOL")
    
    async def _process_events(self) -> None:
        """Process events from various queues and route to strategy engine."""
        # Import strategy engine here to avoid circular imports
        from src.trading.strategy_engine import strategy_engine
        
        while self.running:
            try:
                # Process new token events
                if not self.new_token_queue.empty():
                    token_info = await self.new_token_queue.get()
                    if strategy_engine:
                        await strategy_engine.evaluate_new_token(token_info)
                    self.new_token_queue.task_done()
                
                # Process price update events
                if not self.price_update_queue.empty():
                    price_data = await self.price_update_queue.get()
                    if strategy_engine:
                        await strategy_engine.evaluate_price_update(
                            price_data["token_address"],
                            price_data["price"],
                            price_data["price_change_percent"]
                        )
                    self.price_update_queue.task_done()
                
                # Process volume spike events
                if not self.volume_spike_queue.empty():
                    volume_data = await self.volume_spike_queue.get()
                    if strategy_engine:
                        await strategy_engine.evaluate_volume_spike(
                            volume_data["token_address"],
                            volume_data["volume"],
                            volume_data["volume_change_percent"]
                        )
                    self.volume_spike_queue.task_done()
                
                # Process wallet buy events
                if not self.buy_queue.empty():
                    buy_data = await self.buy_queue.get()
                    if strategy_engine:
                        await strategy_engine.evaluate_wallet_buy(
                            buy_data["wallet_address"],
                            buy_data["token_address"],
                            buy_data["amount_sol"]
                        )
                    self.buy_queue.task_done()
                
                # Process sell events if implemented
                if not self.sell_queue.empty():
                    sell_data = await self.sell_queue.get()
                    logger.info(f"Processing sell event: {sell_data}")
                    # Add logic to handle sell events if needed
                    self.sell_queue.task_done()
                
                # Process create events if implemented
                if not self.create_queue.empty():
                    create_data = await self.create_queue.get()
                    logger.info(f"Processing create event: {create_data}")
                    # Add logic to handle create events if needed
                    self.create_queue.task_done()
                
                await asyncio.sleep(0.1)  # Prevent tight CPU loop
                
            except Exception as e:
                logger.error(f"Error processing events: {str(e)}", exc_info=True)
                await asyncio.sleep(1)  # Wait before retrying on error


# Global event processor instance
event_processor = None

def initialize_event_processor():
    """Initialize the global event processor instance."""
    global event_processor
    event_processor = EventProcessor()
    return event_processor