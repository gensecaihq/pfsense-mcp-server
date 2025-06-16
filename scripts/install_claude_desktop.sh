#!/bin/bash
# Install script for Claude Desktop integration

echo "pfSense MCP Server - Claude Desktop Installation"
echo "=============================================="

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_PATH="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    CONFIG_PATH="$APPDATA/Claude/claude_desktop_config.json"
else
    CONFIG_PATH="$HOME/.config/Claude/claude_desktop_config.json"
fi

echo "Detected config path: $CONFIG_PATH"

# Create config directory
mkdir -p "$(dirname "$CONFIG_PATH")"

# Get current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Create config
cat > "$CONFIG_PATH" << CONFIG
{
  "mcpServers": {
    "pfsense": {
      "command": "python",
      "args": ["$PROJECT_DIR/main.py"],
      "env": {
        "MCP_MODE": "stdio",
        "PFSENSE_URL": "https://your-pfsense.local",
        "PFSENSE_CONNECTION_METHOD": "rest",
        "PFSENSE_API_KEY": "your-api-key",
        "PFSENSE_API_SECRET": "your-api-secret",
        "DEFAULT_ACCESS_LEVEL": "READ_ONLY"
      }
    }
  }
}
CONFIG

echo "Configuration written to: $CONFIG_PATH"
echo ""
echo "Next steps:"
echo "1. Edit $CONFIG_PATH with your pfSense details"
echo "2. Restart Claude Desktop"
echo "3. Test with: 'Show me the pfSense system status'"
