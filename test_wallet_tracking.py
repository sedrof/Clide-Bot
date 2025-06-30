#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify wallet tracking is working
Run after applying the patch to check if issues are resolved
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_wallet_tracking():
    print("Testing Wallet Tracking...")
    print("="*60)
    
    # Setup logging first
    from src.utils.logger import setup_logging
    
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    setup_logging(
        level="DEBUG",
        file_path="logs/test_wallet.log",
        console_output=True
    )
    
    # Load config
    from src.utils.config import config_manager
    config_manager.load_all()
    
    # Initialize connection manager
    from src.core.connection_manager import connection_manager
    await connection_manager.initialize()
    
    # Initialize wallet tracker
    from src.monitoring.wallet_tracker import initialize_wallet_tracker
    wallet_tracker = initialize_wallet_tracker()
    
    print("✓ Wallet tracker initialized")
    print(f"✓ Tracking wallets: {list(wallet_tracker.tracked_wallets)}")
    
    # Register a simple callback to see when buys are detected
    def on_buy_detected(wallet, token, amount):
        print(f"\n🎉 BUY DETECTED! Wallet {wallet[:8]}... bought {token[:16]}... for {amount:.6f} SOL\n")
    
    wallet_tracker.register_buy_callback(on_buy_detected)
    
    # Start tracking
    await wallet_tracker.start()
    print("✓ Wallet tracking started")
    
    # Run for 30 seconds
    print("")
    print("Running for 30 seconds to check for transactions...")
    print("Check logs/test_wallet.log for detailed output")
    print("")
    
    # Show periodic updates
    for i in range(6):  # 6 x 5 seconds = 30 seconds
        await asyncio.sleep(5)
        stats = wallet_tracker.get_stats()
        print(f"[{i*5+5}s] Checks: {stats['checks_performed']}, TX: {stats['transactions_detected']}, Buys: {stats['buys_detected']}")
    
    # Get final stats
    stats = wallet_tracker.get_stats()
    print("")
    print("Final Statistics:")
    print(f"  Checks performed: {stats['checks_performed']}")
    print(f"  Transactions detected: {stats['transactions_detected']}")
    print(f"  Buys detected: {stats['buys_detected']}")
    print(f"  DEX swaps detected: {stats.get('dex_swaps_detected', 0)}")
    print(f"  Errors: {stats['errors']}")
    
    # Stop
    await wallet_tracker.stop()
    await connection_manager.close()
    
    print("")
    print("✅ Test complete!")
    print(f"Check the log file at: {Path('logs/test_wallet.log').absolute()}")

if __name__ == "__main__":
    asyncio.run(test_wallet_tracking())
