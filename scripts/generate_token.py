#!/usr/bin/env python3
"""Generate access tokens for pfSense MCP Server"""

import json
import sys
import argparse
from datetime import datetime, timedelta
import secrets
import base64

def generate_token(user_id: str, access_level: str, expires_days: int = 30) -> str:
    """Generate a simple token"""
    
    valid_levels = ["READ_ONLY", "SECURITY_WRITE", "ADMIN_WRITE", "COMPLIANCE_READ", "EMERGENCY_WRITE"]
    
    if access_level not in valid_levels:
        print(f"Error: Invalid access level. Choose from: {', '.join(valid_levels)}")
        sys.exit(1)
    
    token_data = {
        "user_id": user_id,
        "access_level": access_level,
        "issued": datetime.utcnow().isoformat(),
        "expires": (datetime.utcnow() + timedelta(days=expires_days)).isoformat(),
        "token_id": secrets.token_hex(16)
    }
    
    # Simple encoding (in production, use proper JWT)
    token = base64.b64encode(json.dumps(token_data).encode()).decode()
    
    return token, token_data

def main():
    parser = argparse.ArgumentParser(description="Generate MCP access tokens")
    parser.add_argument("user_id", help="User identifier")
    parser.add_argument("access_level", help="Access level")
    parser.add_argument("--expires", type=int, default=30, help="Days until expiration")
    
    args = parser.parse_args()
    
    token, data = generate_token(args.user_id, args.access_level, args.expires)
    
    print("\n=== pfSense MCP Server Token ===")
    print(f"User: {data['user_id']}")
    print(f"Access Level: {data['access_level']}")
    print(f"Expires: {data['expires']}")
    print(f"\nToken:\n{token}")
    print("\n=== Usage ===")
    print("Set as environment variable:")
    print(f"export MCP_TOKEN={token}")

if __name__ == "__main__":
    main()
