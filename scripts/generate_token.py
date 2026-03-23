#!/usr/bin/env python3
"""Generate a bearer token for pfSense MCP Server HTTP transport mode.

The MCP server requires MCP_API_KEY when running in streamable-http transport.
This script generates a secure random token suitable for that purpose.
"""

import secrets
import sys


def main():
    token = secrets.token_urlsafe(32)

    print("\n=== pfSense MCP Server Bearer Token ===")
    print(f"\nToken:\n{token}")
    print("\n=== Usage ===")
    print("Add to your .env file:")
    print(f"MCP_API_KEY={token}")
    print("\nOr set as environment variable:")
    print(f"export MCP_API_KEY={token}")
    print("\nThis token is used for bearer authentication when running")
    print("the MCP server in streamable-http transport mode.")


if __name__ == "__main__":
    main()
