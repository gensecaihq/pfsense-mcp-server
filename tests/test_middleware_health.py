"""The bearer-auth middleware must answer /health without a token (so container
health checks pass) while still 401ing everything else."""
from src.middleware import BearerAuthMiddleware

_TOKEN = "g7Qx2mVr8ThLpZ4wNc0aBdEf"


async def _drive(mw, path, headers=None):
    scope = {"type": "http", "path": path, "headers": headers or []}
    sent = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(msg):
        sent.append(msg)

    reached_app = {"v": False}
    await mw(scope, receive, send)
    return sent, reached_app


def _status(sent):
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


async def test_health_returns_200_without_auth():
    reached = {"v": False}

    async def app(scope, receive, send):
        reached["v"] = True

    mw = BearerAuthMiddleware(app, _TOKEN)
    sent, _ = await _drive(mw, "/health")
    assert _status(sent) == 200
    assert reached["v"] is False  # health is handled by the middleware, not the app


async def test_mcp_without_token_still_401s():
    async def app(scope, receive, send):
        raise AssertionError("app should not be reached without a valid token")

    mw = BearerAuthMiddleware(app, _TOKEN)
    sent, _ = await _drive(mw, "/mcp")
    assert _status(sent) == 401


async def test_mcp_with_valid_token_reaches_app():
    reached = {"v": False}

    async def app(scope, receive, send):
        reached["v"] = True

    mw = BearerAuthMiddleware(app, _TOKEN)
    headers = [(b"authorization", f"Bearer {_TOKEN}".encode())]
    await _drive(mw, "/mcp", headers=headers)
    assert reached["v"] is True
