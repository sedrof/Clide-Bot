#!/usr/bin/env python3
"""
Simple run script for the Solana Pump.fun Sniping Bot
"""

import subprocess
import sys
import os

if __name__ == "__main__":
    print("🚀 Starting Solana Pump.fun Sniping Bot...")
    print("="*60)
    
    # Run the bot
    try:
        subprocess.run([sys.executable, "src/main.py"], check=True)
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Bot exited with error code: {e.returncode}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
