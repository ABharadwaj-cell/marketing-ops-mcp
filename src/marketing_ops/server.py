"""Official MCP SDK server, local by default, with guarded HTTP transport."""

import hmac
import os

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from .tools import REGISTRY


class BearerAuthASGI:
    """Authenticate every HTTP request before it reaches the MCP application."""

    def __init__(self, app, token):
        if not token or len(token) < 32:
            raise ValueError("MARKETING_OPS_HTTP_TOKEN must be at least 32 characters")
        self.app = app
        self.token = ("Bearer " + token).encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        supplied = next(
            (value for key, value in scope.get("headers", []) if key.lower() == b"authorization"),
            b"",
        )
        if not hmac.compare_digest(supplied, self.token):
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"www-authenticate", b"Bearer"),
                    (b"cache-control", b"no-store"),
                ],
            })
            await send({"type": "http.response.body", "body": b"Unauthorized"})
            return
        await self.app(scope, receive, send)


def run_http(server):
    """Explicitly configured, loopback-only HTTP. Never expose without a TLS gateway."""
    token = os.environ.get("MARKETING_OPS_HTTP_TOKEN", "")
    if len(token) < 32:
        raise ValueError(
            "HTTP is disabled until MARKETING_OPS_HTTP_TOKEN is set to a "
            "random secret of at least 32 characters. Use stdio for local clients."
        )
    import uvicorn

    uvicorn.run(
        BearerAuthASGI(server.streamable_http_app(), token),
        host="127.0.0.1",
        port=8765,
        proxy_headers=False,
    )


def build_server():
    server = FastMCP(
        "Marketing Ops MCP", host="127.0.0.1", port=8765, stateless_http=True, json_response=True
    )
    for name, (schema, handler, description) in REGISTRY.items():
        def bind(input_type, function):
            def invoke(payload):
                return function(payload)

            invoke.__annotations__ = {"payload": input_type, "return": dict}
            return invoke

        server.add_tool(
            bind(schema, handler),
            name=name,
            description=description,
            annotations=ToolAnnotations(
                readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
            ),
        )
    return server
