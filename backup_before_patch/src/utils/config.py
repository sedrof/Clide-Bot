"""
Configuration management for the Solana pump.fun sniping bot.
Handles loading and validation of configuration files.
"""

import json
import os
from typing import Dict, Any, List, Optional
import yaml
from dataclasses import dataclass, field
from jsonschema import validate, ValidationError

from src.utils.logger import get_logger

logger = get_logger("config")


@dataclass
class SolanaConfig:
    rpc_endpoints: List[str]
    websocket_endpoint: str
    commitment: str
    timeout: int


@dataclass
class PumpFunConfig:
    api_endpoint: str
    websocket_endpoint: str
    program_id: str


@dataclass
class RaydiumConfig:
    program_id: str


@dataclass
class TradingConfig:
    max_positions: int
    max_buy_amount_sol: float


@dataclass
class MonitoringConfig:
    new_token_check_interval: int
    price_check_interval: int
    volume_check_interval: int
    max_token_age_minutes: int
    min_market_cap: int
    volume_spike_threshold: float


@dataclass
class TrackingConfig:
    wallets: List[str]

@dataclass
class WalletConfig:
    public_key: str
    keypair: List[int]


@dataclass
class LoggingConfig:
    level: str
    file_path: str
    max_file_size_mb: int
    backup_count: int
    console_output: bool


@dataclass
class BotSettings:
    solana: SolanaConfig
    pump_fun: PumpFunConfig
    raydium: RaydiumConfig
    trading: TradingConfig
    monitoring: MonitoringConfig
    tracking: TrackingConfig
    logging: LoggingConfig


@dataclass
class SellRule:
    name: str
    priority: int
    action: str
    conditions: Dict[str, str]


@dataclass
class SellStrategySettings:
    check_interval_ms: int
    max_hold_time: int
    emergency_stop_loss: float


@dataclass
class ExecutionSettings:
    slippage_tolerance: float
    priority_fee: float


@dataclass
class SellStrategy:
    settings: SellStrategySettings
    execution: ExecutionSettings
    selling_rules: List[SellRule]


