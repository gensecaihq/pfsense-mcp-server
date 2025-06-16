#!/usr/bin/env python3
"""Test connection to pfSense"""

import os
import asyncio
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import PfSenseConnectionManager

async def test():
    """Test pfSense connection"""
    print("Testing pfSense connection...")
    print(f"URL: {os.getenv('PFSENSE_URL')}")
    print(f"Method: {os.getenv('PFSENSE_CONNECTION_METHOD', 'rest')}")
    
    manager = PfSenseConnectionManager()
    
    try:
        connected = await manager.test_connection()
        if connected:
            print("✅ Connection successful!")
            
            # Try to get system status
            status = await manager.execute("system.status")
            print(f"System version: {status.get('version', 'unknown')}")
            print(f"Uptime: {status.get('uptime', 'unknown')}")
        else:
            print("❌ Connection failed!")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        await manager.close()

if __name__ == "__main__":
    asyncio.run(test())
