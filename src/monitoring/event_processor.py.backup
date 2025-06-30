"""
Event processor for the Solana pump.fun sniping bot.
Coordinates monitoring components and triggers strategy actions.
"""
# File Location: src/monitoring/event_processor.py

import asyncio
from typing import Dict, Any, Optional, Callable, List
import time

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.monitoring.pump_monitor import pump_monitor, TokenInfo
from src.monitoring.price_tracker import price_tracker
from src.monitoring.volume_analyzer import volume_analyzer
from src.monitoring.wallet_tracker import wallet_tracker

logger = get_logger("event_processor")


class EventProcessor:
    """Coordinates monitoring components and processes events."""
    
    def __init__(self):
        self.settings = config_manager.get_settings()
        self.running: bool = False
        
        # Event callbacks
        self.new_token_callbacks: List[Callable[[TokenInfo], None]] = []
        self.price_update_callbacks: List[Callable[[str, float, float], None]] = []
        self.volume_spike_callbacks: List[Callable[[str, float], None]] = []
        
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
    
    async def _handle_new_token(self, token_info: TokenInfo) -> None:
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
    
    def register_new_token_callback(self, callback: Callable[[TokenInfo], None]) -> None:
        """Register callback for new token events."""
        self.new_token_callbacks.append(callback)
        logger.info(f"Registered new token callback. Total: {len(self.new_token_callbacks)}")
    
    def register_price_update_callback(self, callback: Callable[[str, float, float], None]) -> None:
        """Register callback for price update events."""
        self.price_update_callbacks.append(callback)
        logger.info(f"Registered price update callback. Total: {len(self.price_update_callbacks)}")
    
    def register_volume_spike_callback(self, callback: Callable[[str, float], None]) -> None:
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
    return event_processor