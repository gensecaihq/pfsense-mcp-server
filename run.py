#!/usr/bin/env python3
"""
Enhanced pfSense MCP Server Launcher
Simple script to start the server with proper Python path handling
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set PYTHONPATH environment variable for subprocess compatibility
os.environ['PYTHONPATH'] = str(project_root)

if __name__ == "__main__":
    from src.main import main
    import asyncio
    
    # Run the main function
    asyncio.run(main())