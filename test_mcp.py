#!/usr/bin/env python3
"""Quick test of MCP functionality"""

import asyncio
import json
import os
from unittest.mock import patch, MagicMock
from main import MCPServer, MCPRequest, SecurityContext, AccessLevel, PfSenseConnectionManager
from datetime import datetime


async def test_ssh_command_injection_vulnerability():
    print("\n4. Testing SSH Command Injection Vulnerability...")
    original_conn_method = os.environ.get("PFSENSE_CONNECTION_METHOD")
    try:
        with patch('main.paramiko.SSHClient') as mock_ssh_client_constructor:
            mock_ssh_instance = MagicMock()
            mock_ssh_client_constructor.return_value = mock_ssh_instance

            os.environ["PFSENSE_CONNECTION_METHOD"] = "ssh"
            # Ensure necessary SSH config env vars are set to avoid other errors
            # if the manager tried to connect before our intended check.
            os.environ["PFSENSE_SSH_HOST"] = "dummy_host"
            os.environ["PFSENSE_SSH_USERNAME"] = "dummy_user"
            os.environ["PFSENSE_SSH_PASSWORD"] = "dummy_pass" # For non-key auth path

            manager = PfSenseConnectionManager()

            try:
                await manager.execute("this_is_an_invalid_command_exploit")
                assert False, "ValueError was not raised for invalid SSH command"
            except ValueError as e:
                print(f"✅ Caught expected ValueError for invalid command: {e}")
                assert "Unsupported SSH command" in str(e)
            except Exception as e:
                assert False, f"An unexpected exception was raised: {e}"

            mock_ssh_instance.connect.assert_not_called()
            mock_ssh_instance.exec_command.assert_not_called()
            print("✅ SSH client methods (connect, exec_command) not called for invalid command.")

    finally:
        if original_conn_method is None:
            del os.environ["PFSENSE_CONNECTION_METHOD"]
        else:
            os.environ["PFSENSE_CONNECTION_METHOD"] = original_conn_method
        # Clean up dummy env vars
        for var in ["PFSENSE_SSH_HOST", "PFSENSE_SSH_USERNAME", "PFSENSE_SSH_PASSWORD"]:
            if f"dummy_{var}" in os.environ: # Check if we set them
                 del os.environ[var]


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

    await test_ssh_command_injection_vulnerability()
    
    print("\n✨ All tests passed!")

if __name__ == "__main__":
    asyncio.run(test())
