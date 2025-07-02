"""
Event processor for coordinating monitoring events.
Routes events from monitors to strategy engine.
"""
# File Location: src/monitoring/event_processor.py

import asyncio
from typing import Dict, Any, Callable, List, Optional
from datetime import datetime

from src.utils.config import config_manager
from src.utils.logger import get_logger

logger = get_logger("event_processor")


class EventProcessor:
    """
    Central event processing hub that coordinates between monitoring components
    and the strategy engine.
    """
    
    def __init__(self):
        self.running = False
        self.new_token_callbacks: List[Callable] = []
        self.price_update_callbacks: List[Callable] = []
        self.volume_spike_callbacks: List[Callable] = []
        self.events_processed = 0
        logger.info("Event processor instance created")
    
    async def start(self) -> None:
        """Start the event processor."""
        if self.running:
            logger.warning("Event processor already running")
            return
            
        self.running = True
        logger.info("Starting event processor")
        
        # Register with monitoring components
        self._register_with_monitors()
        
        # The strategy engine handles its own wallet tracker registration
        # in its initialize() method, so we don't need to do it here
        
    async def stop(self) -> None:
        """Stop the event processor."""
        self.running = False
        logger.info("Stopping event processor")
    
    def _register_with_monitors(self) -> None:
        """Register this processor with all monitoring components."""
        try:
            # Import here to avoid circular imports
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
                
        except Exception as e:
            logger.error(f"Error registering with monitors: {e}", exc_info=True)
    
    async def _handle_new_token(self, token_info) -> None:
        """Handle new token detection event."""
        try:
            logger.info(
                f"Processing new token: {token_info.symbol} ({token_info.address[:8]}...) "
                f"MC: ${token_info.market_cap:,.2f}",
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
            "running": self.running,
            "events_processed": self.events_processed,
            "callbacks": {
                "new_token": len(self.new_token_callbacks),
                "price_update": len(self.price_update_callbacks),
                "volume_spike": len(self.volume_spike_callbacks)
            }
        }


# Global event processor instance
event_processor = None

def initialize_event_processor():
    """Initialize the global event processor instance."""
    global event_processor
    event_processor = EventProcessor()
    return event_processor
