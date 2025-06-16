#!/usr/bin/env python3
"""Quick test of MCP functionality"""

import asyncio
import json
from main import MCPServer, MCPRequest, SecurityContext, AccessLevel
from datetime import datetime

async def test():
    print("Testing pfSense MCP Server...")
    
    # Create server
    server = MCPServer()
    
    # Test initialize
    print("\n1. Testing initialize...")
    request = MCPRequest(method="initialize")
    response = await server.handle_request(request)
    print(f"✅ Server info: {response.result['serverInfo']}")
    
    # Test list tools
    print("\n2. Testing tool list...")
    context = SecurityContext(
        user_id="test_user",
        access_level=AccessLevel.READ_ONLY,
        timestamp=datetime.utcnow()
    )
    tools = await server.list_tools(context)
    print(f"✅ Available tools: {[t['name'] for t in tools]}")
    
    # Test prompt processing
    print("\n3. Testing prompt processing...")
    result = await server.process_prompt("Show me the system status", context)
    print(f"✅ Prompt processed: {result['tool']}")
    
    print("\n✨ All tests passed!")

if __name__ == "__main__":
    asyncio.run(test())
