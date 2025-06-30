"""
Debug script to identify WebSocket connection issues
"""
# File: test-websocket-debug.py

import asyncio
import json
import websockets
import ssl

async def test_websocket_detailed():
    """Test WebSocket with detailed error reporting"""
    
    print("🔍 WebSocket Connection Debug Test")
    print("=" * 50)
    
    # Test different WebSocket endpoints
    endpoints = [
        ("Mainnet Beta", "wss://api.mainnet-beta.solana.com"),
        ("Mainnet Beta (Alternative)", "wss://solana-mainnet.g.alchemy.com/v2/demo"),
        ("Your RPC WebSocket", "wss://lb.drpc.org/ogrpc?network=solana&dkey=AnFgx_WRKUErtPzty2EXGn4b8SFRU-oR8JQVrqRhf0fE")
    ]
    
    for name, url in endpoints:
        print(f"\n📡 Testing {name}: {url}")
        print("-" * 40)
        
        try:
            # Try with SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Set a longer timeout
            async with websockets.connect(
                url, 
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            ) as ws:
                print("✅ Connected successfully!")
                
                # Test 1: Simple getSlot request
                print("   Testing getSlot...")
                test_msg = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getSlot"
                }
                
                await ws.send(json.dumps(test_msg))
                
                # Wait for response with timeout
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    result = json.loads(response)
                    
                    if "result" in result:
                        print(f"   ✅ getSlot response: {result['result']}")
                    else:
                        print(f"   ❌ Unexpected response: {result}")
                        
                except asyncio.TimeoutError:
                    print("   ❌ Timeout waiting for response")
                
                # Test 2: Account subscription
                print("   Testing accountSubscribe...")
                sub_msg = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "accountSubscribe",
                    "params": [
                        "DfyUYAcPc9dM4Mq6bLJGRTpsqPrBt5wKvtHdtwJFmZSA",
                        {"encoding": "base64", "commitment": "confirmed"}
                    ]
                }
                
                await ws.send(json.dumps(sub_msg))
                
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    result = json.loads(response)
                    
                    if "result" in result:
                        print(f"   ✅ Subscription ID: {result['result']}")
                    else:
                        print(f"   ❌ Subscription failed: {result}")
                        
                except asyncio.TimeoutError:
                    print("   ❌ Timeout waiting for subscription response")
                    
        except websockets.exceptions.InvalidURI as e:
            print(f"❌ Invalid URI: {e}")
        except websockets.exceptions.InvalidHandshake as e:
            print(f"❌ Handshake failed: {e}")
        except websockets.exceptions.WebSocketException as e:
            print(f"❌ WebSocket error: {e}")
        except ConnectionRefusedError:
            print("❌ Connection refused - endpoint may be down")
        except TimeoutError:
            print("❌ Connection timeout - endpoint not responding")
        except ssl.SSLError as e:
            print(f"❌ SSL error: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 50)
    print("📋 DIAGNOSIS:")
    print("If all connections failed:")
    print("1. Check your internet connection")
    print("2. Check if you're behind a firewall/proxy")
    print("3. Try using a VPN")
    print("4. Some RPC providers don't support WebSocket")

if __name__ == "__main__":
    asyncio.run(test_websocket_detailed())