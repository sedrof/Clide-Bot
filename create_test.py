#!/usr/bin/env python3

import os
import shutil
import sys
from pathlib import Path

def backup_file(filepath):
    """Create a backup of the file before modifying."""
    backup_path = f"{filepath}.backup_{os.getpid()}"
    if os.path.exists(filepath):
        shutil.copy2(filepath, backup_path)
        print(f"✓ Backed up: {filepath}")
    return backup_path

def write_file(filepath, content):
    """Write content to file."""
    # Get directory path
    dir_path = os.path.dirname(filepath)
    
    # Only create directory if there is one (not current directory)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Updated: {filepath}")

def create_test_script():
    """Create the test script."""
    content = '''#!/usr/bin/env python3
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
        print(f"\\n🎉 BUY DETECTED! Wallet {wallet[:8]}... bought {token[:16]}... for {amount:.6f} SOL\\n")
    
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
'''
    
    write_file('test_wallet_tracking.py', content)
    print("✓ Created test_wallet_tracking.py")

def main():
    """Just create the test script."""
    print("="*60)
    print("🔧 Creating Test Script for Wallet Tracking")
    print("="*60)
    print()
    
    # Check we're in the right directory
    if not os.path.exists('src/main.py'):
        print("❌ ERROR: This script must be run from the project root directory")
        print("   Please cd to C:\\Users\\JJ\\Desktop\\Clide-Bot and run again")
        return 1
    
    try:
        # Create the test script
        create_test_script()
        
        print()
        print("✅ Test script created successfully!")
        print()
        print("🚀 To run the test:")
        print("   python test_wallet_tracking.py")
        print()
        print("📊 The test will:")
        print("   - Monitor the tracked wallet for 30 seconds")
        print("   - Show progress updates every 5 seconds")
        print("   - Display any detected buy transactions")
        print("   - Save detailed logs to logs/test_wallet.log")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
