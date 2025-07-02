"""
Volume analysis for the Solana pump.fun sniping bot.
Detects volume spikes and unusual trading activity.
"""

import asyncio
from typing import Dict, Any, Optional, Callable, List
import time
from datetime import datetime

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.core.connection_manager import connection_manager
from src.monitoring.pump_monitor import TokenInfo

logger = get_logger("volume_analyzer")


class VolumeDataPoint:
    """Stores a single volume data point with timestamp."""
    
    def __init__(self, volume: float, timestamp: float = None):
        self.volume: float = volume
        self.timestamp: float = timestamp or time.time()


class TokenVolumeHistory:
    """Stores volume history for a token."""
    
    def __init__(self, token_address: str, initial_volume: float = 0.0):
        self.token_address: str = token_address
        self.volumes: List[VolumeDataPoint] = [VolumeDataPoint(initial_volume)]
        self.max_history_seconds: float = 3600.0  # Keep 1 hour of history
        self.baseline_volume: float = initial_volume
        self.baseline_calculated: bool = False
        
    def add_volume(self, volume: float) -> None:
        """Add a new volume point to history."""
        self.volumes.append(VolumeDataPoint(volume))
        self._trim_history()
        
    def get_latest_volume(self) -> float:
        """Get the most recent volume."""
        return self.volumes[-1].volume if self.volumes else 0.0
        
    def calculate_volume_multiplier(self, time_window_seconds: float = 300.0) -> float:
        """
        Calculate volume multiplier compared to baseline over a time window.
        
        Args:
            time_window_seconds: Time window in seconds to calculate multiplier over
            
        Returns:
            Volume multiplier compared to baseline
        """
        if not self.baseline_calculated or self.baseline_volume == 0:
            self._calculate_baseline()
            if self.baseline_volume == 0:
                return 1.0
                
        current_time = time.time()
        cutoff_time = current_time - time_window_seconds
        
        # Sum volume in the time window
        window_volume = 0.0
        for point in self.volumes:
            if point.timestamp >= cutoff_time:
                window_volume += point.volume
                
        # Normalize by time window to get average volume per minute
        normalized_volume = window_volume / (time_window_seconds / 60.0)
        
        # Calculate multiplier compared to baseline
        multiplier = normalized_volume / self.baseline_volume if self.baseline_volume > 0 else 1.0
        
        return multiplier
        
    def _calculate_baseline(self, time_window_seconds: float = 1800.0) -> None:
        """
        Calculate baseline volume from historical data.
        
        Args:
            time_window_seconds: Time window in seconds to calculate baseline over
        """
        if len(self.volumes) < 2:
            self.baseline_volume = 0.0
            self.baseline_calculated = False
            return
            
        current_time = time.time()
        cutoff_time = current_time - time_window_seconds
        
        # Sum volume in the time window
        window_volume = 0.0
        count = 0
        
        for point in self.volumes:
            if point.timestamp >= cutoff_time:
                window_volume += point.volume
                count += 1
                
        if count > 0:
            # Normalize to per minute volume
            self.baseline_volume = window_volume / (time_window_seconds / 60.0)
            self.baseline_calculated = True
        else:
            self.baseline_volume = 0.0
            self.baseline_calculated = False
        
    def _trim_history(self) -> None:
        """Remove old volume data points."""
        current_time = time.time()
        cutoff_time = current_time - self.max_history_seconds
        self.volumes = [p for p in self.volumes if p.timestamp >= cutoff_time]


