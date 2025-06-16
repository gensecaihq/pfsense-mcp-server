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
python --version

# Check connection
echo -n "Testing pfSense connection: "
python scripts/test_connection.py > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Connected"
else
    echo "❌ Failed"
fi

# Check HTTP endpoint (if in HTTP mode)
if [ "$MCP_MODE" = "http" ]; then
    echo -n "HTTP endpoint: "
    curl -s http://localhost:8000/health > /dev/null
    if [ $? -eq 0 ]; then
        echo "✅ Healthy"
    else
        echo "❌ Not responding"
    fi
fi

echo "================================"
