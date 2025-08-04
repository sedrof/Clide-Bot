#!/usr/bin/env python3
"""
Secure configuration setup for RPC endpoints.
Moves API keys to environment variables.
"""
import os
import json
from typing import List


def get_rpc_endpoints() -> List[str]:
    """Get RPC endpoints with secure API key handling."""
    endpoints = []
    
    # Always include the public endpoint as fallback
    endpoints.append("https://api.mainnet-beta.solana.com")
    
    # Add private RPC if API key is provided
    private_rpc_key = os.getenv("DRPC_API_KEY")
    if private_rpc_key:
        endpoints.insert(0, f"https://lb.drpc.org/ogrpc?network=solana&dkey={private_rpc_key}")
    
    # Add other private endpoints
    helius_key = os.getenv("HELIUS_API_KEY")
    if helius_key:
        endpoints.insert(0, f"https://mainnet.helius-rpc.com/?api-key={helius_key}")
    
    quicknode_url = os.getenv("QUICKNODE_RPC_URL")
    if quicknode_url:
        endpoints.insert(0, quicknode_url)
    
    return endpoints


def get_websocket_endpoint() -> str:
    """Get WebSocket endpoint."""
    # Try private endpoints first
    helius_key = os.getenv("HELIUS_API_KEY")
    if helius_key:
        return f"wss://mainnet.helius-rpc.com/?api-key={helius_key}"
    
    # Fall back to public
    return "wss://api.mainnet-beta.solana.com"


def check_rpc_security():
    """Check for exposed API keys in config files."""
    issues = []
    
    # Check settings.json for exposed keys
    try:
        with open("config/settings.json", 'r') as f:
            config = json.load(f)
        
        for endpoint in config["solana"]["rpc_endpoints"]:
            if "dkey=" in endpoint or "api-key=" in endpoint:
                issues.append(f"⚠️  API key exposed in settings.json: {endpoint[:50]}...")
    except Exception as e:
        issues.append(f"❌ Could not read settings.json: {e}")
    
    return issues


def main():
    """Check current RPC security and provide recommendations."""
    print("🔍 Checking RPC Configuration Security...\n")
    
    # Check for security issues
    issues = check_rpc_security()
    
    if issues:
        print("❌ Security Issues Found:")
        for issue in issues:
            print(f"   {issue}")
        print()
    
    # Show current endpoints
    print("📡 Current RPC Endpoints:")
    endpoints = get_rpc_endpoints()
    for i, endpoint in enumerate(endpoints, 1):
        if "dkey=" in endpoint or "api-key=" in endpoint:
            print(f"   {i}. {endpoint[:30]}...*** (Private)")
        else:
            print(f"   {i}. {endpoint} (Public)")
    
    print(f"\n🔌 WebSocket: {get_websocket_endpoint()}")
    
    # Recommendations
    print("\n💡 Recommendations:")
    
    if not os.getenv("DRPC_API_KEY"):
        print("   • Set DRPC_API_KEY environment variable to secure your key")
        print("   • Remove API key from settings.json")
    
    print("   • Consider getting dedicated RPC from:")
    print("     - Helius: https://helius.dev (500K free requests/month)")
    print("     - QuickNode: https://quicknode.com (free tier available)")
    print("     - Alchemy: https://alchemy.com (free tier available)")
    print("     - DRPC: https://drpc.org (current provider)")
    
    print("\n🔧 To secure your setup:")
    print("   1. Create .env file with your API keys")
    print("   2. Update settings.json to use public endpoints only")
    print("   3. Use environment variables for private keys")


if __name__ == "__main__":
    main()