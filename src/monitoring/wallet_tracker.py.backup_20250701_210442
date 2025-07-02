"""
Enhanced wallet tracking with improved timing and detection speed.
"""
# File Location: src/monitoring/wallet_tracker.py

import asyncio
from typing import Dict, Any, Optional, Callable, List, Set
import json
from datetime import datetime
from solders.pubkey import Pubkey as PublicKey
from solana.rpc.commitment import Confirmed
import base58
import time
from solders.signature import Signature

from src.utils.config import config_manager
from src.utils.logger import get_logger
from src.core.connection_manager import connection_manager

logger = get_logger("wallet_tracker")


class EnhancedWalletTracker:
    """
    Enhanced wallet tracker with faster polling for pump.fun and DEX transactions.
    """
    
    def __init__(self):
        self.settings = config_manager.get_settings()
        self.tracked_wallets: Set[str] = set(self.settings.tracking.wallets)
        self.pump_program_id = PublicKey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
        self.processed_signatures: Set[str] = set()
        self.running: bool = False
        self.buy_callbacks: List[Callable] = []
        
        # DEX Program IDs
        self.RAYDIUM_V4 = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
        self.JUPITER_V6 = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
        self.ORCA_WHIRLPOOL = "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"
        self.METEORA = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
        self.PHOENIX = "PhoeNiXZ8ByJGLkxNfZRnkUfjvmuYqLR89jjFHGqdXY"
        self.OKX_DEX = "9tKE7Mbmj4mxDjWatikzGMszEyKWiuNksioVe4dFAFxF"
        
        # Transaction polling settings - FASTER for better detection
        self.polling_interval = 0.5  # Check every 500ms for faster detection
        self.max_signatures_per_poll = 20  # Check more recent transactions
        
        logger.info(f"WalletTracker initialized - tracking {len(self.tracked_wallets)} wallet(s)")
        logger.info(f"Polling interval: {self.polling_interval}s for faster detection")
    
    async def start(self) -> None:
        """Start tracking specified wallets for transactions."""
        if self.running:
            logger.warning("Wallet tracker already running")
            return
            
        if not self.tracked_wallets:
            logger.info("No wallets specified for tracking")
            return
            
        self.running = True
        logger.info(f"Starting wallet tracker for wallets: {list(self.tracked_wallets)}")
        
        # Start monitoring tasks for each wallet
        tasks = []
        for wallet_address in self.tracked_wallets:
            task = asyncio.create_task(self._monitor_wallet_fast(wallet_address))
            tasks.append(task)
        
        # Keep tasks reference
        self._monitor_tasks = tasks
    
    async def stop(self) -> None:
        """Stop tracking wallets."""
        self.running = False
        logger.info("Stopping wallet tracker")
        
        # Cancel all monitoring tasks
        if hasattr(self, '_monitor_tasks'):
            for task in self._monitor_tasks:
                task.cancel()
    
    async def _monitor_wallet_fast(self, wallet_address: str) -> None:
        """Monitor a wallet with fast polling for transactions."""
        logger.info(f"Starting to monitor wallet: {wallet_address}")
        
        while self.running:
            try:
                # Get RPC client
                rpc_client = await connection_manager.get_rpc_client()
                if not rpc_client:
                    await asyncio.sleep(5)
                    continue
                
                # Get recent transactions
                try:
                    pubkey = PublicKey.from_string(wallet_address)
                    signatures_response = await rpc_client.get_signatures_for_address(
                        pubkey,
                        limit=self.max_signatures_per_poll,
                        commitment=Confirmed
                    )
                    
                    if signatures_response and hasattr(signatures_response, 'value'):
                        signatures = signatures_response.value
                        
                        # Process each signature
                        for sig_info in signatures:
                            if hasattr(sig_info, 'signature'):
                                signature_str = str(sig_info.signature)
                                
                                # Skip if already processed
                                if signature_str in self.processed_signatures:
                                    continue
                                
                                # Mark as processed immediately
                                self.processed_signatures.add(signature_str)
                                
                                # Keep cache size reasonable
                                if len(self.processed_signatures) > 1000:
                                    self.processed_signatures = set(list(self.processed_signatures)[-500:])
                                
                                # Process the transaction
                                await self._process_transaction_fast(
                                    wallet_address,
                                    signature_str,
                                    rpc_client
                                )
                
                except Exception as e:
                    logger.error(f"Error getting signatures for {wallet_address}: {e}")
                
                # Fast polling interval
                await asyncio.sleep(self.polling_interval)
                
            except Exception as e:
                logger.error(f"Error monitoring wallet {wallet_address}: {e}")
                await asyncio.sleep(5)
    
    async def _process_transaction_fast(
        self,
        wallet_address: str,
        signature: str,
        rpc_client: Any
    ) -> None:
        """Process a transaction quickly to detect buys."""
        try:
            # Get transaction details
            tx_response = await rpc_client.get_transaction(
                Signature.from_string(signature),
                encoding="jsonParsed",
                commitment=Confirmed,
                max_supported_transaction_version=0
            )
            
            if not tx_response or not hasattr(tx_response, 'value'):
                return
            
            tx_data = tx_response.value
            if not tx_data:
                return
            
            # Parse transaction
            result = await self._parse_transaction_for_buy(tx_data, wallet_address, signature)
            
            if result:
                # Detected a buy!
                platform = result.get("platform", "Unknown")
                token_address = result.get("token_address", "")
                amount_sol = result.get("amount_sol", 0)
                
                logger.info(f"[{platform}] Transaction detected: {signature[:32]}...")
                logger.info(f"🟢 BUY DETECTED on {platform} | Wallet: {wallet_address[:8]}... | Token: {token_address[:8]}... | Amount: {amount_sol:.6f} SOL | TX: {signature[:32]}...")
                
                # Notify callbacks with platform info
                tx_url = f"https://solscan.io/tx/{signature}"
                await self._notify_buy_callbacks(
                    wallet_address,
                    token_address,
                    amount_sol,
                    platform,
                    tx_url
                )
                
        except Exception as e:
            logger.error(f"Error processing transaction {signature}: {e}")
    
    async def _parse_transaction_for_buy(
        self,
        tx_data: Any,
        wallet_address: str,
        signature: str
    ) -> Optional[Dict[str, Any]]:
        """Parse transaction to detect buys on any platform."""
        try:
            # Convert to dict if needed
            if hasattr(tx_data, 'to_json'):
                tx_json = tx_data.to_json()
                tx_data = json.loads(tx_json)
            
            meta = tx_data.get("meta", {})
            if meta.get("err"):
                return None  # Skip failed transactions
            
            transaction = tx_data.get("transaction", {})
            message = transaction.get("message", {})
            instructions = message.get("instructions", [])
            
            # Check each instruction
            for instruction in instructions:
                program_id = instruction.get("programId", "")
                
                # Check Pump.fun
                if program_id == str(self.pump_program_id):
                    parsed = await self._parse_pump_instruction(instruction)
                    if parsed and parsed.get("is_buy"):
                        parsed["platform"] = "Pump.fun"
                        return parsed
                
                # Check Raydium
                elif program_id == self.RAYDIUM_V4:
                    parsed = await self._parse_raydium_swap(instruction, meta)
                    if parsed and parsed.get("is_buy"):
                        parsed["platform"] = "Raydium"
                        return parsed
                
                # Check Jupiter
                elif program_id == self.JUPITER_V6:
                    parsed = await self._parse_jupiter_swap(instruction, meta)
                    if parsed and parsed.get("is_buy"):
                        parsed["platform"] = "Jupiter"
                        return parsed
                
                # Check Orca
                elif program_id == self.ORCA_WHIRLPOOL:
                    parsed = await self._parse_orca_swap(instruction, meta)
                    if parsed and parsed.get("is_buy"):
                        parsed["platform"] = "Orca"
                        return parsed
                
                # Check OKX DEX
                elif program_id == self.OKX_DEX or "okx" in program_id.lower():
                    parsed = await self._parse_okx_swap(instruction, meta)
                    if parsed and parsed.get("is_buy"):
                        parsed["platform"] = "OKX DEX Router"
                        return parsed
                
                # Generic DEX detection by instruction type
                elif instruction.get("parsed", {}).get("type") == "swap":
                    parsed = await self._parse_generic_swap(instruction, meta)
                    if parsed and parsed.get("is_buy"):
                        parsed["platform"] = "Unknown DEX"
                        return parsed
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing transaction for buy: {e}")
            return None
    
    async def _parse_pump_instruction(self, instruction: Dict) -> Optional[Dict[str, Any]]:
        """Parse Pump.fun instruction."""
        try:
            data = instruction.get("data", "")
            if isinstance(data, str) and len(data) >= 16:
                # Check if it's a buy instruction
                if data.startswith("66063d1201daebea"):  # Buy discriminator
                    return {
                        "is_buy": True,
                        "token_address": "Unknown",  # Would need to parse accounts
                        "amount_sol": 0.01  # Default, would need to parse
                    }
            return None
        except Exception:
            return None
    
    async def _parse_raydium_swap(self, instruction: Dict, meta: Dict) -> Optional[Dict[str, Any]]:
        """Parse Raydium swap."""
        # Simplified - detect SOL -> Token swaps
        return self._parse_generic_dex_swap(instruction, meta)
    
    async def _parse_jupiter_swap(self, instruction: Dict, meta: Dict) -> Optional[Dict[str, Any]]:
        """Parse Jupiter swap."""
        return self._parse_generic_dex_swap(instruction, meta)
    
    async def _parse_orca_swap(self, instruction: Dict, meta: Dict) -> Optional[Dict[str, Any]]:
        """Parse Orca swap."""
        return self._parse_generic_dex_swap(instruction, meta)
    
    async def _parse_okx_swap(self, instruction: Dict, meta: Dict) -> Optional[Dict[str, Any]]:
        """Parse OKX DEX swap."""
        return self._parse_generic_dex_swap(instruction, meta)
    
    async def _parse_generic_swap(self, instruction: Dict, meta: Dict) -> Optional[Dict[str, Any]]:
        """Parse generic swap instruction."""
        return self._parse_generic_dex_swap(instruction, meta)
    
    def _parse_generic_dex_swap(self, instruction: Dict, meta: Dict) -> Optional[Dict[str, Any]]:
        """Generic DEX swap parser - detects SOL -> Token swaps."""
        try:
            # Look for SOL balance changes in meta
            pre_balances = meta.get("preBalances", [])
            post_balances = meta.get("postBalances", [])
            
            if pre_balances and post_balances and len(pre_balances) == len(post_balances):
                # Check if SOL decreased (indicating a buy)
                for i in range(len(pre_balances)):
                    sol_change = (post_balances[i] - pre_balances[i]) / 1e9
                    if sol_change < -0.0001:  # SOL decreased by at least 0.0001
                        return {
                            "is_buy": True,
                            "token_address": "Unknown",  # Would need more parsing
                            "amount_sol": abs(sol_change)
                        }
            
            # Alternative: Check parsed info
            parsed = instruction.get("parsed", {})
            if parsed.get("type") in ["swap", "swapBaseIn", "buy"]:
                info = parsed.get("info", {})
                # Try to extract amount
                amount = info.get("amountIn", info.get("amount", 0))
                if isinstance(amount, (int, float)) and amount > 0:
                    return {
                        "is_buy": True,
                        "token_address": info.get("mint", "Unknown"),
                        "amount_sol": amount / 1e9 if amount > 1000 else amount
                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"Error parsing generic DEX swap: {e}")
            return None
    
    async def _notify_buy_callbacks(
        self,
        wallet_address: str,
        token_address: str,
        amount_sol: float,
        platform: str,
        tx_url: str
    ) -> None:
        """Notify all registered callbacks about a buy."""
        for callback in self.buy_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(wallet_address, token_address, amount_sol, platform, tx_url)
                else:
                    callback(wallet_address, token_address, amount_sol, platform, tx_url)
            except Exception as e:
                logger.error(f"Error in buy callback: {e}")
    
    def register_buy_callback(self, callback: Callable) -> None:
        """Register a callback for buy events."""
        self.buy_callbacks.append(callback)
        logger.info(f"Registered buy callback - Total callbacks: {len(self.buy_callbacks)}")


# Global wallet tracker instance
wallet_tracker = None

def initialize_wallet_tracker():
    """Initialize the global wallet tracker instance."""
    global wallet_tracker
    wallet_tracker = EnhancedWalletTracker()
    return wallet_tracker
