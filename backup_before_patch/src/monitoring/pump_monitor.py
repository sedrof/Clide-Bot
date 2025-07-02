"""
Pump.fun monitoring for the Solana sniping bot.
Detects new token launches and filters based on criteria.
"""

import asyncio
from typing import Dict, Any, Optional, Callable, List
import json
from datetime import datetime, timedelta
import aiohttp

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.core.connection_manager import connection_manager

logger = get_logger("pump_monitor")


class TokenInfo:
    """Stores information about a detected token."""
    
    def __init__(self, data: Dict[str, Any]):
        self.address: str = data.get("mint", "")
        self.symbol: str = data.get("symbol", "")
        self.name: str = data.get("name", "")
        self.market_cap: float = data.get("marketCap", 0.0)
        self.liquidity: float = data.get("usdLiquidity", 0.0)
        self.creation_time: datetime = datetime.fromtimestamp(data.get("createdTimestamp", 0) / 1000)
        self.bonding_curve: str = data.get("bondingCurve", "")
        self.initial_price: float = data.get("initialPrice", 0.0)
        self.last_price: float = data.get("lastPrice", 0.0)
        self.volume_24h: float = data.get("volume24h", 0.0)
        self.holders: int = data.get("holderCount", 0)
        self.raw_data: Dict[str, Any] = data
        
    def update(self, data: Dict[str, Any]) -> None:
        """Update token information with new data."""
        self.market_cap = data.get("marketCap", self.market_cap)
        self.liquidity = data.get("usdLiquidity", self.liquidity)
        self.last_price = data.get("lastPrice", self.last_price)
        self.volume_24h = data.get("volume24h", self.volume_24h)
        self.holders = data.get("holderCount", self.holders)
        self.raw_data.update(data)
        
    def get_age_minutes(self) -> float:
        """Get token age in minutes."""
        return (datetime.now() - self.creation_time).total_seconds() / 60.0
        
    def __str__(self) -> str:
        return f"{self.symbol} ({self.address[:8]}...) - MC: ${self.market_cap:,.2f}"


