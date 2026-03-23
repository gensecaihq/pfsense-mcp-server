#!/bin/bash
# Health check for pfSense MCP Server

echo "pfSense MCP Server Health Check"
echo "================================"

# Check if running in Docker
if [ -f /.dockerenv ]; then
    echo "Running in Docker container"
fi

# Check Python
echo -n "Python version: "
python3 --version 2>/dev/null || python --version

# Check connection
echo -n "Testing pfSense connection: "
if python3 -c "
import asyncio, os, sys
sys.path.insert(0, '.')
from src.server import get_api_client, reset_api_client
async def test():
    client = get_api_client()
    try:
        return await client.test_connection()
    finally:
        await client.close()
        reset_api_client()
result = asyncio.run(test())
sys.exit(0 if result else 1)
" 2>/dev/null; then
    echo "Connected"
else
    echo "Failed"
fi

# Check HTTP endpoint (if in HTTP transport mode)
TRANSPORT="${MCP_TRANSPORT:-stdio}"
if [ "$TRANSPORT" = "streamable-http" ]; then
    PORT="${MCP_PORT:-3000}"
    echo -n "HTTP endpoint (port $PORT): "
    if curl -sf "http://localhost:$PORT/mcp" > /dev/null 2>&1; then
        echo "Healthy"
    else
        echo "Not responding"
    fi
fi

echo "================================"
