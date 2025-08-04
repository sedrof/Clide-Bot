#!/usr/bin/env python3
"""Test multiple RPC endpoints to find a working one."""
import asyncio
from solana.rpc.async_api import AsyncClient
import time


async def test_rpc_endpoint(endpoint: str):
    """Test a single RPC endpoint."""
    try:
        start = time.time()
        client = AsyncClient(endpoint, timeout=10)
        
        # Try to get version
        response = await client.get_version()
        latency = (time.time() - start) * 1000
        
        await client.close()
        
        if response.value:
            return True, f"✅ Working ({latency:.0f}ms)"
        else:
            return False, "❌ No response"
            
    except Exception as e:
        return False, f"❌ Error: {str(e)[:50]}"


async def main():
    """Test multiple public RPC endpoints."""
    endpoints = [
        # Current endpoint
        "https://lb.drpc.org/ogrpc?network=solana&dkey=AnFgx_WRKUErtPzty2EXGn4b8SFRU-oR8JQVrqRhf0fE",
        
        # Public endpoints
        "https://api.mainnet-beta.solana.com",
        "https://solana-api.projectserum.com",
        "https://rpc.ankr.com/solana",
        "https://solana.public-rpc.com",
        "https://api.mainnet.solana.com",
        
        # Rate-limited but reliable
        "https://mainnet.helius-rpc.com/?api-key=PLACEHOLDER",
    ]
    
    print("Testing Solana RPC endpoints...\n")
    
    working_endpoints = []
    
    for endpoint in endpoints:
        print(f"Testing: {endpoint[:50]}...")
        success, message = await test_rpc_endpoint(endpoint)
        print(f"  {message}")
        
        if success:
            working_endpoints.append(endpoint)
    
    print(f"\n✅ Found {len(working_endpoints)} working endpoints")
    
    if working_endpoints:
        print("\nRecommended endpoints:")
        for ep in working_endpoints[:3]:
            print(f"  - {ep}")


if __name__ == "__main__":
    asyncio.run(main())