class VolumeAnalyzer:
    """Analyzes token trading volume for spikes and patterns."""
    
    def __init__(self):
        self.settings = config_manager.get_settings()
        self.volume_history: Dict[str, TokenVolumeHistory] = {}
        self.volume_spike_callbacks: List[Callable[[str, float, float], None]] = []
        self.running: bool = False
        self.volume_check_interval = self.settings.monitoring.volume_check_interval
        self.volume_spike_threshold = self.settings.monitoring.volume_spike_threshold
        
    async def start(self) -> None:
        """Start volume analysis for monitored tokens."""
        if self.running:
            logger.warning("Volume analyzer already running")
            return
            
        self.running = True
        logger.info("Starting volume analyzer")
        
        # Start background volume update loop
        asyncio.create_task(self._volume_update_loop())
        
    async def stop(self) -> None:
        """Stop volume analysis."""
        self.running = False
        logger.info("Stopping volume analyzer")
        
    async def _volume_update_loop(self) -> None:
        """Periodically update volume data for all tracked tokens."""
        while self.running:
            try:
                # Get list of tokens to update
                tokens = list(self.volume_history.keys())
                
                if not tokens:
                    await asyncio.sleep(1.0)
                    continue
                
                # Update volume for all tokens
                for token_address in tokens:
                    try:
                        # Fetch latest token data
                        token_data = await connection_manager.fetch_pump_token_data(token_address)
                        if token_data and "volume24h" in token_data:
                            new_volume = float(token_data.get("volume24h", 0.0))
                            self._update_volume(token_address, new_volume)
                            
                            # Check for volume spike
                            history = self.volume_history.get(token_address)
                            if history:
                                multiplier = history.calculate_volume_multiplier()
                                if multiplier >= self.volume_spike_threshold:
                                    logger.volume_spike(
                                        token=token_address,
                                        multiplier=multiplier,
                                        current_volume=new_volume
                                    )
                                    self._notify_volume_spike(token_address, multiplier, new_volume)
                    except Exception as e:
                        logger.error(f"Error updating volume for {token_address[:8]}...: {e}")
                
                await asyncio.sleep(self.volume_check_interval)
                
            except Exception as e:
                logger.error(f"Error in volume update loop: {e}")
                await asyncio.sleep(5.0)
    
    def _update_volume(self, token_address: str, volume: float) -> None:
        """Update volume for a token."""
        if token_address not in self.volume_history:
            self.volume_history[token_address] = TokenVolumeHistory(token_address, volume)
        else:
            self.volume_history[token_address].add_volume(volume)
            
        logger.debug(f"Updated volume for {token_address[:8]}...: ${volume:,.2f}")
    
    def _notify_volume_spike(self, token_address: str, multiplier: float, current_volume: float) -> None:
        """Notify callbacks about volume spike."""
        for callback in self.volume_spike_callbacks:
            try:
                callback(token_address, multiplier, current_volume)
            except Exception as e:
                logger.error(f"Error in volume spike callback: {e}")
    
    def track_token(self, token: TokenInfo) -> None:
        """
        Start tracking volume for a new token.
        
        Args:
            token: TokenInfo object for the token to track
        """
        if token.address not in self.volume_history:
            self.volume_history[token.address] = TokenVolumeHistory(token.address, token.volume_24h)
            logger.info(f"Started tracking volume for {token.symbol} ({token.address[:8]}...)")
    
    def stop_tracking_token(self, token_address: str) -> None:
        """
        Stop tracking volume for a token.
        
        Args:
            token_address: Address of token to stop tracking
        """
        if token_address in self.volume_history:
            del self.volume_history[token_address]
            logger.info(f"Stopped tracking volume for token {token_address[:8]}...")
    
    def register_volume_spike_callback(self, callback: Callable[[str, float, float], None]) -> None:
        """
        Register a callback for volume spike detection.
        
        Args:
            callback: Function to call when volume spike detected (params: token_address, multiplier, current_volume)
        """
        self.volume_spike_callbacks.append(callback)
        logger.info(f"Registered volume spike callback. Total callbacks: {len(self.volume_spike_callbacks)}")
    
    def get_volume_multiplier(self, token_address: str) -> Optional[float]:
        """
        Get the current volume multiplier for a token.
        
        Args:
            token_address: Token address to get volume multiplier for
            
        Returns:
            Volume multiplier or None if not tracked
        """
        if token_address in self.volume_history:
            return self.volume_history[token_address].calculate_volume_multiplier()
        return None
    
    def cleanup_old_history(self) -> None:
        """Clean up old volume history data."""
        token_count = len(self.volume_history)
        for token_address in list(self.volume_history.keys()):
            history = self.volume_history[token_address]
            if not history.volumes or (time.time() - history.volumes[-1].timestamp) > 600:  # 10 minutes inactive
                del self.volume_history[token_address]
        
        cleaned = token_count - len(self.volume_history)
        if cleaned > 0:
            logger.debug(f"Cleaned up volume history for {cleaned} inactive tokens")


# Global volume analyzer instance (will be initialized later)
volume_analyzer = None

def initialize_volume_analyzer():
    """Initialize the global volume analyzer instance."""
    global volume_analyzer
    volume_analyzer = VolumeAnalyzer()
    return volume_analyzer
