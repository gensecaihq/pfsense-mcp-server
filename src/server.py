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
VERSION = "1.0.0"

# Initialize FastMCP server
mcp = FastMCP(
    "pfSense Enhanced MCP Server",
    version=VERSION,
    instructions=(
        "You are managing a pfSense firewall via REST API v2. "
        "All destructive operations (delete, bulk block) require confirm=True. "
        "Object IDs are non-persistent array indices — they shift after deletions. "
        "Use verify_descr on update/delete to guard against stale IDs, or "
        "use find_object_by_field for stable lookups. "
        "Always call search/list tools before update/delete to get current IDs. "
        "Log retrieval is capped at 50 lines. Page size is capped at 200."
    ),
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
        version = version_map.get(pf_version)
        if version is None:
            raise ValueError(
                f"PFSENSE_VERSION='{pf_version}' is not recognized. "
                f"Valid options: {', '.join(version_map.keys())}"
            )

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
            raise ValueError(
                "PFSENSE_URL is not set. Copy .env.example to .env and configure it, "
                "or set the PFSENSE_URL environment variable."
            )

        api_key = (os.getenv("PFSENSE_API_KEY") or "").strip() or None
        if auth_method == AuthMethod.API_KEY and not api_key:
            logger.warning("PFSENSE_API_KEY is not set — API calls will fail with 401")

        try:
            api_timeout = int(os.getenv("API_TIMEOUT", "30"))
        except ValueError:
            api_timeout = 30

        api_client = EnhancedPfSenseAPIClient(
            host=pfsense_url,
            auth_method=auth_method,
            username=os.getenv("PFSENSE_USERNAME"),
            password=os.getenv("PFSENSE_PASSWORD"),
            api_key=api_key,
            verify_ssl=os.getenv("VERIFY_SSL", "true").lower() == "true",
            timeout=api_timeout,
            version=version,
            enable_hateoas=os.getenv("ENABLE_HATEOAS", "false").lower() == "true"
        )
        logger.info(f"API client initialized for pfSense {version.value} at {pfsense_url}")
    return api_client
