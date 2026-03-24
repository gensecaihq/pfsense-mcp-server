"""Bearer token auth and Origin validation middleware for HTTP transport.

Per MCP spec (2025-03-26+), servers MUST validate the Origin header on all
incoming HTTP connections to prevent DNS rebinding attacks.
"""

import hmac
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Default allowed origins for local development.
# In production, set MCP_ALLOWED_ORIGINS env var.
_LOCAL_ORIGINS = frozenset({
    "http://localhost",
    "https://localhost",
    "http://127.0.0.1",
    "https://127.0.0.1",
})


class BearerAuthMiddleware:
    """ASGI middleware that validates Origin headers and Bearer tokens.

    Deny-by-default: only 'lifespan' scope is allowed without auth.
    Both HTTP and WebSocket connections require:
    1. A valid Origin header (MCP spec MUST requirement)
    2. A valid Bearer token in the Authorization header

    Args:
        app: The ASGI application to wrap.
        api_key: Bearer token for authentication.
        allowed_origins: Set of allowed origin strings (scheme + host, no path).
            If None, only localhost origins are allowed.
    """

    def __init__(self, app, api_key: str, allowed_origins: set = None):
        self.app = app
        # Support multiple API keys (comma-separated MCP_API_KEY for per-user tokens)
        # Format: "token1,token2,token3" or just "single_token"
        self.api_keys = frozenset(k.strip() for k in api_key.split(",") if k.strip())
        self.allowed_origins = allowed_origins or _LOCAL_ORIGINS

    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if the Origin is in the allowed set.

        Compares scheme + host (with optional port) against the allowlist.
        """
        if not origin:
            # No Origin header — browser requests always send it,
            # non-browser clients (curl, SDKs) may not.
            # Allow requests without Origin (server-to-server),
            # but block requests with an invalid Origin.
            return True
        # Normalize: strip trailing slash, lowercase
        normalized = origin.rstrip("/").lower()
        if normalized in self.allowed_origins:
            return True
        # Also check with default ports stripped
        parsed = urlparse(normalized)
        base = f"{parsed.scheme}://{parsed.hostname}"
        return base in self.allowed_origins

    async def __call__(self, scope, receive, send):
        # Allow ASGI lifespan events (startup/shutdown) without auth
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return

        # All other scope types (http, websocket) require auth
        headers = dict(scope.get("headers", []))

        # 1. Origin validation (MCP spec MUST)
        origin = headers.get(b"origin", b"").decode()
        if origin and not self._is_origin_allowed(origin):
            logger.warning("Rejected request with disallowed Origin: %s", origin)
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 4403})
            else:
                from starlette.responses import JSONResponse
                response = JSONResponse(
                    {"error": "Forbidden: Origin not allowed"},
                    status_code=403,
                )
                await response(scope, receive, send)
            return

        # 2. Bearer token auth (supports multiple keys for per-user tokens)
        auth_header = headers.get(b"authorization", b"").decode()
        token_valid = False
        if auth_header.startswith("Bearer "):
            presented_token = auth_header[7:]
            for valid_key in self.api_keys:
                if hmac.compare_digest(presented_token, valid_key):
                    token_valid = True
                    break
        if not token_valid:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 4401})
            else:
                from starlette.responses import JSONResponse
                response = JSONResponse({"error": "Unauthorized"}, status_code=401)
                await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
