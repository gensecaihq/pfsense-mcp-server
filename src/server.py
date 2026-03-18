"""MCP server instance and API client singleton."""

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastmcp import FastMCP

from .client import EnhancedPfSenseAPIClient
from .models import AuthMethod, PfSenseVersion

# Load environment variables from .env file
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Version
VERSION = "5.0.0"

# Initialize FastMCP server
mcp = FastMCP(
    "pfSense Enhanced MCP Server",
)

# Global API client
api_client: Optional[EnhancedPfSenseAPIClient] = None


def reset_api_client():
    """Reset the global API client singleton (call after close())."""
    global api_client
    api_client = None


def get_api_client() -> EnhancedPfSenseAPIClient:
    """Get or create enhanced API client"""
    global api_client
    if api_client is None:
        # Determine version
        pf_version = os.getenv("PFSENSE_VERSION", "CE_2_8_0")
        version_map = {
            "CE_2_8_0": PfSenseVersion.CE_2_8_0,
            "CE_2_8_1": PfSenseVersion.CE_2_8_1,
            "CE_26_03": PfSenseVersion.CE_26_03,
            "PLUS_24_11": PfSenseVersion.PLUS_24_11,
            "PLUS_25_11": PfSenseVersion.PLUS_25_11,
        }
        version = version_map.get(pf_version, PfSenseVersion.CE_2_8_0)

        # Determine auth method
        auth_method_str = os.getenv("AUTH_METHOD", "api_key").lower()
        if auth_method_str == "basic":
            auth_method = AuthMethod.BASIC
        elif auth_method_str == "jwt":
            auth_method = AuthMethod.JWT
        else:
            auth_method = AuthMethod.API_KEY

        pfsense_url = os.getenv("PFSENSE_URL", "").strip()
        if not pfsense_url:
            logger.warning("PFSENSE_URL is not set — copy .env.example to .env and configure it")
            pfsense_url = "https://pfsense.local"

        api_key = (os.getenv("PFSENSE_API_KEY") or "").strip() or None
        if auth_method == AuthMethod.API_KEY and not api_key:
            logger.warning("PFSENSE_API_KEY is not set — API calls will fail with 401")

        if pf_version not in version_map:
            logger.warning(
                "PFSENSE_VERSION='%s' is not recognized — defaulting to CE_2_8_0. "
                "Valid options: %s", pf_version, ", ".join(version_map.keys())
            )

        api_client = EnhancedPfSenseAPIClient(
            host=pfsense_url,
            auth_method=auth_method,
            username=os.getenv("PFSENSE_USERNAME"),
            password=os.getenv("PFSENSE_PASSWORD"),
            api_key=api_key,
            verify_ssl=os.getenv("VERIFY_SSL", "true").lower() == "true",
            version=version,
            enable_hateoas=os.getenv("ENABLE_HATEOAS", "false").lower() == "true"
        )
        logger.info(f"API client initialized for pfSense {version.value} at {pfsense_url}")
    return api_client
