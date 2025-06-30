"""
Trading strategy engine for the Solana pump.fun sniping bot.
Evaluates events and market conditions to make trading decisions.
"""
# File Location: src/trading/strategy_engine.py

import asyncio
from typing import Dict, Any, Optional, List, Set
import time
from collections import defaultdict

from src.utils.config import config_manager
from typing import Callable
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
        Evaluate price updates for active positions.
        
        Args:
            token_address: Token address with price update
            price: Current price in SOL
            price_change_percent: Price change percentage
        """
        try:
            if token_address in self.active_positions:
                position = self.active_positions[token_address]
                logger.info(
                    f"Price update for active position {position['symbol']}: {price:.8f} SOL ({price_change_percent:.2f}%)",
                    token=token_address
                )
                
                # Update position data
                position['current_price'] = price
                position['price_change_percent'] = price_change_percent
                
                # Check if sell criteria are met
                if self._meets_sell_criteria(position):
                    logger.info(f"Sell criteria met for {position['symbol']}. Executing sell order.", token=token_address)
                    await self.execute_sell(token_address)
                    
        except Exception as e:
            logger.error(f"Error evaluating price update for token {token_address[:8]}...: {e}", exc_info=True)
    
    async def evaluate_volume_spike(self, token_address: str, volume: float, volume_change_percent: float) -> None:
        """
        Evaluate volume spikes for potential trading opportunities.
        
        Args:
            token_address: Token address with volume spike
            volume: Current volume
            volume_change_percent: Volume change percentage
        """
        try:
            if token_address in self.active_positions:
                logger.info(
                    f"Volume spike for active position {token_address[:8]}...: {volume:.2f} ({volume_change_percent:.2f}%)"
                )
                # Volume spikes might influence sell decisions
                position = self.active_positions[token_address]
                position['current_volume'] = volume
                position['volume_change_percent'] = volume_change_percent
                
                if self._meets_sell_criteria(position):
                    logger.info(f"Sell criteria met for {position['symbol']} due to volume spike. Executing sell order.", token=token_address)
                    await self.execute_sell(token_address)
            else:
                # Check if volume spike indicates a buying opportunity for a new token
                if len(self.active_positions) < self.max_positions:
                    logger.info(f"Volume spike detected for non-position token {token_address[:8]}...: Evaluating for buy.")
                    # Fetch token data to evaluate
                    token_data = await connection_manager.fetch_pump_token_data(token_address)
                    if token_data:
                        token_info = TokenInfo(token_data)
                        if self._meets_buy_criteria(token_info):
                            logger.info(f"Token {token_info.symbol} meets buy criteria due to volume spike. Executing buy order.", token=token_address)
                            await self.execute_buy(token_info)
                        else:
                            logger.info(f"Token {token_info.symbol} does not meet buy criteria despite volume spike.", token=token_address)
                    else:
                        logger.error(f"Failed to fetch token data for {token_address[:8]}... despite volume spike.")
                else:
                    logger.warning(f"Volume spike for {token_address[:8]}... but max positions reached ({self.max_positions}). Skipping.")
                    
        except Exception as e:
            logger.error(f"Error evaluating volume spike for token {token_address[:8]}...: {e}", exc_info=True)
    
    async def evaluate_wallet_buy(self, wallet_address: str, token_address: str, amount_sol: float) -> None:
        """
        Evaluate a buy transaction from a tracked wallet for potential mimic buy.
        
        Args:
            wallet_address: Wallet address that made the buy
            token_address: Token address that was bought
            amount_sol: Amount in SOL spent on the buy
        """
        try:
            logger.info(f"Evaluating wallet buy from {wallet_address[:8]}... for token {token_address[:8]}... with {amount_sol:.2f} SOL")
            
            # Check if we have capacity to buy
            if len(self.active_positions) >= self.max_positions:
                logger.warning(
                    f"Cannot mimic buy for {token_address[:8]}... from wallet {wallet_address[:8]}... - max positions reached",
                    max_positions=self.max_positions
                )
                return
            
            # Check balance
            balance = await wallet_manager.get_balance()
            buy_amount = min(amount_sol, self.max_buy_amount_sol)
            if balance < buy_amount * 1.2:  # Add 20% buffer for fees
                logger.warning(
                    f"Insufficient SOL balance to mimic buy for {token_address[:8]}...: {balance:.4f} SOL",
                    required=buy_amount * 1.2
                )
                return
            
            # Fetch token details
            token_data = await connection_manager.fetch_pump_token_data(token_address)
            if not token_data:
                logger.error(f"Failed to fetch token data for {token_address[:8]}...")
                return
            
            token_info = TokenInfo(token_data)
            
            # Execute buy
            logger.info(
                f"Mimicking buy for {token_info.symbol} from wallet {wallet_address[:8]}... with {buy_amount} SOL",
                token=token_address
            )
            
            success = await self.execute_buy(token_info)
            if success:
                logger.info(
                    f"Successfully mimicked buy for {token_info.symbol} from wallet {wallet_address[:8]}...",
                    token=token_address,
                    amount_sol=buy_amount
                )
            else:
                logger.error(
                    f"Failed to mimic buy for {token_info.symbol} from wallet {wallet_address[:8]}...",
                    token=token_address
                )
                
        except Exception as e:
            logger.error(f"Error evaluating wallet buy for token {token_address[:8]}... from wallet {wallet_address[:8]}...: {e}", exc_info=True)
    
    def _meets_buy_criteria(self, token_info: TokenInfo) -> bool:
        """
        Check if token meets buy criteria based on settings.
        
        Args:
            token_info: Information about the token
            
        Returns:
            bool: True if token meets buy criteria
        """
        try:
            # Check market cap
            if token_info.market_cap_sol > self.settings.trading.max_market_cap_sol:
                logger.info(
                    f"Token {token_info.symbol} market cap {token_info.market_cap_sol:.2f} SOL exceeds max {self.settings.trading.max_market_cap_sol:.2f} SOL",
                    token=token_info.address
                )
                return False
            
            # Check liquidity
            if token_info.liquidity_sol < self.settings.trading.min_liquidity_sol:
                logger.info(
                    f"Token {token_info.symbol} liquidity {token_info.liquidity_sol:.2f} SOL below min {self.settings.trading.min_liquidity_sol:.2f} SOL",
                    token=token_info.address
                )
                return False
            
            # Check if token is too old (based on creation time or first trade)
            if token_info.age_seconds > self.settings.trading.max_token_age_seconds:
                logger.info(
                    f"Token {token_info.symbol} age {token_info.age_seconds:.0f}s exceeds max {self.settings.trading.max_token_age_seconds:.0f}s",
                    token=token_info.address
                )
                return False
            
            # Additional criteria can be added here
            return True
            
        except Exception as e:
            logger.error(f"Error checking buy criteria for token {token_info.symbol}: {e}", exc_info=True)
            return False
    
    def _meets_sell_criteria(self, position: Dict[str, Any]) -> bool:
        """
        Check if position meets sell criteria based on settings.
        
        Args:
            position: Information about the active position
            
        Returns:
            bool: True if position meets sell criteria
        """
        try:
            # Check take profit
            if position['price_change_percent'] >= self.settings.trading.take_profit_percent:
                logger.info(
                    f"Take profit triggered for {position['symbol']}: {position['price_change_percent']:.2f}% >= {self.settings.trading.take_profit_percent:.2f}%",
                    token=position['token_address']
                )
                return True
            
            # Check stop loss
            if position['price_change_percent'] <= -self.settings.trading.stop_loss_percent:
                logger.info(
                    f"Stop loss triggered for {position['symbol']}: {position['price_change_percent']:.2f}% <= -{self.settings.trading.stop_loss_percent:.2f}%",
                    token=position['token_address']
                )
                return True
            
            # Check holding time
            holding_time = time.time() - position['buy_time']
            if holding_time >= self.settings.trading.max_holding_time_seconds:
                logger.info(
                    f"Max holding time reached for {position['symbol']}: {holding_time:.0f}s >= {self.settings.trading.max_holding_time_seconds:.0f}s",
                    token=position['token_address']
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking sell criteria for position {position.get('symbol', 'unknown')}: {e}", exc_info=True)
            return False
    
    async def execute_buy(self, token_info: TokenInfo) -> bool:
        """
        Execute a buy order for a token.
        
        Args:
            token_info: Information about the token to buy
            
        Returns:
            bool: True if buy was successful
        """
        try:
            # Calculate buy amount based on settings and available balance
            balance = await wallet_manager.get_balance()
            buy_amount_sol = min(
                balance * 0.9,  # Leave 10% buffer for fees and other trades
                self.max_buy_amount_sol,
                self.settings.trading.buy_amount_sol
            )
            
            if buy_amount_sol < self.settings.trading.min_buy_amount_sol:
                logger.warning(
                    f"Buy amount {buy_amount_sol:.4f} SOL for {token_info.symbol} below minimum {self.settings.trading.min_buy_amount_sol:.4f} SOL. Skipping.",
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
                        callback("BUY", token_info.address, buy_amount_sol / token_info.price_sol, token_info.price_sol)
                    except Exception as e:
                        logger.error(f"Error in trade callback for buy {token_info.symbol}: {e}")
                
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
            token_address: Token address to sell
            
        Returns:
            bool: True if sell was successful
        """
        try:
            if token_address not in self.active_positions:
                logger.warning(f"No active position found for {token_address[:8]}... to sell")
                return False
            
            position = self.active_positions[token_address]
            logger.info(f"Executing sell for {position['symbol']}", token=token_address)
            
            # Build and execute sell transaction
            # For simplicity, sell entire position
            tx_signature = await transaction_builder.build_and_execute_sell_transaction(token_address)
            
            if tx_signature:
                logger.info(f"Sell transaction successful for {position['symbol']}: {tx_signature[:8]}...", token=token_address)
                
                # Notify callbacks about trade
                sell_amount = position.get('token_balance', 0.0)  # This would be updated by actual balance
                sell_price = position['current_price']
                
                for callback in self.trade_callbacks:
                    try:
                        callback("SELL", token_address, sell_amount, sell_price)
                    except Exception as e:
                        logger.error(f"Error in trade callback for sell {position['symbol']}: {e}")
                
                # Remove from active positions
                del self.active_positions[token_address]
                return True
            else:
                logger.error(f"Sell transaction failed for {position['symbol']}", token=token_address)
                return False
                
        except Exception as e:
            logger.error(f"Error executing sell for token {token_address[:8]}...: {e}", exc_info=True)
            return False
    
    async def _monitor_positions(self) -> None:
        """Monitor active positions for sell conditions."""
        while self.running:
            try:
                # Check each active position for sell conditions
                positions_to_sell = []
                for token_address, position in list(self.active_positions.items()):
                    if self._meets_sell_criteria(position):
                        positions_to_sell.append(token_address)
                
                # Execute sells for positions meeting criteria
                for token_address in positions_to_sell:
                    await self.execute_sell(token_address)
                
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                logger.error(f"Error monitoring positions: {e}", exc_info=True)
                await asyncio.sleep(5)  # Wait before retrying on error
    
    def register_trade_callback(self, callback: Callable[[str, str, float, float], None]) -> None:
        """
        Register a callback for trade executions.
        
        Args:
            callback: Function to call when trade executed (params: trade_type, token_address, amount, price)
        """
        self.trade_callbacks.append(callback)
        logger.info(f"Registered trade callback. Total callbacks: {len(self.trade_callbacks)}")


# Global strategy engine instance (will be initialized later)
strategy_engine = None

def initialize_strategy_engine():
    """Initialize the global strategy engine instance."""
    global strategy_engine
    strategy_engine = StrategyEngine()
    return strategy_engine
