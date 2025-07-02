#!/usr/bin/env python3

import os
import sys

def fix_connection_manager_directly():
    """Directly fix the get_health issue in connection_manager.py"""
    filepath = "src/core/connection_manager.py"
    
    try:
        # Read the file
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace get_health with get_recent_blockhash
        if "get_health" in content:
            content = content.replace(
                "result = await client.get_health()",
                "result = await client.get_recent_blockhash()"
            )
            content = content.replace(
                "if result:",
                "if result and result.value:"
            )
            print("✓ Fixed get_health() -> get_recent_blockhash()")
        else:
            print("⚠️  get_health not found, checking for other patterns...")
            # Maybe it's formatted differently
            content = content.replace(
                "await client.get_health",
                "await client.get_recent_blockhash"
            )
        
        # Write back
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✓ Updated: {filepath}")
        
    except Exception as e:
        print(f"❌ Error fixing connection_manager.py: {e}")

def fix_wallet_manager_directly():
    """Directly fix the wallet_manager.py initialize method"""
    filepath = "src/core/wallet_manager.py"
    
    try:
        # Read the file
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the initialize method and make it async
        if "def initialize(self) -> None:" in content:
            content = content.replace(
                "def initialize(self) -> None:",
                "async def initialize(self) -> None:"
            )
            print("✓ Made initialize() method async")
        elif "def initialize(self):" in content:
            content = content.replace(
                "def initialize(self):",
                "async def initialize(self):"
            )
            print("✓ Made initialize() method async")
        else:
            print("⚠️  Could not find initialize method to fix")
        
        # Also check if it has the load_keypair call
        if "await self.load_keypair()" not in content and "self.load_keypair()" in content:
            # The load_keypair is also async, so we need to await it
            content = content.replace(
                "self.load_keypair()",
                "await self.load_keypair()"
            )
            print("✓ Added await to load_keypair()")
        
        # Write back
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✓ Updated: {filepath}")
        
    except Exception as e:
        print(f"❌ Error fixing wallet_manager.py: {e}")

def check_current_files():
    """Check the current state of the files"""
    print("\n📋 Checking current file states...")
    
    # Check connection_manager.py
    try:
        with open("src/core/connection_manager.py", 'r') as f:
            content = f.read()
            if "get_health" in content:
                print("❌ connection_manager.py still has get_health()")
            else:
                print("✓ connection_manager.py doesn't have get_health()")
    except Exception as e:
        print(f"❌ Could not read connection_manager.py: {e}")
    
    # Check wallet_manager.py
    try:
        with open("src/core/wallet_manager.py", 'r') as f:
            content = f.read()
            if "async def initialize" in content:
                print("✓ wallet_manager.py has async initialize()")
            else:
                print("❌ wallet_manager.py doesn't have async initialize()")
    except Exception as e:
        print(f"❌ Could not read wallet_manager.py: {e}")

def create_minimal_connection_manager():

    content = ''

import asyncio
from typing import List, Optional
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment, Confirmed

from src.utils.config import config_manager
from src.utils.logger import get_logger

logger = get_logger("connection")


class ConnectionManager:
    """Manages connections to Solana RPC endpoints."""
    
    def __init__(self):
        self.r