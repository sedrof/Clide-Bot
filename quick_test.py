#!/usr/bin/env python3
"""Quick test to check RPC connection and wallet balance."""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from solana.rpc.async_api import AsyncClient
from src.utils.config import config_manager


async def test_rpc():
    """Test RPC connection."""
    try:
        # Load config
        config_manager.load_all()
        settings = config_manager.get_settings()
        
        print("Testing RPC connection...")
        print(f"Endpoint: {settings.solana.rpc_endpoints[0]}")
        
        client = AsyncClient(settings.solana.rpc_endpoints[0])
        
        # Test connection
        response = await client.get_version()
        print(f"✅ Connected! Solana version: {response.value}")
        
        # Get wallet balance
        from solders.pubkey import Pubkey
        wallet = config_manager.get_wallet()
        pubkey = Pubkey.from_string(wallet.public_key)
        balance_response = await client.get_balance(pubkey)
        
        balance_sol = balance_response.value / 1_000_000_000
        print(f"✅ Wallet balance: {balance_sol:.6f} SOL")
        
        if balance_sol < 0.005:
            print("⚠️  Warning: Balance is below minimum required (0.005 SOL)")
        
        await client.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_rpc())
    sys.exit(0 if success else 1)