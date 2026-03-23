"""Bearer token auth middleware for HTTP transport."""

import hmac


class BearerAuthMiddleware:
    """ASGI middleware that checks for a valid Bearer token in the Authorization header.

    Deny-by-default: only 'lifespan' scope is allowed without auth.
    Both HTTP and WebSocket connections require a valid bearer token.
    """

    def __init__(self, app, api_key: str):
        self.app = app
        self.api_key = api_key

    async def __call__(self, scope, receive, send):
        # Allow ASGI lifespan events (startup/shutdown) without auth
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return

        # All other scope types (http, websocket) require auth
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        if not auth_header.startswith("Bearer ") or not hmac.compare_digest(auth_header[7:], self.api_key):
            if scope["type"] == "websocket":
                # For WebSocket, send a close frame
                await send({"type": "websocket.close", "code": 4401})
            else:
                from starlette.responses import JSONResponse
                response = JSONResponse({"error": "Unauthorized"}, status_code=401)
                await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
