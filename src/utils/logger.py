"""
Structured logging configuration for the Solana pump.fun sniping bot.
Provides centralized logging with file rotation and console output.
"""

import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
import structlog
from rich.console import Console
from rich.logging import RichHandler

console = Console()


def setup_logging(
    level: str = "DEBUG",
    file_path: str = "logs/bot.log",
    max_file_size_mb: int = 100,
    backup_count: int = 5,
    console_output: bool = True
) -> None:
    """
    Setup structured logging with file rotation and optional console output.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        file_path: Path to log file
        max_file_size_mb: Maximum size of log file in MB before rotation
        backup_count: Number of backup files to keep
        console_output: Whether to output logs to console
    """
    
    # Create logs directory if it doesn't exist
    log_file = Path(file_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        filename=file_path,
        maxBytes=max_file_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler with Rich formatting
    if console_output:
        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True
        )
        console_formatter = logging.Formatter(
            '%(message)s'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)


class BotLogger:
    """Enhanced logger for bot-specific functionality."""
    
    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)
        self._trade_count = 0
        self._error_count = 0
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self._error_count += 1
        self.logger.error(message, error_count=self._error_count, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self.logger.debug(message, **kwargs)
    
    def trade_executed(self, action: str, token: str, amount: float, price: float, **kwargs):
        """Log trade execution with structured data."""
        self._trade_count += 1
        self.logger.info(
            f"Trade executed: {action}",
            action=action,
            token=token,
            amount=amount,
            price=price,
            trade_number=self._trade_count,
            **kwargs
        )
    
    def position_update(self, token: str, entry_price: float, current_price: float, 
                       gain_percent: float, time_held: float, **kwargs):
        """Log position updates with performance metrics."""
        self.logger.info(
            f"Position update: {token[:8]}...",
            token=token,
            entry_price=entry_price,
            current_price=current_price,
            gain_percent=gain_percent,
            time_held_seconds=time_held,
            **kwargs
        )
    
    def strategy_triggered(self, rule_name: str, token: str, conditions: dict, **kwargs):
        """Log when a selling strategy rule is triggered."""
        self.logger.info(
            f"Strategy triggered: {rule_name}",
            rule_name=rule_name,
            token=token,
            conditions=conditions,
            **kwargs
        )
    
    def performance_summary(self, total_trades: int, successful_trades: int, 
                          total_pnl: float, avg_hold_time: float, **kwargs):
        """Log performance summary statistics."""
        success_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0
        self.logger.info(
            "Performance Summary",
            total_trades=total_trades,
            successful_trades=successful_trades,
            success_rate_percent=round(success_rate, 2),
            total_pnl_sol=total_pnl,
            avg_hold_time_seconds=avg_hold_time,
            **kwargs
        )
    
    def connection_status(self, service: str, status: str, **kwargs):
        """Log connection status for various services."""
        self.logger.info(
            f"Connection {status}: {service}",
            service=service,
            status=status,
            **kwargs
        )
    
    def token_detected(self, token: str, market_cap: float, liquidity: float, **kwargs):
        """Log new token detection."""
        self.logger.info(
            f"New token detected: {token[:8]}...",
            token=token,
            market_cap=market_cap,
            liquidity=liquidity,
            **kwargs
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
