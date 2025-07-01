"""
# File: src/monitoring/position_tracker.py
Position tracking system for monitoring open trades and calculating P&L.
This module keeps track of all open positions, their entry prices, and current performance.
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import time

from src.utils.logger import get_logger
from src.core.connection_manager import connection_manager

logger = get_logger("position_tracker")


class PositionTracker:
    """
    Tracks open positions and calculates performance metrics.
    
    This class is like a portfolio manager that keeps track of:
    - What tokens you own
    - When you bought them
    - How much you paid
    - Current profit/loss
    - How long you've held them
    """
    
    def __init__(self):
        # Dictionary to store all positions
        # Key: token_address, Value: position details
        self.positions: Dict[str, Dict[str, Any]] = {}
        
        # Track historical performance
        self.closed_positions: List[Dict[str, Any]] = []
        
        # Performance metrics
        self.total_pnl = 0.0
        self.win_count = 0
        self.loss_count = 0
        
        logger.info("Position tracker initialized")
    
    async def add_position(
        self,
        token_address: str,
        amount_tokens: float,
        entry_price: float,
        entry_tx: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a new position to track.
        
        Think of this like recording a purchase in your investment journal:
        - What did you buy? (token_address)
        - How much? (amount_tokens)
        - At what price? (entry_price)
        - Transaction proof (entry_tx)
        
        Args:
            token_address: The token's contract address
            amount_tokens: Number of tokens purchased
            entry_price: Price in SOL at entry
            entry_tx: Transaction signature for the buy
            metadata: Any additional information about the trade
        """
        position = {
            "token_address": token_address,
            "amount": amount_tokens,
            "entry_price": entry_price,
            "entry_time": datetime.now(),
            "entry_tx": entry_tx,
            "metadata": metadata or {},
            "status": "open",
            "current_price": entry_price,  # Will be updated
            "last_update": time.time()
        }
        
        self.positions[token_address] = position
        
        logger.info(
            f"Added position: {token_address[:8]}... | "
            f"Amount: {amount_tokens:.2f} | "
            f"Entry: {entry_price:.6f} SOL"
        )
    
    async def update_position_price(
        self,
        token_address: str,
        current_price: float
    ) -> None:
        """
        Update the current price for a position.
        
        This is like checking your portfolio value - we need to know
        the current price to calculate if we're in profit or loss.
        
        Args:
            token_address: The token to update
            current_price: Current price in SOL
        """
        if token_address in self.positions:
            self.positions[token_address]["current_price"] = current_price
            self.positions[token_address]["last_update"] = time.time()
            
            # Calculate current P&L
            position = self.positions[token_address]
            gain_percent = ((current_price - position["entry_price"]) / position["entry_price"]) * 100
            
            logger.debug(
                f"Updated {token_address[:8]}... | "
                f"Price: {current_price:.6f} | "
                f"Gain: {gain_percent:+.2f}%"
            )
    
    async def get_position_metrics(
        self,
        token_address: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed metrics for a specific position.
        
        This provides all the information needed to make trading decisions:
        - How much profit/loss?
        - How long held?
        - Current vs entry price
        
        Returns:
            Dictionary with position metrics or None if position not found
        """
        if token_address not in self.positions:
            return None
        
        position = self.positions[token_address]
        current_time = time.time()
        
        # Calculate performance metrics
        entry_price = position["entry_price"]
        current_price = position.get("current_price", entry_price)
        
        # Percentage gain/loss
        gain_percent = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
        
        # Time held in seconds
        time_held = (datetime.now() - position["entry_time"]).total_seconds()
        
        # Absolute profit/loss in SOL
        pnl_sol = (current_price - entry_price) * position["amount"]
        
        return {
            "token_address": token_address,
            "amount": position["amount"],
            "entry_price": entry_price,
            "current_price": current_price,
            "gain_percent": gain_percent,
            "pnl_sol": pnl_sol,
            "time_held_seconds": time_held,
            "entry_time": position["entry_time"],
            "status": position["status"]
        }
    
    async def remove_position(
        self,
        token_address: str,
        exit_price: Optional[float] = None,
        exit_tx: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Remove a position and record the final performance.
        
        This is like closing a trade in your journal - we record:
        - Final price
        - Total profit/loss
        - How long we held
        
        Args:
            token_address: Token to remove
            exit_price: Price at exit (if known)
            exit_tx: Transaction signature for the sell
            
        Returns:
            Final position details or None
        """
        if token_address not in self.positions:
            return None
        
        position = self.positions[token_address]
        
        # Update final metrics
        if exit_price:
            position["exit_price"] = exit_price
        else:
            position["exit_price"] = position.get("current_price", position["entry_price"])
        
        position["exit_time"] = datetime.now()
        position["exit_tx"] = exit_tx
        position["status"] = "closed"
        
        # Calculate final P&L
        entry_price = position["entry_price"]
        exit_price = position["exit_price"]
        final_pnl = (exit_price - entry_price) * position["amount"]
        position["final_pnl"] = final_pnl
        
        # Update statistics
        self.total_pnl += final_pnl
        if final_pnl > 0:
            self.win_count += 1
        else:
            self.loss_count += 1
        
        # Move to closed positions
        self.closed_positions.append(position)
        del self.positions[token_address]
        
        logger.info(
            f"Closed position: {token_address[:8]}... | "
            f"P&L: {final_pnl:+.6f} SOL | "
            f"Return: {((exit_price - entry_price) / entry_price * 100):+.2f}%"
        )
        
        return position
    
    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all open positions."""
        return self.positions.copy()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get overall performance summary.
        
        This is like your trading report card showing:
        - Total profit/loss
        - Win rate
        - Number of trades
        """
        total_trades = self.win_count + self.loss_count
        win_rate = (self.win_count / total_trades * 100) if total_trades > 0 else 0
        
        return {
            "total_pnl": self.total_pnl,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "open_positions": len(self.positions),
            "closed_positions": len(self.closed_positions)
        }
    
    async def update_all_positions(self) -> None:
        """
        Update prices for all positions.
        
        In a real implementation, this would fetch current prices
        from the blockchain or a price API. For now, it's a placeholder
        for when you implement price fetching.
        """
        for token_address in list(self.positions.keys()):
            # TODO: Implement actual price fetching
            # For now, we'll just log that we should update
            logger.debug(f"Should update price for {token_address[:8]}...")
            
            # In production, you would:
            # 1. Fetch current price from DEX or price API
            # 2. Call update_position_price with the new price
            pass


# Global position tracker instance
position_tracker = PositionTracker()


def get_position_tracker() -> PositionTracker:
    """Get the global position tracker instance."""
    return position_tracker
