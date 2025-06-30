"""
Price tracking for the Solana pump.fun sniping bot.
Monitors token prices in real-time.
"""

import asyncio
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
import time

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.core.connection_manager import connection_manager
from src.monitoring.pump_monitor import TokenInfo

logger = get_logger("price_tracker")


class PriceDataPoint:
    """Stores a single price data point with timestamp."""
    
    def __init__(self, price: float, timestamp: float = None):
        self.price: float = price
        self.timestamp: float = timestamp or time.time()


class TokenPriceHistory:
    """Stores price history for a token."""
    
    def __init__(self, token_address: str, initial_price: float):
        self.token_address: str = token_address
        self.prices: List[PriceDataPoint] = [PriceDataPoint(initial_price)]
        self.max_history_seconds: float = 300.0  # Keep 5 minutes of history
        
    def add_price(self, price: float) -> None:
        """Add a new price point to history."""
        self.prices.append(PriceDataPoint(price))
        self._trim_history()
        
    def get_latest_price(self) -> float:
        """Get the most recent price."""
        return self.prices[-1].price if self.prices else 0.0
        
    def get_price_change(self, time_window_seconds: float = 60.0) -> float:
        """
        Calculate price change percentage over a time window.
        
        Args:
            time_window_seconds: Time window in seconds to calculate change over
            
        Returns:
            Percentage change in price over the window
        """
        if len(self.prices) < 2:
            return 0.0
            
        current_time = time.time()
        cutoff_time = current_time - time_window_seconds
        
        # Find the first price point in the window
        start_price = None
        for point in self.prices:
            if point.timestamp >= cutoff_time:
                start_price = point.price
                break
                
        if start_price is None:
            return 0.0
            
        end_price = self.prices[-1].price
        
        if start_price == 0:
            return 0.0
            
        return ((end_price - start_price) / start_price) * 100.0
        
    def _trim_history(self) -> None:
        """Remove old price data points."""
        current_time = time.time()
        cutoff_time = current_time - self.max_history_seconds
        self.prices = [p for p in self.prices if p.timestamp >= cutoff_time]


class PriceTracker:
    """Tracks token prices in real-time."""
    
    def __init__(self):
        self.settings = config_manager.get_settings()
        self.price_history: Dict[str, TokenPriceHistory] = {}
        self.price_update_callbacks: List[Callable[[str, float], None]] = []
        self.running: bool = False
        self.price_check_interval = self.settings.monitoring.price_check_interval
        
    async def start(self) -> None:
        """Start price tracking for monitored tokens."""
        if self.running:
            logger.warning("Price tracker already running")
            return
            
        self.running = True
        logger.info("Starting price tracker")
        
        # Start background price update loop
        asyncio.create_task(self._price_update_loop())
        
    async def stop(self) -> None:
        """Stop price tracking."""
        self.running = False
        logger.info("Stopping price tracker")
        
    async def _price_update_loop(self) -> None:
        """Periodically update prices for all tracked tokens."""
        while self.running:
            try:
                # Get list of tokens to update
                tokens = list(self.price_history.keys())
                
                if not tokens:
                    await asyncio.sleep(1.0)
                    continue
                
                # Update prices for all tokens
                for token_address in tokens:
                    try:
                        # Fetch latest token data
                        token_data = await connection_manager.fetch_pump_token_data(token_address)
                        if token_data and "lastPrice" in token_data:
                            new_price = float(token_data.get("lastPrice", 0.0))
                            if new_price > 0:
                                self._update_price(token_address, new_price)
                                logger.debug(f"Updated price for {token_address[:8]}...: ${new_price:.8f}")
                    except Exception as e:
                        logger.error(f"Error updating price for {token_address[:8]}...: {e}")
                
                await asyncio.sleep(self.price_check_interval)
                
            except Exception as e:
                logger.error(f"Error in price update loop: {e}")
                await asyncio.sleep(5.0)
    
    def _update_price(self, token_address: str, price: float) -> None:
        """Update price for a token and notify callbacks."""
        if token_address not in self.price_history:
            self.price_history[token_address] = TokenPriceHistory(token_address, price)
        else:
            self.price_history[token_address].add_price(price)
            
        # Notify callbacks about price update
        for callback in self.price_update_callbacks:
            try:
                callback(token_address, price)
            except Exception as e:
                logger.error(f"Error in price update callback: {e}")
    
    def track_token(self, token: TokenInfo) -> None:
        """
        Start tracking price for a new token.
        
        Args:
            token: TokenInfo object for the token to track
        """
        if token.address not in self.price_history:
            self.price_history[token.address] = TokenPriceHistory(token.address, token.last_price)
            logger.info(f"Started tracking price for {token.symbol} ({token.address[:8]}...)")
    
    def stop_tracking_token(self, token_address: str) -> None:
        """
        Stop tracking price for a token.
        
        Args:
            token_address: Address of token to stop tracking
        """
        if token_address in self.price_history:
            del self.price_history[token_address]
            logger.info(f"Stopped tracking price for token {token_address[:8]}...")
    
    def register_price_update_callback(self, callback: Callable[[str, float], None]) -> None:
        """
        Register a callback for price updates.
        
        Args:
            callback: Function to call when price updates (params: token_address, new_price)
        """
        self.price_update_callbacks.append(callback)
        logger.info(f"Registered price update callback. Total callbacks: {len(self.price_update_callbacks)}")
    
    def get_current_price(self, token_address: str) -> Optional[float]:
        """
        Get the current price for a token.
        
        Args:
            token_address: Token address to get price for
            
        Returns:
            Current price or None if not tracked
        """
        if token_address in self.price_history:
            return self.price_history[token_address].get_latest_price()
        return None
    
    def get_price_change(self, token_address: str, time_window_seconds: float = 60.0) -> Optional[float]:
        """
        Get the price change percentage for a token over a time window.
        
        Args:
            token_address: Token address to get price change for
            time_window_seconds: Time window in seconds to calculate change over
            
        Returns:
            Percentage change or None if not tracked
        """
        if token_address in self.price_history:
            return self.price_history[token_address].get_price_change(time_window_seconds)
        return None
    
    def cleanup_old_history(self) -> None:
        """Clean up old price history data."""
        token_count = len(self.price_history)
        for token_address in list(self.price_history.keys()):
            history = self.price_history[token_address]
            if not history.prices or (time.time() - history.prices[-1].timestamp) > 600:  # 10 minutes inactive
                del self.price_history[token_address]
        
        cleaned = token_count - len(self.price_history)
        if cleaned > 0:
            logger.debug(f"Cleaned up price history for {cleaned} inactive tokens")


# Global price tracker instance (will be initialized later)
price_tracker = None

def initialize_price_tracker():
    """Initialize the global price tracker instance."""
    global price_tracker
    price_tracker = PriceTracker()
    return price_tracker
