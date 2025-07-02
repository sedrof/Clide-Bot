"""
Trading strategy engine with WORKING copy trading!
Fixed async issues - trades will execute properly now.
"""
# File Location: src/trading/strategy_engine.py

import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
import time

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.core.transaction_builder import transaction_builder
from src.monitoring.position_tracker import position_tracker
from src.monitoring.wallet_tracker import wallet_tracker
from src.core.wallet_manager import wallet_manager

logger = get_logger("strategy")


class StrategyEngine:
    """
    Manages trading strategies with WORKING copy trading!
    """
    
    def __init__(self):
        self.settings = config_manager.get_settings().trading
        self.positions: Dict[str, Any] = {}
        self.trade_history: List[Dict[str, Any]] = []
        self.trade_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.running = False
        self.active_positions: Dict[str, Any] = {}
        self.max_positions = self.settings.max_positions
        
        # Cache balance to avoid repeated calls
        self._cached_balance = 0.0
        self._balance_cache_time = 0
        self._balance_cache_duration = 10  # Cache for 10 seconds
        
        # Minimum trade amounts by platform
        self.platform_minimums = {
            "Jupiter": 0.001,
            "Raydium": 0.001,
            "Pump.fun": 0.01,
            "Orca": 0.001,
            "Meteora": 0.001,
            "OKX DEX Router": 0.001,
            "Phantom": 0.001,
            "default": 0.001
        }
        
        # Platform-specific settings
        self.platform_settings = {
            "Jupiter": {"slippage": 0.01},
            "Raydium": {"slippage": 0.02},
            "Pump.fun": {"slippage": 0.05},
            "Orca": {"slippage": 0.02},
            "OKX DEX Router": {"slippage": 0.02},
            "default": {"slippage": 0.02}
        }
    
    async def initialize(self) -> None:
        """Initialize the strategy engine."""
        logger.info("Strategy engine initialized")
        
        # Register callback with wallet tracker
        from src.monitoring.wallet_tracker import wallet_tracker
        if wallet_tracker:
            wallet_tracker.register_buy_callback(self.handle_tracked_wallet_buy)
            logger.info("Registered copy trading callback with wallet tracker")
        
        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())
        
        # Get initial balance
        await self._update_cached_balance()
    
    def register_with_wallet_tracker(self) -> None:
        """Register with wallet tracker for copy trading."""
        try:
            from src.monitoring.wallet_tracker import wallet_tracker
            if wallet_tracker:
                wallet_tracker.register_buy_callback(self.handle_tracked_wallet_buy)
                logger.info("Registered copy trading callback with wallet tracker")
        except Exception as e:
            logger.error(f"Error registering with wallet tracker: {e}")
    
    async def start(self) -> None:
        """Start the strategy engine."""
        if self.running:
            logger.warning("Strategy engine already running")
            return
        
        self.running = True
        logger.info("Starting strategy engine")
        
        # Initialize if not already done
        await self.initialize()
        
        # Start position monitoring
        asyncio.create_task(self._monitor_positions())
    
    async def stop(self) -> None:
        """Stop the strategy engine."""
        self.running = False
        logger.info("Stopping strategy engine")
    
    async def _update_cached_balance(self) -> float:
        """Update cached balance."""
        try:
            self._cached_balance = await wallet_manager.get_balance()
            self._balance_cache_time = time.time()
            return self._cached_balance
        except Exception as e:
            logger.error(f"Error updating balance: {e}")
            return self._cached_balance
    
    async def _get_balance(self) -> float:
        """Get wallet balance with caching."""
        current_time = time.time()
        
        # Check if cache is still valid
        if current_time - self._balance_cache_time > self._balance_cache_duration:
            await self._update_cached_balance()
        
        return self._cached_balance
    
    async def handle_tracked_wallet_buy(
        self, 
        wallet_address: str, 
        token_address: str, 
        amount_sol: float,
        platform: str = "Unknown",
        tx_url: str = ""
    ) -> None:
        """
        Handle buy signal from tracked wallet - FIXED async version!
        """
        try:
            logger.info("="*60)
            logger.info(f"📋 COPY TRADE SIGNAL DETECTED")
            logger.info(f"Wallet: {wallet_address[:8]}...")
            logger.info(f"Token: {token_address}")
            logger.info(f"Platform: {platform}")
            logger.info(f"Amount: {amount_sol:.4f} SOL")
            if tx_url:
                logger.info(f"TX: {tx_url}")
            
            # Check if we should copy this trade
            should_copy = await self._should_copy_trade(wallet_address, amount_sol, platform)
            if not should_copy:
                return
            
            # Calculate our copy trade amount
            copy_amount = self._calculate_copy_amount(amount_sol, platform)
            
            logger.info(f"Executing copy trade for {copy_amount:.4f} SOL on {platform}")
            
            # Execute the copy trade on the SAME platform as tracked wallet
            success = await self.execute_buy(
                token_address=token_address,
                amount_sol=copy_amount,
                preferred_dex=platform,
                metadata={
                    "copy_from_wallet": wallet_address,
                    "original_amount": amount_sol,
                    "original_platform": platform,
                    "original_tx": tx_url,
                    "source": "copy_trade"
                }
            )
            
            if success:
                logger.info(f"✅ Copy trade executed successfully on {platform}")
            else:
                logger.error(f"❌ Copy trade failed on {platform}")
            
        except Exception as e:
            logger.error(f"Error handling tracked wallet buy: {e}", exc_info=True)
    
    async def _should_copy_trade(self, wallet_address: str, amount_sol: float, platform: str) -> bool:
        """Determine if we should copy this trade - ASYNC version."""
        try:
            # Get current balance
            current_balance = await self._get_balance()
            
            logger.info(f"Current balance: {current_balance:.4f} SOL")
            
            # Check minimum balance
            min_balance = self.settings.min_balance_sol
            if current_balance < min_balance:
                logger.warning(f"Insufficient balance for copy trade. Current: {current_balance:.4f} SOL, Required: {min_balance:.4f} SOL")
                return False
            
            # Check if we have capacity
            if len(self.active_positions) >= self.max_positions:
                logger.warning(f"Max positions reached ({self.max_positions}), skipping copy trade")
                return False
            
            # Check minimum amount for platform
            min_amount = self.platform_minimums.get(platform, self.platform_minimums["default"])
            if amount_sol < min_amount * 0.5:
                logger.info(f"Trade amount {amount_sol:.4f} below minimum {min_amount} for {platform}")
                return False
            
            logger.info(f"✅ Copy trade approved! Balance sufficient and all checks passed.")
            return True
            
        except Exception as e:
            logger.error(f"Error in _should_copy_trade: {e}")
            return False
    
    def _calculate_copy_amount(self, original_amount: float, platform: str) -> float:
        """Calculate how much to copy trade based on settings."""
        # Use configured buy amount
        copy_amount = self.settings.buy_amount_sol
        
        # Get platform minimum
        min_amount = self.platform_minimums.get(platform, self.platform_minimums["default"])
        
        # Ensure we meet platform minimum
        if copy_amount < min_amount:
            copy_amount = min_amount
            logger.info(f"Adjusted copy amount to platform minimum: {copy_amount:.4f} SOL")
        
        # Don't exceed max buy amount
        if copy_amount > self.settings.max_buy_amount_sol:
            copy_amount = self.settings.max_buy_amount_sol
        
        logger.info(f"Copy trade amount: {copy_amount:.4f} SOL (original: {original_amount:.4f})")
        return copy_amount
    
    async def execute_buy(
        self,
        token_address: str,
        amount_sol: float,
        preferred_dex: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Execute a buy order on the specified DEX/platform."""
        try:
            start_time = time.time()
            logger.info("="*60)
            logger.info(f"🚀 EXECUTING BUY ORDER")
            logger.info(f"Token: {token_address}")
            logger.info(f"Amount: {amount_sol:.4f} SOL")
            logger.info(f"Platform: {preferred_dex or 'Auto-detect'}")
            
            if metadata:
                if "copy_from_wallet" in metadata:
                    logger.info(f"Copy from: {metadata['copy_from_wallet'][:8]}...")
                if "symbol" in metadata:
                    logger.info(f"Symbol: {metadata['symbol']}")
                if "market_cap" in metadata:
                    logger.info(f"Market Cap: ${metadata['market_cap']:,.2f}")
            
            # Get platform-specific slippage
            slippage = self.platform_settings.get(
                preferred_dex or "default", 
                self.platform_settings["default"]
            )["slippage"]
            
            logger.info(f"Using slippage: {slippage*100:.1f}%")
            
            # Execute the transaction
            tx_signature = await transaction_builder.execute_buy(
                token_address=token_address,
                amount_sol=amount_sol,
                slippage=slippage,
                preferred_dex=preferred_dex
            )
            
            execution_time = time.time() - start_time
            
            if tx_signature:
                logger.info(f"✅ BUY ORDER SUCCESSFUL in {execution_time:.2f}s")
                logger.info(f"TX: {tx_signature}")
                logger.info("="*60)
                
                # Track the position
                self.active_positions[token_address] = {
                    "token_address": token_address,
                    "amount_sol": amount_sol,
                    "tx_signature": tx_signature,
                    "timestamp": datetime.now(),
                    "platform": preferred_dex or "unknown",
                    "status": "open",
                    "metadata": metadata or {},
                    "entry_price": amount_sol
                }
                
                # Update position tracker
                await position_tracker.add_position(
                    token_address=token_address,
                    amount_sol=amount_sol,
                    amount_tokens=0,
                    entry_price=amount_sol,
                    entry_tx=tx_signature
                )
                
                # Trigger callbacks
                await self._trigger_trade_callback({
                    "type": "buy",
                    "token": token_address,
                    "amount_sol": amount_sol,
                    "tx_signature": tx_signature,
                    "timestamp": datetime.now().isoformat(),
                    "platform": preferred_dex or "auto"
                })
                
                # Update balance cache after successful trade
                await self._update_cached_balance()
                
                return True
            else:
                logger.error(f"❌ BUY ORDER FAILED after {execution_time:.2f}s")
                logger.error("="*60)
                return False
        
        except Exception as e:
            logger.error(f"Error executing buy: {e}", exc_info=True)
            return False
    
    async def execute_sell(
        self,
        token_address: str,
        amount_tokens: float,
        reason: str = "Manual sell",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Execute a sell order with the SAME exit strategy regardless of platform."""
        try:
            start_time = time.time()
            logger.info("="*60)
            logger.info(f"🔴 EXECUTING SELL ORDER")
            logger.info(f"Token: {token_address}")
            logger.info(f"Amount: {amount_tokens:.2f} tokens")
            logger.info(f"Reason: {reason}")
            
            # Get position info
            position = self.active_positions.get(token_address, {})
            platform = position.get("platform", "auto")
            
            logger.info(f"Original buy platform: {platform}")
            
            # Get platform-specific slippage
            slippage = self.platform_settings.get(
                platform, 
                self.platform_settings["default"]
            )["slippage"]
            
            # Execute the transaction
            tx_signature = await transaction_builder.execute_sell(
                token_address=token_address,
                amount_tokens=amount_tokens,
                slippage=slippage
            )
            
            execution_time = time.time() - start_time
            
            if tx_signature:
                logger.info(f"✅ SELL ORDER SUCCESSFUL in {execution_time:.2f}s")
                logger.info(f"TX: {tx_signature}")
                logger.info("="*60)
                
                # Update position status
                if token_address in self.active_positions:
                    self.active_positions[token_address]["status"] = "closed"
                    self.active_positions[token_address]["exit_tx"] = tx_signature
                    self.active_positions[token_address]["exit_time"] = datetime.now()
                    self.active_positions[token_address]["exit_reason"] = reason
                
                # Remove from position tracker
                await position_tracker.remove_position(token_address)
                
                # Trigger callbacks
                await self._trigger_trade_callback({
                    "type": "sell",
                    "token": token_address,
                    "amount_tokens": amount_tokens,
                    "tx_signature": tx_signature,
                    "reason": reason,
                    "timestamp": datetime.now().isoformat(),
                    "platform": platform
                })
                
                # Update balance cache after successful trade
                await self._update_cached_balance()
                
                return True
            else:
                logger.error(f"❌ SELL ORDER FAILED after {execution_time:.2f}s")
                logger.error("="*60)
                return False
        
        except Exception as e:
            logger.error(f"Error executing sell: {e}", exc_info=True)
            return False
    
    async def evaluate_new_token(self, token_info) -> None:
        """Evaluate a newly detected token for potential buy."""
        try:
            logger.info(f"Evaluating new token: {token_info.symbol}", token=token_info.address)
            
            # Check if we have capacity
            if len(self.active_positions) >= self.max_positions:
                logger.warning(f"Max positions reached ({self.max_positions}). Skipping {token_info.symbol} evaluation.")
                return
            
            # Check if token meets criteria
            if self._meets_buy_criteria(token_info):
                logger.info(f"Token {token_info.symbol} meets buy criteria. Executing buy order.", token=token_info.address)
                await self.execute_buy_from_token_info(token_info)
            else:
                logger.info(f"Token {token_info.symbol} does not meet buy criteria. Skipping.", token=token_info.address)
        
        except Exception as e:
            logger.error(f"Error evaluating new token {token_info.symbol}: {e}", exc_info=True)
    
    async def evaluate_price_update(self, token_address: str, price: float, price_change_percent: float) -> None:
        """Evaluate price update for an active position."""
        if token_address in self.active_positions:
            position = self.active_positions[token_address]
            position['current_price'] = price
            position['price_change_percent'] = price_change_percent
            
            logger.debug(
                f"Price update for {position.get('symbol', 'Unknown')}: {price:.6f} SOL ({price_change_percent:+.2f}%)",
                token=token_address
            )
    
    async def evaluate_volume_spike(self, token_address: str, volume_spike_ratio: float) -> None:
        """Evaluate volume spike for potential action."""
        if token_address in self.active_positions:
            position = self.active_positions[token_address]
            position['volume_spike_ratio'] = volume_spike_ratio
            
            logger.info(
                f"Volume spike detected for {position.get('symbol', 'Unknown')}: {volume_spike_ratio:.2f}x average",
                token=token_address
            )
    
    def _meets_buy_criteria(self, token_info) -> bool:
        """Check if a token meets the criteria for buying."""
        # Check market cap
        if hasattr(token_info, 'market_cap') and token_info.market_cap < self.settings.min_market_cap:
            logger.debug(f"Token {token_info.symbol} market cap too low: ${token_info.market_cap:,.2f}")
            return False
        
        # Check liquidity
        if hasattr(token_info, 'liquidity') and token_info.liquidity < self.settings.min_liquidity:
            logger.debug(f"Token {token_info.symbol} liquidity too low: ${token_info.liquidity:,.2f}")
            return False
        
        # Check if already in positions
        if hasattr(token_info, 'address') and token_info.address in self.active_positions:
            logger.debug(f"Token {token_info.symbol} already in positions")
            return False
        
        return True
    
    async def execute_buy_from_token_info(self, token_info) -> bool:
        """Execute buy based on TokenInfo object."""
        return await self.execute_buy(
            token_address=token_info.address,
            amount_sol=self.settings.buy_amount_sol,
            metadata={
                "symbol": token_info.symbol,
                "market_cap": token_info.market_cap,
                "liquidity": token_info.liquidity,
                "source": "new_token_detection"
            }
        )
    
    async def _monitor_positions(self) -> None:
        """Monitor active positions for selling opportunities."""
        while self.running:
            try:
                # Check each position
                for token_address in list(self.active_positions.keys()):
                    position = self.active_positions[token_address]
                    
                    # Skip if not open
                    if position.get("status") != "open":
                        continue
                    
                    # Get current metrics
                    try:
                        metrics = await position_tracker.get_position_metrics(token_address)
                        if metrics:
                            # Check exit conditions
                            should_sell, reason = self._check_exit_conditions(position, metrics)
                            
                            if should_sell:
                                logger.info(f"Exit condition triggered for {token_address[:8]}...: {reason}")
                                logger.info(f"Position was bought on: {position.get('platform', 'Unknown')}")
                                
                                await self.execute_sell(
                                    token_address=token_address,
                                    amount_tokens=metrics["amount"],
                                    reason=reason
                                )
                    except Exception as e:
                        logger.debug(f"Could not get metrics for {token_address[:8]}...: {e}")
                
                await asyncio.sleep(5)
            
            except Exception as e:
                logger.error(f"Error monitoring positions: {e}", exc_info=True)
                await asyncio.sleep(10)
    
    async def _monitoring_loop(self) -> None:
        """Monitor positions and market conditions."""
        while True:
            try:
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)
    
    def _check_exit_conditions(
        self,
        position: Dict[str, Any],
        metrics: Dict[str, Any]
    ) -> tuple[bool, str]:
        """Check if position should be sold based on UNIVERSAL strategy rules."""
        gain_percent = metrics.get("gain_percent", 0)
        time_held = metrics.get("time_held_seconds", 0)
        
        logger.debug(f"Position metrics: gain={gain_percent:.2f}%, held={time_held/60:.1f}min")
        
        # Take profit - same for all platforms
        if gain_percent >= self.settings.take_profit_percentage:
            return True, f"Take profit: {gain_percent:.1f}% gain"
        
        # Stop loss - same for all platforms
        if gain_percent <= -self.settings.stop_loss_percentage:
            return True, f"Stop loss: {gain_percent:.1f}% loss"
        
        # Time-based stop loss - same for all platforms
        if self.settings.time_based_stop_loss_minutes > 0:
            if time_held > self.settings.time_based_stop_loss_minutes * 60:
                if gain_percent < 0:
                    return True, f"Time stop: {time_held/60:.0f}min held with {gain_percent:.1f}% loss"
        
        # Trailing stop - same for all platforms
        if self.settings.trailing_stop_percentage > 0:
            if hasattr(position, 'peak_gain'):
                drawdown = position.peak_gain - gain_percent
                if drawdown >= self.settings.trailing_stop_percentage:
                    return True, f"Trailing stop: {drawdown:.1f}% drawdown from peak"
            
            # Update peak gain
            if not hasattr(position, 'peak_gain') or gain_percent > position.peak_gain:
                position.peak_gain = gain_percent
        
        return False, ""
    
    async def _trigger_trade_callback(self, trade_data: Dict[str, Any]):
        """Trigger trade callbacks."""
        for callback in self.trade_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(trade_data)
                else:
                    callback(trade_data)
            except Exception as e:
                logger.error(f"Error in trade callback: {e}")
    
    def register_trade_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for trade events."""
        self.trade_callbacks.append(callback)
        logger.info(f"Registered trade callback. Total callbacks: {len(self.trade_callbacks)}")
    
    def get_active_positions(self) -> List[Dict[str, Any]]:
        """Get list of active positions."""
        return [p for p in self.active_positions.values() if p.get("status") == "open"]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        active_positions = self.get_active_positions()
        total_trades = len(self.trade_history)
        
        return {
            "active_positions": len(active_positions),
            "total_trades": total_trades,
            "positions": active_positions,
            "current_balance": self._cached_balance
        }


# Global strategy engine instance
strategy_engine = None

def initialize_strategy_engine():
    """Initialize the global strategy engine instance."""
    global strategy_engine
    strategy_engine = StrategyEngine()
    return strategy_engine
