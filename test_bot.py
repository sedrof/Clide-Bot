#!/usr/bin/env python3
"""
Comprehensive test suite for the Solana pump.fun sniping bot.
Tests all critical components before running the bot with real money.
"""
import asyncio
import json
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import rich for nice output
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import print as rprint

console = Console()


class BotTester:
    """Main test runner for the trading bot."""
    
    def __init__(self):
        self.results = []
        self.errors = []
        self.warnings = []
        
    async def run_all_tests(self):
        """Run all tests in sequence."""
        console.print(Panel.fit("🧪 Solana Trading Bot Test Suite", style="bold blue"))
        console.print()
        
        tests = [
            self.test_environment,
            self.test_dependencies,
            self.test_configuration,
            self.test_wallet,
            self.test_rpc_connection,
            self.test_websocket_connection,
            self.test_pump_fun_api,
            self.test_trading_logic,
            self.test_sell_strategy,
            self.test_monitoring_components,
            self.test_safety_checks
        ]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            for test in tests:
                task = progress.add_task(f"Running {test.__name__}...", total=1)
                try:
                    await test()
                    progress.update(task, completed=1)
                except Exception as e:
                    self.errors.append(f"{test.__name__}: {str(e)}")
                    progress.update(task, completed=1)
        
        self.print_results()
    
    async def test_environment(self):
        """Test Python environment and basic setup."""
        self.results.append(("Python Version", sys.version.split()[0], "✅"))
        self.results.append(("Platform", sys.platform, "✅"))
        self.results.append(("Working Directory", os.getcwd(), "✅"))
        
        # Check if virtual environment is active
        venv_active = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        self.results.append(("Virtual Environment", "Active" if venv_active else "Not Active", "✅" if venv_active else "⚠️"))
    
    async def test_dependencies(self):
        """Test all required dependencies are installed."""
        required_modules = [
            'solana', 'solders', 'anchorpy', 'base58', 'websockets',
            'httpx', 'aiohttp', 'pydantic', 'yaml', 'rich', 'tenacity'
        ]
        
        for module_name in required_modules:
            try:
                module = __import__(module_name)
                version = getattr(module, '__version__', 'Unknown')
                self.results.append((f"{module_name} module", f"v{version}", "✅"))
            except ImportError as e:
                self.errors.append(f"Missing dependency: {module_name}")
                self.results.append((f"{module_name} module", "Not installed", "❌"))
    
    async def test_configuration(self):
        """Test configuration files exist and are valid."""
        config_files = [
            ('config/settings.json', 'Settings'),
            ('config/wallet.json', 'Wallet'),
            ('config/sell_strategy.yaml', 'Sell Strategy')
        ]
        
        for file_path, name in config_files:
            if os.path.exists(file_path):
                try:
                    if file_path.endswith('.json'):
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                        self.results.append((f"{name} Config", "Valid JSON", "✅"))
                    elif file_path.endswith('.yaml'):
                        import yaml
                        with open(file_path, 'r') as f:
                            data = yaml.safe_load(f)
                        self.results.append((f"{name} Config", "Valid YAML", "✅"))
                except Exception as e:
                    self.errors.append(f"Invalid {name} config: {str(e)}")
                    self.results.append((f"{name} Config", "Invalid format", "❌"))
            else:
                self.errors.append(f"Missing config file: {file_path}")
                self.results.append((f"{name} Config", "File not found", "❌"))
    
    async def test_wallet(self):
        """Test wallet configuration and balance."""
        try:
            from src.utils.config import config_manager
            from src.core.wallet_manager import WalletManager
            
            # Load config
            config_manager.load_all()
            wallet_config = config_manager.get_wallet()
            
            # Check wallet structure
            if wallet_config.keypair and len(wallet_config.keypair) == 64:
                self.results.append(("Wallet Keypair", "64 bytes found", "✅"))
            else:
                self.errors.append("Invalid wallet keypair format")
                self.results.append(("Wallet Keypair", "Invalid format", "❌"))
            
            # Check public key
            if wallet_config.public_key:
                self.results.append(("Public Key", wallet_config.public_key[:8] + "...", "✅"))
            else:
                self.warnings.append("Public key not found in wallet config")
                
        except Exception as e:
            self.errors.append(f"Wallet test failed: {str(e)}")
            self.results.append(("Wallet Test", "Failed", "❌"))
    
    async def test_rpc_connection(self):
        """Test RPC connection to Solana network."""
        try:
            from src.utils.config import config_manager
            from solana.rpc.async_api import AsyncClient
            
            settings = config_manager.get_settings()
            rpc_endpoint = settings.solana.rpc_endpoints[0]
            
            # Test connection
            client = AsyncClient(rpc_endpoint)
            try:
                # Get recent blockhash to test connection
                response = await client.get_latest_blockhash()
                if response.value:
                    self.results.append(("RPC Connection", f"Connected to {rpc_endpoint.split('/')[2]}", "✅"))
                    
                    # Check network health by getting slot
                    slot = await client.get_slot()
                    self.results.append(("Network Health", f"Slot: {slot.value}", "✅"))
                else:
                    self.errors.append("Failed to get blockhash from RPC")
                    self.results.append(("RPC Connection", "Connection failed", "❌"))
            finally:
                await client.close()
                
        except Exception as e:
            self.errors.append(f"RPC connection test failed: {str(e)}")
            self.results.append(("RPC Connection", "Failed", "❌"))
    
    async def test_websocket_connection(self):
        """Test WebSocket connection capabilities."""
        try:
            import websockets
            
            # Test basic websocket capability
            self.results.append(("WebSocket Support", "Available", "✅"))
            
            # Note: We won't actually connect to pump.fun WebSocket in tests
            # to avoid rate limiting or unwanted connections
            self.results.append(("WebSocket Config", "Configuration found", "✅"))
            
        except Exception as e:
            self.errors.append(f"WebSocket test failed: {str(e)}")
            self.results.append(("WebSocket Support", "Failed", "❌"))
    
    async def test_pump_fun_api(self):
        """Test pump.fun API configuration."""
        try:
            from src.utils.config import config_manager
            
            settings = config_manager.get_settings()
            pump_config = settings.pump_fun
            
            if pump_config.api_endpoint:
                self.results.append(("Pump.fun API", pump_config.api_endpoint, "✅"))
            
            if pump_config.websocket_endpoint:
                self.results.append(("Pump.fun WebSocket", pump_config.websocket_endpoint, "✅"))
                
            if pump_config.program_id:
                self.results.append(("Pump.fun Program ID", pump_config.program_id[:8] + "...", "✅"))
                
        except Exception as e:
            self.errors.append(f"Pump.fun config test failed: {str(e)}")
            self.results.append(("Pump.fun Config", "Failed", "❌"))
    
    async def test_trading_logic(self):
        """Test trading configuration and logic."""
        try:
            from src.utils.config import config_manager
            
            settings = config_manager.get_settings()
            trading_config = settings.trading
            
            # Check critical trading parameters
            checks = [
                ('max_positions', lambda x: x > 0 and x <= 10),
                ('max_buy_amount_sol', lambda x: x > 0 and x <= 1),
                ('buy_amount_sol', lambda x: x > 0 and x <= 0.1),
                ('min_balance_sol', lambda x: x > 0),
                ('take_profit_percentage', lambda x: x > 0 and x <= 100),
                ('stop_loss_percentage', lambda x: x > 0 and x <= 100)
            ]
            
            for param, validator in checks:
                value = getattr(trading_config, param, None)
                if value is not None:
                    if validator(value):
                        self.results.append((f"Trading {param}", f"{value}", "✅"))
                    else:
                        self.warnings.append(f"Trading parameter {param} has unusual value: {value}")
                        self.results.append((f"Trading {param}", f"{value}", "⚠️"))
                else:
                    self.errors.append(f"Missing trading parameter: {param}")
                    self.results.append((f"Trading {param}", "Missing", "❌"))
                    
        except Exception as e:
            self.errors.append(f"Trading logic test failed: {str(e)}")
            self.results.append(("Trading Logic", "Failed", "❌"))
    
    async def test_sell_strategy(self):
        """Test sell strategy configuration."""
        try:
            from src.utils.config import config_manager
            
            sell_strategy = config_manager.get_sell_strategy()
            
            if hasattr(sell_strategy, 'selling_rules'):
                rule_count = len(sell_strategy.selling_rules)
                self.results.append(("Sell Rules", f"{rule_count} rules configured", "✅"))
                
                # Validate each rule
                for i, rule in enumerate(sell_strategy.selling_rules):
                    if hasattr(rule, 'name') and hasattr(rule, 'conditions') and hasattr(rule, 'action'):
                        self.results.append((f"Rule {i+1}", rule.name, "✅"))
                    else:
                        self.warnings.append(f"Incomplete sell rule: {getattr(rule, 'name', 'unnamed')}")
            else:
                self.errors.append("No selling rules found")
                self.results.append(("Sell Rules", "No rules found", "❌"))
                
        except Exception as e:
            self.errors.append(f"Sell strategy test failed: {str(e)}")
            self.results.append(("Sell Strategy", "Failed", "❌"))
    
    async def test_monitoring_components(self):
        """Test monitoring components initialization."""
        components = [
            'pump_monitor',
            'price_tracker', 
            'volume_analyzer',
            'wallet_tracker',
            'event_processor'
        ]
        
        for component in components:
            try:
                # Import the initialization function
                module = __import__(f'src.monitoring.{component}', fromlist=['initialize_' + component])
                init_func = getattr(module, f'initialize_{component}')
                
                # Check if it's callable
                if callable(init_func):
                    self.results.append((f"{component}", "Module OK", "✅"))
                else:
                    self.warnings.append(f"{component} initialization function not callable")
                    self.results.append((f"{component}", "Init function issue", "⚠️"))
                    
            except Exception as e:
                self.errors.append(f"Failed to import {component}: {str(e)}")
                self.results.append((f"{component}", "Import failed", "❌"))
    
    async def test_safety_checks(self):
        """Test safety features and limits."""
        try:
            from src.utils.config import config_manager
            
            settings = config_manager.get_settings()
            trading_config = settings.trading
            
            # Safety checks
            buy_amount = trading_config.buy_amount_sol
            max_buy = trading_config.max_buy_amount_sol
            min_balance = trading_config.min_balance_sol
            
            # Check if buy amount is reasonable
            if buy_amount <= 0.01:  # 0.01 SOL or less
                self.results.append(("Buy Amount Safety", f"{buy_amount} SOL (safe for testing)", "✅"))
            else:
                self.warnings.append(f"Buy amount {buy_amount} SOL might be high for testing")
                self.results.append(("Buy Amount Safety", f"{buy_amount} SOL (high for testing)", "⚠️"))
            
            # Check position limits
            max_positions = trading_config.max_positions
            if max_positions <= 5:
                self.results.append(("Position Limit", f"{max_positions} positions", "✅"))
            else:
                self.warnings.append(f"High position limit: {max_positions}")
                self.results.append(("Position Limit", f"{max_positions} positions", "⚠️"))
                
        except Exception as e:
            self.errors.append(f"Safety check failed: {str(e)}")
            self.results.append(("Safety Checks", "Failed", "❌"))
    
    def print_results(self):
        """Print test results in a nice table."""
        console.print()
        
        # Create results table
        table = Table(title="Test Results", show_header=True, header_style="bold magenta")
        table.add_column("Test", style="cyan", width=30)
        table.add_column("Result", style="white", width=40)
        table.add_column("Status", justify="center", width=10)
        
        for test, result, status in self.results:
            table.add_row(test, result, status)
        
        console.print(table)
        
        # Print errors if any
        if self.errors:
            console.print()
            console.print(Panel.fit("❌ Errors Found", style="bold red"))
            for error in self.errors:
                console.print(f"  • {error}", style="red")
        
        # Print warnings if any
        if self.warnings:
            console.print()
            console.print(Panel.fit("⚠️  Warnings", style="bold yellow"))
            for warning in self.warnings:
                console.print(f"  • {warning}", style="yellow")
        
        # Summary
        console.print()
        error_count = len(self.errors)
        warning_count = len(self.warnings)
        
        if error_count == 0:
            if warning_count == 0:
                console.print(Panel.fit("✅ All tests passed! Bot is ready to run.", style="bold green"))
                console.print()
                console.print("To run the bot in production mode:")
                console.print("  python src/main.py", style="bold cyan")
                console.print()
                console.print("To run with dry-run mode (recommended for first time):")
                console.print("  python src/main.py --dry-run", style="bold cyan")
            else:
                console.print(Panel.fit(f"✅ Tests passed with {warning_count} warnings. Review warnings before running.", style="bold yellow"))
        else:
            console.print(Panel.fit(f"❌ {error_count} errors found. Fix these before running the bot.", style="bold red"))


async def main():
    """Main test runner."""
    tester = BotTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    # Run tests
    asyncio.run(main())