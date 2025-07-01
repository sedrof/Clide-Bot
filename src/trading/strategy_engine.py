"""
Trading strategy engine with platform-specific copy trading.
Ensures trades happen on the same platform where they were detected.
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
import time

from src.utils.config import config_manager, TradingSettings
from src.utils.logger import get_logger
from src.core.transaction_builder import transaction_builder
from src.monitoring.position_tracker import position_tracker
from src.monitoring.wallet_tracker import wallet_tracker

logger = get_logger("strategy")


class StrategyEngine:
    """
    Manages trading strategies including entry and exit rules.
    Now with platform-specific copy trading.
    """
    
    def __init__(self):
        self.settings: TradingSettings = config_manager.get_settings().trading
        self.positions: Dict[str, Any] = {}
        self.trade_history: List[Dict[str, Any]] = []
        self.trade_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        # Minimum trade amounts by platform
        self.platform_minimums = {
            "Jupiter": 0.0001,
            "Raydium": 0.001,
            "Pump.fun": 0.01,
            "Orca": 0.001,
            "Meteora": 0.001,
            "default": 0.001
        }
        
        # Platform-specific settings
        self.platform_settings = {
            "Jupiter": {"slippage": 0.01},
            "Raydium": {"slippage": 0.02},
            "Pump.fun": {"slippage": 0.05},  # Higher slippage for bonding curves
            "default": {"slippage": 0.02}
        }
        
    async def initialize(self) -> None:
        """Initialize the strategy engine."""
        logger.info("Strategy engine initialized")
        
        # Register callback with wallet tracker (with platform parameter)
        wallet_tracker.register_buy_callback(self.handle_tracked_wallet_buy)
        
        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())
    
    async def handle_tracked_wallet_buy(
        self, 
        wallet_address: str, 
        token_address: str, 
        amount_sol: float,
        platform: str,
        tx_url: str
    ) -> None:
        """
        Handle buy signal from tracked wallet - execute copy trade on same platform.
        
        Args:
            wallet_address: The tracked wallet that made the buy
            token_address: The token that was bought
            amount_sol: Amount in SOL that was spent
            platform: The platform where the buy was detected
            tx_url: Solscan URL for the transaction
        """
        try:
            # Log detailed information
            logger.info("="*60)
            logger.info(f"📋 COPY TRADE SIGNAL RECEIVED")
            logger.info(f"   Wallet: {wallet_address}")
            logger.info(f"   Token: {token_address}")
            logger.info(f"   Amount: {amount_sol:.9f} SOL")
            logger.info(f"   Platform: {platform}")
            logger.info(f"   TX: {tx_url}")
            logger.info("="*60)
            
            # Validate and adjust amount
            minimum_amount = self.platform_minimums.get(platform, self.platform_minimums["default"])
            
            # Calculate copy trade amount
            copy_percentage = self.settings.copy_trade_percentage
            calculated_amount = amount_sol * copy_percentage
            
            # Ensure minimum amount
            if calculated_amount < minimum_amount:
                logger.warning(
                    f"Calculated amount {calculated_amount:.9f} SOL below {platform} minimum {minimum_amount} SOL. "
                    f"Using minimum."
                )
                calculated_amount = minimum_amount
            
            # Cap at maximum position size
            if calculated_amount > self.settings.max_position_size:
                logger.warning(
                    f"Calculated amount {calculated_amount:.4f} SOL exceeds max position size. "
                    f"Using max: {self.settings.max_position_size} SOL"
                )
                calculated_amount = self.settings.max_position_size
            
            logger.info(f"Executing copy trade: Buying {token_address[:8]}... with {calculated_amount:.6f} SOL on {platform}")
            
            # Get platform-specific settings
            platform_config = self.platform_settings.get(platform, self.platform_settings["default"])
            slippage = platform_config["slippage"]
            
            # Execute buy on the same platform
            success = await self.execute_buy(
                token_address=token_address,
                amount_sol=calculated_amount,
                reason=f"Copy trade from {wallet_address[:8]}...",
                metadata={
                    "source_wallet": wallet_address,
                    "source_amount": amount_sol,
                    "source_platform": platform,
                    "source_tx": tx_url,
                    "copy_percentage": copy_percentage
                },
                preferred_dex=platform,  # Use same platform
                slippage=slippage
            )
            
            if success:
                logger.info(f"✅ Copy trade executed successfully on {platform}")
            else:
                logger.error(f"❌ Copy trade failed for {token_address[:8]}... on {platform}")
                
        except Exception as e:
            logger.error(f"Error in copy trade handler: {e}", exc_info=True)
    
    async def execute_buy(
        self,
        token_address: str,
        amount_sol: float,
        reason: str = "Manual buy",
        metadata: Optional[Dict[str, Any]] = None,
        preferred_dex: Optional[str] = None,
        slippage: Optional[float] = None
    ) -> bool:
        """
        Execute a buy order with detailed logging.
        
        Args:
            token_address: Token to buy
            amount_sol: Amount in SOL
            reason: Reason for the buy
            metadata: Additional metadata
            preferred_dex: Preferred DEX to use
            slippage: Slippage tolerance
            
        Returns:
            Success status
        """
        try:
            start_time = time.time()
            
            logger.info("="*60)
            logger.info(f"🔄 EXECUTING BUY ORDER")
            logger.info(f"   Token: {token_address}")
            logger.info(f"   Amount: {amount_sol:.6f} SOL")
            logger.info(f"   Platform: {preferred_dex or 'auto'}")
            logger.info(f"   Slippage: {slippage or 'default'}")
            logger.info(f"   Reason: {reason}")
            
            if metadata:
                logger.info(f"   Metadata: {metadata}")
            
            # Execute transaction
            tx_signature = await transaction_builder.build_and_execute_buy_transaction(
                token_address=token_address,
                amount_sol=amount_sol,
                slippage_tolerance=slippage or 0.01,
                preferred_dex=preferred_dex
            )
            
            execution_time = time.time() - start_time
            
            if tx_signature:
                # Create position record
                position = {
                    "token": token_address,
                    "entry_price": amount_sol,  # This should be actual price
                    "amount": amount_sol,
                    "entry_time": datetime.now(),
                    "tx_signature": tx_signature,
                    "reason": reason,
                    "metadata": metadata or {},
                    "platform": preferred_dex or "auto",
                    "status": "open"
                }
                
                self.positions[token_address] = position
                
                # Log success
                logger.info(f"✅ BUY ORDER SUCCESSFUL")
                logger.info(f"   TX: {tx_signature}")
                logger.info(f"   Solscan: https://solscan.io/tx/{tx_signature}")
                logger.info(f"   Execution Time: {execution_time:.2f}s")
                logger.info("="*60)
                
                # Track position
                await position_tracker.add_position(
                    token_address=token_address,
                    amount_tokens=amount_sol,  # This should be token amount
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
        """Execute a sell order with detailed logging."""
        try:
            position = self.positions.get(token_address)
            if not position:
                logger.error(f"No position found for {token_address}")
                return False
            
            start_time = time.time()
            
            logger.info("="*60)
            logger.info(f"🔄 EXECUTING SELL ORDER")
            logger.info(f"   Token: {token_address}")
            logger.info(f"   Amount: {amount_tokens:.2f} tokens")
            logger.info(f"   Reason: {reason}")
            
            # Use same platform as buy for consistency
            platform = position.get("platform", "auto")
            
            # Execute transaction
            tx_signature = await transaction_builder.build_and_execute_sell_transaction(
                token_address=token_address,
                amount_tokens=amount_tokens,
                preferred_dex=platform
            )
            
            execution_time = time.time() - start_time
            
            if tx_signature:
                # Update position
                position["status"] = "closed"
                position["exit_time"] = datetime.now()
                position["exit_tx"] = tx_signature
                position["sell_reason"] = reason
                
                # Log success
                logger.info(f"✅ SELL ORDER SUCCESSFUL")
                logger.info(f"   TX: {tx_signature}")
                logger.info(f"   Solscan: https://solscan.io/tx/{tx_signature}")
                logger.info(f"   Execution Time: {execution_time:.2f}s")
                logger.info("="*60)
                
                # Remove from position tracker
                await position_tracker.remove_position(token_address, exit_tx=tx_signature)
                
                # Trigger callbacks
                await self._trigger_trade_callback({
                    "type": "sell",
                    "token": token_address,
                    "amount_tokens": amount_tokens,
                    "tx_signature": tx_signature,
                    "timestamp": datetime.now().isoformat(),
                    "reason": reason,
                    "platform": platform
                })
                
                return True
            else:
                logger.error(f"❌ SELL ORDER FAILED after {execution_time:.2f}s")
                return False
                
        except Exception as e:
            logger.error(f"Error executing sell: {e}", exc_info=True)
            return False
    
    async def _monitoring_loop(self) -> None:
        """Monitor positions and apply exit strategies."""
        while True:
            try:
                # Check each position
                for token_address, position in list(self.positions.items()):
                    if position.get("status") != "open":
                        continue
                    
                    # Get current metrics
                    metrics = await position_tracker.get_position_metrics(token_address)
                    if not metrics:
                        continue
                    
                    # Check exit conditions
                    should_sell, reason = self._check_exit_conditions(position, metrics)
                    
                    if should_sell:
                        logger.info(f"Exit condition triggered for {token_address[:8]}...: {reason}")
                        await self.execute_sell(
                            token_address=token_address,
                            amount_tokens=metrics["amount"],
                            reason=reason
                        )
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)
    
    def _check_exit_conditions(
        self,
        position: Dict[str, Any],
        metrics: Dict[str, Any]
    ) -> tuple[bool, str]:
        """Check if position should be sold based on strategy rules."""
        gain_percent = metrics["gain_percent"]
        time_held = metrics["time_held_seconds"]
        
        # Take profit
        if gain_percent >= self.settings.take_profit_percentage:
            return True, f"Take profit: {gain_percent:.1f}% gain"
        
        # Stop loss
        if gain_percent <= -self.settings.stop_loss_percentage:
            return True, f"Stop loss: {gain_percent:.1f}% loss"
        
        # Time-based stop loss
        if self.settings.time_based_stop_loss_minutes > 0:
            if time_held > self.settings.time_based_stop_loss_minutes * 60:
                if gain_percent < 0:
                    return True, f"Time stop: {time_held/60:.0f}min held with {gain_percent:.1f}% loss"
        
        # Trailing stop
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
        return [p for p in self.positions.values() if p.get("status") == "open"]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        active_positions = self.get_active_positions()
        total_trades = len(self.trade_history)
        
        return {
            "active_positions": len(active_positions),
            "total_trades": total_trades,
            "positions": active_positions
        }


# Global strategy engine instance
strategy_engine = None

def initialize_strategy_engine():
    """Initialize the global strategy engine instance."""
    global strategy_engine
    strategy_engine = StrategyEngine()
    return strategy_engine