class PumpMonitor:
    """Monitors pump.fun for new token launches."""
    
    def __init__(self):
        self.settings = config_manager.get_settings()
        self.tokens: Dict[str, TokenInfo] = {}
        self.new_token_callbacks: List[Callable[[TokenInfo], None]] = []
        self.running: bool = False
        self.max_token_age_minutes = self.settings.monitoring.max_token_age_minutes
        self.min_market_cap = self.settings.monitoring.min_market_cap
        self.new_token_check_interval = self.settings.monitoring.new_token_check_interval
        
    async def start(self) -> None:
        """Start monitoring pump.fun for new tokens."""
        if self.running:
            logger.warning("Pump monitor already running")
            return
            
        self.running = True
        logger.info("Starting pump.fun monitor")
        
        # Directly start REST API polling instead of WebSocket due to connection issues
        await self._start_rest_polling()
        
    async def stop(self) -> None:
        """Stop monitoring pump.fun."""
        self.running = False
        logger.info("Stopping pump.fun monitor")
        # Ensure any polling tasks are cancelled
        if hasattr(self, '_polling_task') and self._polling_task:
            self._polling_task.cancel()
            self._polling_task = None
            
    async def _start_rest_polling(self) -> None:
        """Start polling REST API with focus on tracked wallet to minimize calls."""
        logger.info("Starting targeted REST API polling for pump.fun data")
        polling_interval = self.settings.monitoring.new_token_check_interval
        
        async def poll_rest_api():
            while self.running:
                try:
                    # Get tracked wallet address if available
                    tracked_wallet = None
                    if hasattr(self, 'wallet_tracker'):
                        tracked_wallets = self.wallet_tracker.get_tracked_wallets()
                        if tracked_wallets:
                            tracked_wallet = tracked_wallets[0]  # Focus on first tracked wallet
                    
                    if tracked_wallet:
                        async with aiohttp.ClientSession() as session:
                            # Fetch data specific to the tracked wallet (adjust endpoint if API supports wallet-specific queries)
                            url = f"https://frontend-api.pump.fun/coins/?wallet={tracked_wallet}"
                            async with session.get(url) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    for token_data in data:
                                        self._process_new_token(token_data)
                                else:
                                    logger.error(f"REST API request failed with status {response.status}")
                    else:
                        logger.debug("No tracked wallet available, skipping API call")
                        await asyncio.sleep(polling_interval / 2)  # Shorter sleep if no call made
                        
                except Exception as e:
                    logger.error(f"Error during targeted REST API polling: {e}")
                await asyncio.sleep(polling_interval)
        
        # Start polling task
        self._polling_task = asyncio.create_task(poll_rest_api())
        logger.info("Targeted REST API polling started")
        
    async def _monitor_websocket(self) -> None:
        """Monitor pump.fun WebSocket for new token events."""
        logger.info("Connecting to pump.fun WebSocket for monitoring")
        
        def process_event(data: Dict[str, Any]) -> None:
            """Process incoming WebSocket event."""
            try:
                event_type = data.get("event", "")
                
                if event_type == "newToken":
                    token_data = data.get("data", {})
                    self._process_new_token(token_data)
                elif event_type == "trade":
                    token_address = data.get("data", {}).get("mint", "")
                    if token_address in self.tokens:
                        self.tokens[token_address].update(data.get("data", {}))
                else:
                    logger.debug(f"Received unhandled event type: {event_type}")
                    
            except Exception as e:
                logger.error(f"Error processing pump.fun event: {e}")
        
        reconnect_delay = 5
        max_delay = 60
        while self.running:
            try:
                await connection_manager.receive_pump_events(process_event)
                reconnect_delay = 5  # Reset delay on successful connection
            except Exception as e:
                logger.error(f"Pump.fun WebSocket monitoring failed: {e}")
                if self.running:
                    logger.info(f"Reconnecting to pump.fun WebSocket in {reconnect_delay} seconds...")
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, max_delay)  # Exponential backoff
                    await self._monitor_websocket()
                else:
                    break
    
    def _process_new_token(self, token_data: Dict[str, Any]) -> None:
        """Process a new token detection event."""
        try:
            token_address = token_data.get("mint", "")
            if not token_address:
                logger.warning("Received new token event without mint address")
                return
                
            if token_address in self.tokens:
                logger.debug(f"Token already tracked: {token_address[:8]}...")
                self.tokens[token_address].update(token_data)
                return
                
            token_info = TokenInfo(token_data)
            self.tokens[token_address] = token_info
            
            logger.token_detected(
                token=token_address,
                market_cap=token_info.market_cap,
                liquidity=token_info.liquidity,
                symbol=token_info.symbol
            )
            
            # Check if token meets basic criteria
            if self._meets_basic_criteria(token_info):
                # Notify callbacks about new token
                for callback in self.new_token_callbacks:
                    try:
                        callback(token_info)
                    except Exception as e:
                        logger.error(f"Error in new token callback: {e}")
            else:
                logger.debug(
                    f"Token filtered out by basic criteria: {token_info.symbol}",
                    market_cap=token_info.market_cap,
                    age_minutes=token_info.get_age_minutes()
                )
                
        except Exception as e:
            logger.error(f"Error processing new token: {e}")
    
    def _meets_basic_criteria(self, token: TokenInfo) -> bool:
        """
        Check if token meets basic monitoring criteria.
        
        Args:
            token: TokenInfo object to check
            
        Returns:
            True if token meets criteria
        """
        if token.market_cap < self.min_market_cap:
            return False
            
        if token.get_age_minutes() > self.max_token_age_minutes:
            return False
            
        return True
    
    async def cleanup_old_tokens(self) -> None:
        """Remove old tokens from tracking."""
        try:
            initial_count = len(self.tokens)
            self.tokens = {
                addr: token 
                for addr, token in self.tokens.items()
                if token.get_age_minutes() <= self.max_token_age_minutes * 2  # Keep some buffer
            }
            removed = initial_count - len(self.tokens)
            if removed > 0:
                logger.debug(f"Cleaned up {removed} old tokens. Tracking {len(self.tokens)} tokens.")
        except Exception as e:
            logger.error(f"Error cleaning up old tokens: {e}")
    
    def register_new_token_callback(self, callback: Callable[[TokenInfo], None]) -> None:
        """
        Register a callback for new token detection.
        
        Args:
            callback: Function to call when new token is detected
        """
        self.new_token_callbacks.append(callback)
        logger.info(f"Registered new token callback. Total callbacks: {len(self.new_token_callbacks)}")
    
    def get_tracked_tokens(self) -> List[TokenInfo]:
        """Get list of currently tracked tokens."""
        return list(self.tokens.values())
    
    async def fetch_token_details(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed information about a specific token.
        
        Args:
            token_address: Token address to fetch details for
            
        Returns:
            Token details dictionary or None if failed
        """
        try:
            details = await connection_manager.fetch_pump_token_data(token_address)
            if details and token_address in self.tokens:
                self.tokens[token_address].update(details)
            return details
        except Exception as e:
            logger.error(f"Failed to fetch token details for {token_address}: {e}")
            return None


# Global pump monitor instance (will be initialized later)
pump_monitor = None

def initialize_pump_monitor():
    """Initialize the global pump monitor instance."""
    global pump_monitor
    pump_monitor = PumpMonitor()
    return pump_monitor