class ConfigManager:
    """Manages configuration loading and validation."""
    
    def __init__(self):
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.settings_path = os.path.join(self.base_path, "../../config", "settings.json")
        self.wallet_path = os.path.join(self.base_path, "../../config", "wallet.json")
        self.sell_strategy_path = os.path.join(self.base_path, "../../config", "sell_strategy.yaml")
        
        self._settings: Optional[BotSettings] = None
        self._wallet_data: Optional[Dict[str, Any]] = None
        self._sell_strategy: Optional[SellStrategy] = None
        
        # JSON schema for settings validation
        self.settings_schema = {
            "type": "object",
            "properties": {
                "solana": {
                    "type": "object",
                    "properties": {
                        "rpc_endpoints": {"type": "array", "items": {"type": "string"}},
                        "websocket_endpoint": {"type": "string"},
                        "commitment": {"type": "string"},
                        "timeout": {"type": "number"}
                    },
                    "required": ["rpc_endpoints", "websocket_endpoint", "commitment", "timeout"]
                },
                "pump_fun": {
                    "type": "object",
                    "properties": {
                        "api_endpoint": {"type": "string"},
                        "websocket_endpoint": {"type": "string"},
                        "program_id": {"type": "string"}
                    },
                    "required": ["api_endpoint", "websocket_endpoint", "program_id"]
                },
                "raydium": {
                    "type": "object",
                    "properties": {
                        "program_id": {"type": "string"}
                    },
                    "required": ["program_id"]
                },
                "trading": {
                    "type": "object",
                    "properties": {
                        "max_positions": {"type": "number"},
                        "max_buy_amount_sol": {"type": "number"}
                    },
                    "required": ["max_positions", "max_buy_amount_sol"]
                },
                "monitoring": {
                    "type": "object",
                    "properties": {
                        "new_token_check_interval": {"type": "number"},
                        "price_check_interval": {"type": "number"},
                        "volume_check_interval": {"type": "number"},
                        "max_token_age_minutes": {"type": "number"},
                        "min_market_cap": {"type": "number"},
                        "volume_spike_threshold": {"type": "number"}
                    },
                    "required": [
                        "new_token_check_interval", "price_check_interval", 
                        "volume_check_interval", "max_token_age_minutes",
                        "min_market_cap", "volume_spike_threshold"
                    ]
                },
                "tracking": {
                    "type": "object",
                    "properties": {
                        "wallets": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["wallets"]
                },
                "logging": {
                    "type": "object",
                    "properties": {
                        "level": {"type": "string"},
                        "file_path": {"type": "string"},
                        "max_file_size_mb": {"type": "number"},
                        "backup_count": {"type": "number"},
                        "console_output": {"type": "boolean"}
                    },
                    "required": ["level", "file_path", "max_file_size_mb", "backup_count", "console_output"]
                }
            },
            "required": ["solana", "pump_fun", "raydium", "trading", "monitoring", "tracking", "logging"]
        }
    
    def load_all(self) -> None:
        """Load all configuration files."""
        try:
            self._load_settings()
            self._load_wallet()
            self._load_sell_strategy()
            logger.info("All configurations loaded successfully")
        except Exception as e:
            logger.error(f"Error loading configurations: {e}")
            raise
    
    def _load_settings(self) -> None:
        """Load settings from settings.json."""
        try:
            with open(self.settings_path, 'r') as f:
                settings_data = json.load(f)
            
            # Validate settings against schema
            validate(instance=settings_data, schema=self.settings_schema)
            
            # Convert to BotSettings object
            self._settings = BotSettings(
                solana=SolanaConfig(
                    rpc_endpoints=settings_data['solana']['rpc_endpoints'],
                    websocket_endpoint=settings_data['solana']['websocket_endpoint'],
                    commitment=settings_data['solana']['commitment'],
                    timeout=settings_data['solana']['timeout']
                ),
                pump_fun=PumpFunConfig(
                    api_endpoint=settings_data['pump_fun']['api_endpoint'],
                    websocket_endpoint=settings_data['pump_fun']['websocket_endpoint'],
                    program_id=settings_data['pump_fun']['program_id']
                ),
                raydium=RaydiumConfig(
                    program_id=settings_data['raydium']['program_id']
                ),
                trading=TradingConfig(
                    max_positions=settings_data['trading']['max_positions'],
                    max_buy_amount_sol=settings_data['trading']['max_buy_amount_sol']
                ),
                monitoring=MonitoringConfig(
                    new_token_check_interval=settings_data['monitoring']['new_token_check_interval'],
                    price_check_interval=settings_data['monitoring']['price_check_interval'],
                    volume_check_interval=settings_data['monitoring']['volume_check_interval'],
                    max_token_age_minutes=settings_data['monitoring']['max_token_age_minutes'],
                    min_market_cap=settings_data['monitoring']['min_market_cap'],
                    volume_spike_threshold=settings_data['monitoring']['volume_spike_threshold']
                ),
                tracking=TrackingConfig(
                    wallets=settings_data['tracking']['wallets']
                ),
                logging=LoggingConfig(
                    level=settings_data['logging']['level'],
                    file_path=settings_data['logging']['file_path'],
                    max_file_size_mb=settings_data['logging']['max_file_size_mb'],
                    backup_count=settings_data['logging']['backup_count'],
                    console_output=settings_data['logging']['console_output']
                )
            )
            logger.info(f"Loaded settings from {self.settings_path}")
            
        except ValidationError as ve:
            logger.error(f"Settings validation error: {ve.message}")
            raise
        except Exception as e:
            logger.error(f"Error loading settings from {self.settings_path}: {e}")
            raise
    
    def _load_wallet(self) -> None:
        """Load wallet data from wallet.json."""
        try:
            with open(self.wallet_path, 'r') as f:
                self._wallet_data = json.load(f)
            logger.info(f"Loaded wallet data from {self.wallet_path}")
        except Exception as e:
            logger.error(f"Error loading wallet data from {self.wallet_path}: {e}")
            raise
    
    def get_wallet(self) -> WalletConfig:
        """Get the loaded wallet data as a WalletConfig object."""
        if self._wallet_data is None:
            raise ValueError("Wallet data not loaded")
        return WalletConfig(
            public_key=self._wallet_data.get("public_key", ""),
            keypair=self._wallet_data.get("keypair", [])
        )
    
    def _load_sell_strategy(self) -> None:
        """Load sell strategy from sell_strategy.yaml."""
        try:
            with open(self.sell_strategy_path, 'r') as f:
                strategy_data = yaml.safe_load(f)
            
            settings_data = strategy_data['settings']
            execution_data = strategy_data['execution']
            
            # Parse selling rules
            selling_rules = []
            for rule_data in strategy_data.get('selling_rules', []):
                selling_rules.append(SellRule(
                    name=rule_data['name'],
                    priority=rule_data['priority'],
                    action=rule_data['action'],
                    conditions=rule_data.get('conditions', {})
                ))
            
            self._sell_strategy = SellStrategy(
                settings=SellStrategySettings(
                    check_interval_ms=settings_data['check_interval_ms'],
                    max_hold_time=settings_data['max_hold_time'],
                    emergency_stop_loss=settings_data['emergency_stop_loss']
                ),
                execution=ExecutionSettings(
                    slippage_tolerance=execution_data['slippage_tolerance'],
                    priority_fee=execution_data['priority_fee']
                ),
                selling_rules=selling_rules
            )
            logger.info(f"Loaded sell strategy from {self.sell_strategy_path}")
            
        except Exception as e:
            logger.error(f"Error loading sell strategy from {self.sell_strategy_path}: {e}")
            raise
    
    def get_settings(self) -> BotSettings:
        """Get the loaded bot settings."""
        if self._settings is None:
            raise ValueError("Settings not loaded")
        return self._settings
    
    def get_wallet_data(self) -> Dict[str, Any]:
        """Get the loaded wallet data."""
        if self._wallet_data is None:
            raise ValueError("Wallet data not loaded")
        return self._wallet_data
    
    def get_sell_strategy(self) -> SellStrategy:
        """Get the loaded sell strategy."""
        if self._sell_strategy is None:
            raise ValueError("Sell strategy not loaded")
        return self._sell_strategy
    
    def validate_configuration(self) -> bool:
        """
        Validate the loaded configuration.
        Returns True if configuration is valid, False otherwise.
        """
        try:
            if self._settings is None or self._wallet_data is None or self._sell_strategy is None:
                logger.error("Configuration not fully loaded")
                return False
                
            # Validate SOL balance for trading
            if self._settings.trading.max_buy_amount_sol <= 0:
                logger.error("Max buy amount must be greater than 0")
                return False
                
            # Validate RPC endpoints
            if not self._settings.solana.rpc_endpoints:
                logger.error("No Solana RPC endpoints configured")
                return False
                
            # Validate wallet data structure
            if "private_key" not in self._wallet_data and "keypair" not in self._wallet_data:
                logger.error("Wallet data missing private key or keypair")
                return False
                
            logger.info("Configuration validated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation error: {e}")
            return False


# Global config manager instance
config_manager = ConfigManager()
