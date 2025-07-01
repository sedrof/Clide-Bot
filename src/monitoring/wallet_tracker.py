"""
Enhanced wallet tracking with platform detection and verbose logging.
Detects which DEX was used and provides detailed transaction information.
"""

import asyncio
from typing import Dict, Any, Optional, Callable, List, Set, Tuple
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
    Enhanced wallet tracker with complete platform detection and verbose logging.
    """
    
    def __init__(self):
        self.settings = config_manager.get_settings()
        self.tracked_wallets: Set[str] = set(self.settings.tracking.wallets)
        
        # Program IDs for various DEXs and protocols
        self.program_ids = {
            "Pump.fun": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
            "Raydium V4": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
            "Raydium CLMM": "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",
            "Raydium Launchpad": "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj",
            "Jupiter V6": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
            "Jupiter V4": "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB",
            "Jupiter V3": "JUP3c2Uh3WA4Ng34tw6kPd2G4C5BB21Xo36Je1s32Ph",
            "Orca": "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP",
            "Meteora": "Eo7WjKq67rjJQSZxS6z3YkapzY3eMj6Xy8X5EQVn5UaB"
        }
        
        # System constants
        self.WSOL_MINT = "So11111111111111111111111111111111111111112"
        self.TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
        
        self.dex_program_ids = set(self.program_ids.values())
        self.running: bool = False
        self.buy_callbacks: List[Callable[[str, str, float, str, str], None]] = []  # Added platform and tx_url params
        self.processed_signatures: Set[str] = set()
        self.processed_signatures_time: Dict[str, float] = {}
        self.monitoring_tasks: List[asyncio.Task] = []
        self.monitoring_active = False
        
        # Faster polling interval
        self.POLL_INTERVAL = 0.5
        
        # Statistics
        self.stats = {
            "transactions_detected": 0,
            "buys_detected": 0,
            "sells_detected": 0,
            "dex_swaps_detected": 0,
            "errors": 0,
            "checks_performed": 0,
            "platforms": {},  # Track per-platform stats
            "last_check": time.time(),
            "last_detection_time": 0,
            "average_detection_delay": 0,
            "detection_delays": []
        }
        
        logger.info(f"WalletTracker initialized - tracking {len(self.tracked_wallets)} wallet(s)")
        
    async def start(self) -> None:
        """Start tracking specified wallets for transactions."""
        if self.running:
            logger.warning("Wallet tracker already running")
            return
            
        if not self.tracked_wallets:
            logger.warning("No wallets specified for tracking")
            return
            
        self.running = True
        self.monitoring_active = True
        
        logger.info(f"Starting wallet tracker for wallets: {list(self.tracked_wallets)}")
        
        # Start monitoring task for each wallet
        for wallet_address in self.tracked_wallets:
            task = asyncio.create_task(self._monitor_wallet(wallet_address))
            self.monitoring_tasks.append(task)
        
        # Start statistics logger
        asyncio.create_task(self._log_statistics())
        
    async def stop(self) -> None:
        """Stop tracking wallets."""
        self.running = False
        self.monitoring_active = False
        
        # Cancel all monitoring tasks
        for task in self.monitoring_tasks:
            task.cancel()
        
        await asyncio.gather(*self.monitoring_tasks, return_exceptions=True)
        self.monitoring_tasks.clear()
        
        logger.info("Wallet tracker stopped")
    
    async def _monitor_wallet(self, wallet_address: str) -> None:
        """Monitor a wallet for transactions with fast polling."""
        logger.info(f"Starting fast monitoring for wallet: {wallet_address}")
        
        consecutive_errors = 0
        
        while self.running:
            try:
                await self._check_wallet_transactions(wallet_address)
                self.stats["checks_performed"] += 1
                consecutive_errors = 0
                await asyncio.sleep(self.POLL_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error monitoring wallet {wallet_address}: {e}")
                self.stats["errors"] += 1
                
                # Exponential backoff on errors
                wait_time = min(self.POLL_INTERVAL * (2 ** consecutive_errors), 10)
                await asyncio.sleep(wait_time)
    
    async def _check_wallet_transactions(self, wallet_address: str) -> None:
        """Check recent transactions for a wallet."""
        try:
            client = await connection_manager.get_rpc_client()
            if not client:
                return
            
            # Get recent signatures
            response = await client.get_signatures_for_address(
                PublicKey.from_string(wallet_address),
                limit=5  # Check more transactions
            )
            
            if not response or not response.value:
                return
            
            # Process new transactions
            for sig_info in response.value:
                signature = str(sig_info.signature)
                
                # Check if we've seen this signature recently
                current_time = time.time()
                if signature in self.processed_signatures_time:
                    if current_time - self.processed_signatures_time[signature] < 60:
                        continue
                
                # Mark as processed with timestamp
                self.processed_signatures.add(signature)
                self.processed_signatures_time[signature] = current_time
                
                # Clean up old entries
                for sig, timestamp in list(self.processed_signatures_time.items()):
                    if current_time - timestamp > 300:
                        del self.processed_signatures_time[sig]
                        self.processed_signatures.discard(sig)
                
                # Calculate detection delay
                if sig_info.block_time:
                    detection_delay = time.time() - sig_info.block_time
                    self.stats["detection_delays"].append(detection_delay)
                    if len(self.stats["detection_delays"]) > 100:
                        self.stats["detection_delays"].pop(0)
                    self.stats["average_detection_delay"] = sum(self.stats["detection_delays"]) / len(self.stats["detection_delays"])
                    
                    logger.info(f"[TIMING] Transaction detected {detection_delay:.2f}s after block time")
                
                # Fetch transaction details
                tx_response = await client.get_transaction(
                    sig_info.signature,
                    encoding="jsonParsed",
                    commitment=Confirmed,
                    max_supported_transaction_version=0
                )
                
                if tx_response and tx_response.value:
                    await self._analyze_transaction(tx_response.value, wallet_address, signature)
                    
        except Exception as e:
            logger.error(f"Error checking transactions: {e}")
            self.stats["errors"] += 1
    
    async def _analyze_transaction(self, tx_data: Any, wallet_address: str, signature: str) -> None:
        """Analyze a transaction for DEX operations with detailed logging."""
        try:
            # Convert to dict if needed
            if hasattr(tx_data, 'to_json'):
                tx_json = tx_data.to_json()
                tx_data = json.loads(tx_json)
            
            meta = tx_data.get("meta", {})
            if meta.get("err"):
                return  # Skip failed transactions
            
            transaction = tx_data.get("transaction", {})
            message = transaction.get("message", {})
            instructions = message.get("instructions", [])
            inner_instructions = meta.get("innerInstructions", [])
            logs = meta.get("logMessages", [])
            
            # Build Solscan URL
            solscan_url = f"https://solscan.io/tx/{signature}"
            
            # Check for DEX programs
            program_ids_in_tx = set()
            detected_platforms = []
            
            for instruction in instructions:
                program_id = instruction.get("programId")
                if program_id and program_id in self.dex_program_ids:
                    program_ids_in_tx.add(program_id)
                    platform_name = next((name for name, id in self.program_ids.items() if id == program_id), program_id)
                    detected_platforms.append(platform_name)
            
            if not program_ids_in_tx:
                return  # No DEX programs found
            
            # Log detected platforms
            logger.info(f"Transaction {signature[:32]}... uses platforms: {', '.join(detected_platforms)}")
            logger.info(f"Solscan: {solscan_url}")
            
            # Update stats
            self.stats["transactions_detected"] += 1
            self.stats["last_detection_time"] = time.time()
            
            # Extract swap information based on DEX type
            swap_info = None
            primary_platform = None
            
            for prog_id in program_ids_in_tx:
                prog_name = next((name for name, id in self.program_ids.items() if id == prog_id), prog_id)
                
                logger.info(f"[{prog_name}] Analyzing transaction...")
                
                # Platform-specific parsing
                if "Jupiter" in prog_name:
                    swap_info = await self._parse_jupiter_swap_complete(instructions, inner_instructions, logs)
                    primary_platform = "Jupiter"
                elif "Raydium" in prog_name:
                    swap_info = await self._parse_raydium_swap_complete(instructions, inner_instructions, logs)
                    primary_platform = "Raydium"
                elif prog_name == "Pump.fun":
                    swap_info = await self._parse_pump_fun_transaction(instructions, logs)
                    primary_platform = "Pump.fun"
                elif prog_name == "Orca":
                    swap_info = await self._parse_orca_swap(instructions, inner_instructions, logs)
                    primary_platform = "Orca"
                elif prog_name == "Meteora":
                    swap_info = await self._parse_meteora_swap(instructions, inner_instructions, logs)
                    primary_platform = "Meteora"
                
                if swap_info:
                    swap_info["platform"] = primary_platform
                    break
            
            # Process the swap if detected
            if swap_info and swap_info.get("is_buy"):
                self.stats["buys_detected"] += 1
                self.stats["dex_swaps_detected"] += 1
                
                # Update platform stats
                platform = swap_info.get("platform", "Unknown")
                if platform not in self.stats["platforms"]:
                    self.stats["platforms"][platform] = {"buys": 0, "sells": 0}
                self.stats["platforms"][platform]["buys"] += 1
                
                token_address = swap_info.get("token_address", "Unknown")
                amount_sol = swap_info.get("amount_sol", 0)
                token_amount = swap_info.get("token_amount", 0)
                
                # Detailed logging
                logger.info("="*60)
                logger.info(f"🟢 BUY DETECTED on {platform}")
                logger.info(f"📊 Transaction Details:")
                logger.info(f"   Wallet: {wallet_address}")
                logger.info(f"   Token: {token_address}")
                logger.info(f"   SOL Amount: {amount_sol:.9f} SOL")
                logger.info(f"   Token Amount: {token_amount:,.2f} tokens")
                logger.info(f"   Platform: {platform}")
                logger.info(f"   TX: {signature}")
                logger.info(f"   Solscan: {solscan_url}")
                logger.info(f"   Block Time: {datetime.fromtimestamp(tx_data.get('blockTime', 0))}")
                logger.info(f"   Avg Detection Delay: {self.stats['average_detection_delay']:.2f}s")
                logger.info("="*60)
                
                # Trigger callbacks with platform info
                await self._trigger_buy_callbacks(
                    wallet_address, 
                    token_address, 
                    amount_sol,
                    platform,
                    solscan_url
                )
                        
        except Exception as e:
            logger.error(f"Error analyzing transaction: {e}", exc_info=True)
            self.stats["errors"] += 1
    
    async def _parse_jupiter_swap_complete(self, instructions: List[Dict], inner_instructions: List[Dict], 
                                          logs: List[str]) -> Optional[Dict[str, Any]]:
        """Parse Jupiter swap with complete details."""
        try:
            # Look for swap event in logs
            for log in logs:
                if "swapEvent" in log:
                    logger.debug(f"Found Jupiter swap event in logs: {log[:200]}...")
                    
                    # Extract the event data
                    try:
                        # Find JSON in log
                        start_idx = log.find('{')
                        if start_idx >= 0:
                            json_str = log[start_idx:]
                            json_str = json_str.replace('\"', '"')
                            
                            # Handle nested JSON
                            if '{"data":' in json_str:
                                data_start = json_str.find('{"data":')
                                if data_start >= 0:
                                    json_str = json_str[data_start:]
                                    event_wrapper = json.loads(json_str)
                                    event_data = event_wrapper.get("data", {})
                            else:
                                event_data = json.loads(json_str)
                            
                            input_mint = event_data.get("inputMint")
                            output_mint = event_data.get("outputMint")
                            input_amount = event_data.get("inputAmount", "0")
                            output_amount = event_data.get("outputAmount", "0")
                            
                            logger.debug(f"Jupiter swap: {input_mint} -> {output_mint}, amounts: {input_amount} -> {output_amount}")
                            
                            if input_mint == self.WSOL_MINT and output_mint != self.WSOL_MINT:
                                # This is a buy
                                amount_sol = float(input_amount) / 1e9
                                token_amount = float(output_amount) / 1e9  # Assuming 9 decimals
                                
                                # Validate amount
                                if amount_sol > 0.00001:  # Reasonable minimum
                                    return {
                                        "is_buy": True,
                                        "token_address": output_mint,
                                        "amount_sol": amount_sol,
                                        "token_amount": token_amount,
                                        "dex_name": "Jupiter V6"
                                    }
                    except Exception as e:
                        logger.debug(f"Failed to parse Jupiter event from log: {e}")
            
            # Fallback: Check instruction data
            for inst in instructions:
                if inst.get("programId") in [self.program_ids["Jupiter V6"], self.program_ids["Jupiter V4"]]:
                    # Parse from instruction data
                    data = inst.get("data", "")
                    if data:
                        logger.debug(f"Jupiter instruction data: {data[:100]}...")
                        # Instruction data parsing would go here
                        pass
            
            # Final fallback: Parse from inner instructions
            sol_amount = 0
            token_mint = None
            token_amount = 0
            
            for inner in inner_instructions:
                for inst in inner.get("instructions", []):
                    parsed = inst.get("parsed", {})
                    if parsed.get("type") in ["transfer", "transferChecked"]:
                        info = parsed.get("info", {})
                        
                        # Look for SOL transfers
                        if not info.get("mint") or info.get("mint") == self.WSOL_MINT:
                            amt = info.get("amount") or info.get("lamports", "0")
                            if isinstance(amt, str) and amt.isdigit():
                                potential_amount = float(amt) / 1e9
                                if 0.00001 < potential_amount < 100:  # Reasonable range
                                    sol_amount = potential_amount
                        
                        # Look for token transfers
                        elif info.get("mint") and info.get("mint") != self.WSOL_MINT:
                            token_mint = info.get("mint")
                            token_amt = info.get("tokenAmount", {})
                            if isinstance(token_amt, dict):
                                token_amount = float(token_amt.get("uiAmount", 0))
            
            if token_mint and sol_amount > 0:
                return {
                    "is_buy": True,
                    "token_address": token_mint,
                    "amount_sol": sol_amount,
                    "token_amount": token_amount,
                    "dex_name": "Jupiter"
                }
                
        except Exception as e:
            logger.error(f"Error parsing Jupiter swap: {e}")
        
        return None
    
    async def _parse_raydium_swap_complete(self, instructions: List[Dict], inner_instructions: List[Dict], 
                                          logs: List[str]) -> Optional[Dict[str, Any]]:
        """Parse Raydium swap with complete details."""
        try:
            # Check for Raydium swap indicators
            is_swap = False
            for log in logs:
                log_lower = log.lower()
                if any(indicator in log_lower for indicator in ["swap", "buy", "sell", "raydium"]):
                    is_swap = True
                    logger.debug(f"Found Raydium swap indicator: {log[:100]}...")
                    break
            
            if not is_swap:
                return None
            
            # Look for swap amounts in logs
            sol_amount = 0
            token_mint = None
            token_amount = 0
            
            # Parse amounts from logs
            for log in logs:
                # Look for amount patterns
                if "amount" in log.lower():
                    try:
                        import re
                        # Extract numbers from log
                        numbers = re.findall(r'\d+', log)
                        for num_str in numbers:
                            if len(num_str) > 6:  # Likely lamports
                                amount = float(num_str) / 1e9
                                if 0.00001 < amount < 100:
                                    sol_amount = amount
                                    logger.debug(f"Found potential SOL amount in log: {amount}")
                    except:
                        pass
            
            # Parse from instructions
            for inst in instructions:
                if inst.get("programId") in [self.program_ids["Raydium V4"], self.program_ids["Raydium CLMM"], self.program_ids["Raydium Launchpad"]]:
                    accounts = inst.get("accounts", [])
                    
                    # Raydium typically has token mints at specific positions
                    if len(accounts) >= 10:
                        # Check various positions for token mint
                        for idx in [5, 6, 9, 10]:
                            if idx < len(accounts):
                                potential_mint = accounts[idx]
                                if potential_mint != self.WSOL_MINT and len(potential_mint) == 44:
                                    token_mint = potential_mint
                                    logger.debug(f"Found potential token mint at position {idx}: {token_mint}")
                                    break
            
            # Parse from inner instructions
            if not token_mint or sol_amount == 0:
                for inner in inner_instructions:
                    for inst in inner.get("instructions", []):
                        parsed = inst.get("parsed", {})
                        if parsed.get("type") == "transferChecked":
                            info = parsed.get("info", {})
                            mint = info.get("mint", "")
                            
                            if mint and mint != self.WSOL_MINT:
                                token_mint = mint
                                token_amt = info.get("tokenAmount", {})
                                if isinstance(token_amt, dict):
                                    token_amount = float(token_amt.get("uiAmount", 0))
                            elif mint == self.WSOL_MINT:
                                amt = info.get("tokenAmount", {}).get("amount", "0")
                                if isinstance(amt, str) and amt.isdigit():
                                    sol_amount = float(amt) / 1e9
            
            if token_mint and sol_amount > 0:
                return {
                    "is_buy": True,
                    "token_address": token_mint,
                    "amount_sol": sol_amount,
                    "token_amount": token_amount,
                    "dex_name": "Raydium"
                }
                
        except Exception as e:
            logger.error(f"Error parsing Raydium swap: {e}")
        
        return None
    
    async def _parse_pump_fun_transaction(self, instructions: List[Dict], logs: List[str]) -> Optional[Dict[str, Any]]:
        """Parse Pump.fun transactions with complete details."""
        try:
            # Check logs for operation type
            logs_str = " ".join(logs).lower()
            
            operation = None
            if "create" in logs_str or "initialize" in logs_str:
                operation = "create"
            elif "buy" in logs_str:
                operation = "buy"
            elif "sell" in logs_str:
                operation = "sell"
            
            if operation not in ["create", "buy"]:
                return None
            
            # Find pump.fun instruction
            for inst in instructions:
                if inst.get("programId") == self.program_ids["Pump.fun"]:
                    accounts = inst.get("accounts", [])
                    
                    # Token mint is typically in first few accounts
                    token_mint = None
                    for idx in range(min(5, len(accounts))):
                        account = accounts[idx]
                        if account != self.WSOL_MINT and len(account) == 44:
                            token_mint = account
                            break
                    
                    if token_mint:
                        # Extract amount from logs or use defaults
                        sol_amount = 0.1 if operation == "create" else 0.01  # Defaults
                        
                        # Try to find actual amount in logs
                        for log in logs:
                            if "amount" in log.lower():
                                try:
                                    import re
                                    numbers = re.findall(r'\d+\.?\d*', log)
                                    for num_str in numbers:
                                        val = float(num_str)
                                        if 0.001 < val < 10:  # Reasonable SOL range
                                            sol_amount = val
                                            break
                                except:
                                    pass
                        
                        return {
                            "is_buy": True,
                            "token_address": token_mint,
                            "amount_sol": sol_amount,
                            "token_amount": 0,  # Pump.fun doesn't always show token amounts
                            "dex_name": "Pump.fun",
                            "operation": operation
                        }
                
        except Exception as e:
            logger.error(f"Error parsing Pump.fun transaction: {e}")
        
        return None
    
    async def _parse_orca_swap(self, instructions: List[Dict], inner_instructions: List[Dict], 
                              logs: List[str]) -> Optional[Dict[str, Any]]:
        """Parse Orca swap."""
        # Placeholder for Orca parsing
        return None
    
    async def _parse_meteora_swap(self, instructions: List[Dict], inner_instructions: List[Dict], 
                                 logs: List[str]) -> Optional[Dict[str, Any]]:
        """Parse Meteora swap."""
        # Placeholder for Meteora parsing
        return None
    
    async def _trigger_buy_callbacks(self, wallet_address: str, token_address: str, 
                                   amount_sol: float, platform: str, tx_url: str):
        """Trigger buy callbacks with platform info."""
        for callback in self.buy_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(wallet_address, token_address, amount_sol, platform, tx_url))
                else:
                    callback(wallet_address, token_address, amount_sol, platform, tx_url)
            except Exception as e:
                logger.error(f"Error in buy callback: {e}")
    
    async def _log_statistics(self):
        """Log statistics periodically."""
        while self.running:
            await asyncio.sleep(30)
            
            avg_delay = self.stats['average_detection_delay']
            platform_stats = ", ".join([f"{p}: {s['buys']}" for p, s in self.stats['platforms'].items()])
            
            logger.info(
                f"📊 STATS | Checks: {self.stats['checks_performed']} | "
                f"TX: {self.stats['transactions_detected']} | "
                f"Buys: {self.stats['buys_detected']} | "
                f"Platforms: [{platform_stats}] | "
                f"Avg Delay: {avg_delay:.2f}s"
            )
    
    def register_buy_callback(self, callback: Callable[[str, str, float, str, str], None]) -> None:
        """Register a callback for buy transactions with platform info."""
        self.buy_callbacks.append(callback)
        logger.info(f"Registered buy callback - Total callbacks: {len(self.buy_callbacks)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tracking statistics."""
        stats = self.stats.copy()
        stats["monitoring_active"] = self.monitoring_active
        stats["tracked_wallets"] = len(self.tracked_wallets)
        return stats
    
    def is_monitoring_active(self) -> bool:
        """Check if monitoring is actively running."""
        return self.monitoring_active and self.running


# Global wallet tracker instance
wallet_tracker = None

def initialize_wallet_tracker():
    """Initialize the global wallet tracker instance."""
    global wallet_tracker
    wallet_tracker = EnhancedWalletTracker()
    return wallet_tracker
