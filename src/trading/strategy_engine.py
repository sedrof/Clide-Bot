"""
Trading strategy engine for the Solana pump.fun sniping bot.
Evaluates events and market conditions to make trading decisions.
Includes copy trading functionality for tracked wallets.
"""
# File Location: src/trading/strategy_engine.py

import asyncio
from typing import Dict, Any, Optional, List, Set, Callable
import time
from collections import defaultdict

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.core.connection_manager import connection_manager
from src.core.wallet_manager import wallet_manager
from src.core.transaction_builder import transaction_builder
from src.monitoring.pump_monitor import TokenInfo

logger = get_logger("strategy")


class StrategyEngine:
    """Evaluates market conditions and events to make trading decisions."""
    
    def __init__(self):
        self.settings = config_manager.get_settings()
        self.running: bool = False
        self.active_positions: Dict[str, Dict[str, Any]] = {}
        self.max_positions: int = self.settings.trading.max_positions
        self.max_buy_amount_sol: float = self.settings.trading.max_buy_amount_sol
        self.trade_callbacks: List[Callable[[str, str, float, float], None]] = []
        
        # Sell strategy settings
        self.sell_strategy = config_manager.get_sell_strategy()
        
        # Performance tracking
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        
    async def start(self) -> None:
        """Start the strategy engine."""
        if self.running:
            logger.warning("Strategy engine already running")
            return
            
        self.running = True
        logger.info("Starting strategy engine")
        
        # Initialize any background tasks if needed
        asyncio.create_task(self._monitor_positions())
    
    async def stop(self) -> None:
        """Stop the strategy engine."""
        self.running = False
        logger.info("Stopping strategy engine")
    
    async def _monitor_positions(self) -> None:
        """Monitor active positions for selling opportunities."""
        while self.running:
            try:
                # Check each position against selling rules
                for token_address in list(self.active_positions.keys()):
                    position = self.active_positions[token_address]
                    
                    # Check if position should be sold
                    if await self._should_sell_position(position):
                        await self.execute_sell(token_address)
                
                # Wait before next check
                check_interval = self.sell_strategy.settings.check_interval_ms / 1000
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error monitoring positions: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def evaluate_new_token(self, token_info: TokenInfo) -> None:
        """
        Evaluate a newly detected token for potential buy.
        
        Args:
            token_info: Information about the new token
        """
        try:
            logger.info(f"Evaluating new token: {token_info.symbol}", token=token_info.address)
            
            # Check if we have capacity for new positions
            if len(self.active_positions) >= self.max_positions:
                logger.warning(f"Max positions reached ({self.max_positions}). Skipping {token_info.symbol} evaluation.")
                return
            
            # Check if token meets basic criteria
            if self._meets_buy_criteria(token_info):
                logger.info(f"Token {token_info.symbol} meets buy criteria. Executing buy order.", token=token_info.address)
                await self.execute_buy(token_info)
            else:
                logger.info(f"Token {token_info.symbol} does not meet buy criteria. Skipping.", token=token_info.address)
                
        except Exception as e:
            logger.error(f"Error evaluating new token {token_info.symbol}: {e}", exc_info=True)
    
    async def evaluate_price_update(self, token_address: str, price: float, price_change_percent: float) -> None:
        """
        Evaluate price update for an active position.
        
        Args:
            token_address: Token address
            price: Current price in SOL
            price_change_percent: Price change percentage
        """
        if token_address in self.active_positions:
            position = self.active_positions[token_address]
            position['current_price'] = price
            position['price_change_percent'] = price_change_percent
            
            logger.debug(
                f"Price update for {position['symbol']}: {price:.6f} SOL ({price_change_percent:+.2f}%)",
                token=token_address
            )
    
    async def evaluate_volume_spike(self, token_address: str, volume_spike_ratio: float) -> None:
        """
        Evaluate volume spike for potential action.
        
        Args:
            token_address: Token address
            volume_spike_ratio: Ratio of current volume to average
        """
        if token_address in self.active_positions:
            position = self.active_positions[token_address]
            position['volume_spike_ratio'] = volume_spike_ratio
            
            logger.info(
                f"Volume spike detected for {position['symbol']}: {volume_spike_ratio:.2f}x average",
                token=token_address
            )
    
    def _meets_buy_criteria(self, token_info: TokenInfo) -> bool:
        """
        Check if a token meets the criteria for buying.
        
        Args:
            token_info: Token information
            
        Returns:
            True if meets criteria, False otherwise
        """
        # Basic criteria checks
        min_market_cap = self.settings.monitoring.min_market_cap
        
        if token_info.market_cap < min_market_cap:
            logger.debug(f"Token {token_info.symbol} market cap ({token_info.market_cap}) below minimum ({min_market_cap})")
            return False
        
        # Check token age
        max_age_minutes = self.settings.monitoring.max_token_age_minutes
        token_age_minutes = (time.time() - token_info.created_timestamp) / 60
        
        if token_age_minutes > max_age_minutes:
            logger.debug(f"Token {token_info.symbol} too old ({token_age_minutes:.1f} minutes)")
            return False
        
        # Add more criteria as needed
        return True
    
    async def _should_sell_position(self, position: Dict[str, Any]) -> bool:
        """
        Check if a position should be sold based on selling rules.
        
        Args:
            position: Position information
            
        Returns:
            True if should sell, False otherwise
        """
        # Check emergency stop loss
        price_change = position.get('price_change_percent', 0)
        if price_change <= -self.sell_strategy.settings.emergency_stop_loss:
            logger.warning(f"Emergency stop loss triggered for {position['symbol']}: {price_change:.2f}%")
            return True
        
        # Check max hold time
        hold_time = time.time() - position['buy_time']
        if hold_time > self.sell_strategy.settings.max_hold_time:
            logger.info(f"Max hold time reached for {position['symbol']}: {hold_time:.0f}s")
            return True
        
        # Check selling rules
        for rule in self.sell_strategy.selling_rules:
            if self._evaluate_sell_rule(rule, position):
                logger.info(f"Sell rule '{rule.name}' triggered for {position['symbol']}")
                return True
        
        return False
    
    def _evaluate_sell_rule(self, rule: Any, position: Dict[str, Any]) -> bool:
        """
        Evaluate a specific sell rule against a position.
        
        Args:
            rule: Sell rule to evaluate
            position: Position information
            
        Returns:
            True if rule conditions met, False otherwise
        """
        try:
            conditions = rule.conditions
            
            # Check price gain condition
            if 'price_gain_percent' in conditions:
                required_gain = float(conditions['price_gain_percent'])
                actual_gain = position.get('price_change_percent', 0)
                if actual_gain < required_gain:
                    return False
            
            # Check hold time condition
            if 'min_hold_time_seconds' in conditions:
                min_hold = float(conditions['min_hold_time_seconds'])
                actual_hold = time.time() - position['buy_time']
                if actual_hold < min_hold:
                    return False
            
            # Check volume spike condition
            if 'volume_spike_ratio' in conditions:
                required_spike = float(conditions['volume_spike_ratio'])
                actual_spike = position.get('volume_spike_ratio', 1.0)
                if actual_spike < required_spike:
                    return False
            
            # All conditions met
            return True
            
        except Exception as e:
            logger.error(f"Error evaluating sell rule {rule.name}: {e}")
            return False
    
    async def execute_buy(self, token_info: TokenInfo) -> bool:
        """
        Execute a buy order for a token.
        
        Args:
            token_info: Token information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate buy amount (could be dynamic based on strategy)
            buy_amount_sol = min(self.max_buy_amount_sol, 0.1)  # Start with small amounts
            
            # Check wallet balance
            balance = await wallet_manager.get_balance()
            if balance < buy_amount_sol + 0.01:  # Keep some SOL for fees
                logger.warning(
                    f"Insufficient balance for buy. Required: {buy_amount_sol:.4f} SOL, Available: {balance:.4f} SOL",
                    token=token_info.address
                )
                return False
            
            logger.info(f"Executing buy for {token_info.symbol} with {buy_amount_sol:.4f} SOL", token=token_info.address)
            
            # Build and execute transaction
            tx_signature = await transaction_builder.build_and_execute_buy_transaction(
                token_info.address,
                buy_amount_sol
            )
            
            if tx_signature:
                logger.info(f"Buy transaction successful for {token_info.symbol}: {tx_signature[:8]}...", token=token_info.address)
                
                # Record position
                self.active_positions[token_info.address] = {
                    'token_address': token_info.address,
                    'symbol': token_info.symbol,
                    'buy_price': token_info.price_sol,
                    'buy_amount_sol': buy_amount_sol,
                    'buy_time': time.time(),
                    'current_price': token_info.price_sol,
                    'price_change_percent': 0.0,
                    'current_volume': token_info.volume_24h_sol,
                    'volume_change_percent': 0.0
                }
                
                # Notify callbacks about trade
                for callback in self.trade_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback("BUY", token_info.address, buy_amount_sol / token_info.price_sol, token_info.price_sol)
                        else:
                            callback("BUY", token_info.address, buy_amount_sol / token_info.price_sol, token_info.price_sol)
                    except Exception as e:
                        logger.error(f"Error in trade callback for buy {token_info.symbol}: {e}")
                
                self.total_trades += 1
                return True
            else:
                logger.error(f"Buy transaction failed for {token_info.symbol}", token=token_info.address)
                return False
                
        except Exception as e:
            logger.error(f"Error executing buy for {token_info.symbol}: {e}", exc_info=True, token=token_info.address)
            return False
    
    async def execute_sell(self, token_address: str) -> bool:
        """
        Execute a sell order for a token position.
        
        Args:
            token_address: Token to sell
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if token_address not in self.active_positions:
                logger.warning(f"No active position for token {token_address[:8]}...")
                return False
            
            position = self.active_positions[token_address]
            logger.info(f"Executing sell for {position['symbol']}", token=token_address)
            
            # Calculate token amount to sell (placeholder - need actual balance check)
            # This would need to query actual token balance
            token_amount = position['buy_amount_sol'] / position['buy_price']
            
            # Build and execute transaction
            tx_signature = await transaction_builder.build_and_execute_sell_transaction(
                token_address,
                token_amount
            )
            
            if tx_signature:
                logger.info(f"Sell transaction successful for {position['symbol']}: {tx_signature[:8]}...", token=token_address)
                
                # Calculate PnL
                sell_price = position.get('current_price', position['buy_price'])
                pnl = (sell_price - position['buy_price']) * token_amount
                
                # Update stats
                if pnl > 0:
                    self.successful_trades += 1
                else:
                    self.failed_trades += 1
                
                # Notify callbacks about trade
                for callback in self.trade_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback("SELL", token_address, token_amount, sell_price)
                        else:
                            callback("SELL", token_address, token_amount, sell_price)
                    except Exception as e:
                        logger.error(f"Error in trade callback for sell {position['symbol']}: {e}")
                
                # Remove position
                del self.active_positions[token_address]
                
                return True
            else:
                logger.error(f"Sell transaction failed for {position['symbol']}", token=token_address)
                return False
                
        except Exception as e:
            logger.error(f"Error executing sell for {token_address}: {e}", exc_info=True)
            return False
    
    async def handle_tracked_wallet_buy(self, wallet_address: str, token_address: str, amount_sol: float) -> None:
        """
        Handle buy signal from tracked wallet - execute copy trade.
        
        Args:
            wallet_address: The tracked wallet that made the buy
            token_address: The token that was bought
            amount_sol: Amount in SOL that was spent
        """
        try:
            logger.info(
                f"Copy trade signal: Wallet {wallet_address[:8]}... bought "
                f"token {token_address[:8]}... for {amount_sol:.4f} SOL"
            )
            
            # Check if we have capacity for new positions
            if len(self.active_positions) >= self.max_positions:
                logger.warning(
                    f"Max positions reached ({self.max_positions}). "
                    f"Skipping copy trade for {token_address[:8]}..."
                )
                return
            
            # Check if we already have a position in this token
            if token_address in self.active_positions:
                logger.info(f"Already have position in {token_address[:8]}... Skipping.")
                return
            
            # Determine buy amount (use configured max or match tracked wallet, whichever is less)
            buy_amount = min(amount_sol, self.max_buy_amount_sol)
            
            # Check wallet balance
            balance = await wallet_manager.get_balance()
            if balance < buy_amount + 0.01:  # Keep 0.01 SOL for fees
                logger.warning(
                    f"Insufficient balance for copy trade. "
                    f"Required: {buy_amount:.4f} SOL, Available: {balance:.4f} SOL"
                )
                return
            
            logger.info(
                f"Executing copy trade: Buying {token_address[:8]}... "
                f"with {buy_amount:.4f} SOL"
            )
            
            # Execute the buy
            success = await self._execute_copy_trade_buy(token_address, buy_amount)
            
            if success:
                logger.info(
                    f"Copy trade successful for {token_address[:8]}... "
                    f"Amount: {buy_amount:.4f} SOL"
                )
            else:
                logger.error(f"Copy trade failed for {token_address[:8]}...")
                
        except Exception as e:
            logger.error(f"Error handling tracked wallet buy: {str(e)}", exc_info=True)
    
    async def _execute_copy_trade_buy(self, token_address: str, amount_sol: float) -> bool:
        """
        Execute a buy order for copy trading.
        
        Args:
            token_address: Token to buy
            amount_sol: Amount in SOL to spend
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Build and execute transaction
            tx_signature = await transaction_builder.build_and_execute_buy_transaction(
                token_address,
                amount_sol
            )
            
            if tx_signature:
                logger.info(
                    f"Copy trade transaction successful: {tx_signature[:8]}... "
                    f"Token: {token_address[:8]}..."
                )
                
                # Record position
                self.active_positions[token_address] = {
                    'token_address': token_address,
                    'symbol': token_address[:8] + "...",  # Abbreviated for now
                    'buy_price': 0.0,  # Will be updated when we get price data
                    'buy_amount_sol': amount_sol,
                    'buy_time': time.time(),
                    'current_price': 0.0,
                    'price_change_percent': 0.0,
                    'current_volume': 0.0,
                    'volume_change_percent': 0.0,
                    'is_copy_trade': True
                }
                
                # Notify callbacks about trade
                for callback in self.trade_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback("BUY", token_address, amount_sol, 0.0)
                        else:
                            callback("BUY", token_address, amount_sol, 0.0)
                    except Exception as e:
                        logger.error(f"Error in trade callback: {str(e)}")
                
                self.total_trades += 1
                return True
            else:
                logger.error(f"Copy trade transaction failed for {token_address[:8]}...")
                return False
                
        except Exception as e:
            logger.error(f"Error executing copy trade buy: {str(e)}", exc_info=True)
            return False
    
    def register_trade_callback(self, callback: Callable[[str, str, float, float], None]) -> None:
        """
        Register a callback for trade events.
        
        Args:
            callback: Function to call when trade occurs (trade_type, token_address, amount, price)
        """
        self.trade_callbacks.append(callback)
        logger.info(f"Registered trade callback. Total callbacks: {len(self.trade_callbacks)}")
    
    def register_with_wallet_tracker(self):
        """Register copy trading callback with wallet tracker."""
        try:
            from src.monitoring.wallet_tracker import wallet_tracker
            if wallet_tracker:
                # Register async callback for tracked wallet buys
                wallet_tracker.register_buy_callback(self.handle_tracked_wallet_buy)
                logger.info("Registered copy trading callback with wallet tracker")
            else:
                logger.warning("Wallet tracker not available for registration")
        except Exception as e:
            logger.error(f"Error registering with wallet tracker: {str(e)}")
    
    def get_active_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get current active positions."""
        return self.active_positions.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get strategy engine statistics."""
        return {
            'total_trades': self.total_trades,
            'successful_trades': self.successful_trades,
            'failed_trades': self.failed_trades,
            'active_positions': len(self.active_positions),
            'win_rate': (self.successful_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        }


# Global strategy engine instance - DO NOT instantiate here!
strategy_engine = None

def initialize_strategy_engine():
    """Initialize the global strategy engine instance."""
    global strategy_engine
    strategy_engine = StrategyEngine()
    return strategy_engine