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
      "args": ["-m", "src.main"],
      "cwd": "$PROJECT_DIR",
      "env": {
        "PFSENSE_URL": "https://your-pfsense.local",
        "AUTH_METHOD": "basic",
        "PFSENSE_USERNAME": "admin",
        "PFSENSE_PASSWORD": "your-password",
        "PFSENSE_VERSION": "PLUS_24_11",
        "VERIFY_SSL": "false"
      }
    }
  }
}
CONFIG

echo "Configuration written to: $CONFIG_PATH"
echo ""
echo "Next steps:"
echo "1. Edit $CONFIG_PATH with your pfSense URL and credentials"
echo "2. Install dependencies: cd $PROJECT_DIR && pip install -r requirements.txt"
echo "3. Restart Claude Desktop"
echo "4. Test with: 'Show me the pfSense system status'"
