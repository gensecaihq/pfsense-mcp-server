"""Bearer token auth middleware for HTTP transport."""


class BearerAuthMiddleware:
    """ASGI middleware that checks for a valid Bearer token in the Authorization header."""

    def __init__(self, app, api_key: str):
        self.app = app
        self.api_key = api_key

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()
            if not auth_header.startswith("Bearer ") or auth_header[7:] != self.api_key:
                from starlette.responses import JSONResponse
                response = JSONResponse({"error": "Unauthorized"}, status_code=401)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
