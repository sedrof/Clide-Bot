"""
Simplified logging configuration for the Solana pump.fun sniping bot.
Fixed for Python 3.13 compatibility.
"""

import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
from datetime import datetime

# Simple console formatter
class SimpleConsoleFormatter(logging.Formatter):
    """Simple formatter with color support."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Purple
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        
        # Format the message
        message = super().format(record)
        return message


def setup_logging(
    level: str = "DEBUG",
    file_path: str = "logs/bot.log",
    max_file_size_mb: int = 100,
    backup_count: int = 5,
    console_output: bool = True
) -> None:
    """
    Setup simple logging with file rotation and console output.
    """
    
    # Create logs directory if it doesn't exist
    log_file = Path(file_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=max_file_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, level.upper()))
    
    # Simple file formatter
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        
        # Console formatter with colors
        console_formatter = SimpleConsoleFormatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # Log initialization
    root_logger.info(f"Logging initialized - Level: {level}, File: {file_path}")
    print(f"✓ Logging initialized - Level: {level}, File: {file_path}")


class BotLogger:
    """Enhanced logger for bot-specific functionality."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._trade_count = 0
        self._error_count = 0
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        if extra_info:
            message = f"{message} | {extra_info}"
        self.logger.info(message)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        if extra_info:
            message = f"{message} | {extra_info}"
        self.logger.warning(message)
    
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self._error_count += 1
        kwargs['error_count'] = self._error_count
        extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        if extra_info:
            message = f"{message} | {extra_info}"
        self.logger.error(message, exc_info=kwargs.get('exc_info', False))
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        if extra_info:
            message = f"{message} | {extra_info}"
        self.logger.debug(message)
    
    def trade_executed(self, action: str, token: str, amount: float, price: float, **kwargs):
        """Log trade execution with structured data."""
        self._trade_count += 1
        self.logger.info(
            f"TRADE EXECUTED: {action} | token={token[:8]}... | amount={amount:.6f} | "
            f"price={price:.6f} | trade_number={self._trade_count}"
        )
    
    def position_update(self, token: str, entry_price: float, current_price: float, 
                       gain_percent: float, time_held: float, **kwargs):
        """Log position updates with performance metrics."""
        self.logger.info(
            f"POSITION UPDATE: {token[:8]}... | entry={entry_price:.6f} | "
            f"current={current_price:.6f} | gain={gain_percent:+.2f}% | held={time_held:.0f}s"
        )
    
    def strategy_triggered(self, rule_name: str, token: str, conditions: dict, **kwargs):
        """Log when a selling strategy rule is triggered."""
        cond_str = ", ".join([f"{k}={v}" for k, v in conditions.items()])
        self.logger.info(f"STRATEGY TRIGGERED: {rule_name} | token={token[:8]}... | {cond_str}")
    
    def performance_summary(self, total_trades: int, successful_trades: int, 
                          total_pnl: float, avg_hold_time: float, **kwargs):
        """Log performance summary statistics."""
        success_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0
        self.logger.info(
            f"PERFORMANCE SUMMARY: trades={total_trades} | successful={successful_trades} | "
            f"success_rate={success_rate:.1f}% | pnl={total_pnl:.4f} SOL | avg_hold={avg_hold_time:.0f}s"
        )
    
    def connection_status(self, service: str, status: str, **kwargs):
        """Log connection status for various services."""
        self.logger.info(f"CONNECTION {status}: {service}")
    
    def token_detected(self, token: str, market_cap: float, liquidity: float, **kwargs):
        """Log new token detection."""
        symbol = kwargs.get('symbol', 'Unknown')
        self.logger.info(
            f"NEW TOKEN DETECTED: {symbol} ({token[:8]}...) | "
            f"market_cap=${market_cap:,.2f} | liquidity=${liquidity:,.2f}"
        )
    
    def get_stats(self) -> dict:
        """Get logger statistics."""
        return {
            "trade_count": self._trade_count,
            "error_count": self._error_count
        }


def get_logger(name: str) -> BotLogger:
    """Get a bot logger instance."""
    return BotLogger(name)


# Pre-configured loggers for different modules
main_logger = get_logger("main")
trading_logger = get_logger("trading")
monitoring_logger = get_logger("monitoring")
strategy_logger = get_logger("strategy")
connection_logger = get_logger("connection")
