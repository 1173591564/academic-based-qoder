"""Process hosting and HTTP access policy for the Scholar MCP adapter."""

import hmac
import ipaddress
import os
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from scholar_mcp.health import readiness_payload


@dataclass(frozen=True)
class TransportSettings:
    """Validated process settings for one Scholar MCP server."""

    transport: str
    host: str
    port: int
    bearer_token: str
    allow_insecure_loopback: bool

    @classmethod
    def from_environment(cls) -> "TransportSettings":
        """Load transport settings from the process environment."""
        return cls(
            transport=os.getenv("SCHOLAR_MCP_TRANSPORT", "stdio"),
            host=os.getenv("SCHOLAR_MCP_HOST", "127.0.0.1"),
            port=int(os.getenv("SCHOLAR_MCP_PORT", "8000")),
            bearer_token=os.getenv("SCHOLAR_MCP_TOKEN", ""),
            allow_insecure_loopback=(
                os.getenv("SCHOLAR_MCP_ALLOW_INSECURE_LOOPBACK", "") == "1"
            ),
        )

    def validate(self) -> None:
        """Reject unsupported or unauthenticated network configurations."""
        if self.transport not in {"stdio", "streamable-http"}:
            raise RuntimeError("SCHOLAR_MCP_TRANSPORT must be stdio or streamable-http")
        if self.transport == "stdio" or self.bearer_token:
            return
        if not self.allow_insecure_loopback or not is_loopback_host(self.host):
            raise RuntimeError(
                "SCHOLAR_MCP_TOKEN is required for streamable HTTP unless explicit "
                "loopback-only no-auth mode is enabled"
            )


def bearer_token_middleware(token: str):
    """Require the configured Bearer token on every HTTP request."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    expected = f"Bearer {token}"

    class BearerTokenAuthentication(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            supplied = request.headers.get("authorization", "")
            if not hmac.compare_digest(supplied, expected):
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return await call_next(request)

    return BearerTokenAuthentication


def loopback_only_middleware():
    """Reject requests that do not arrive directly through a loopback authority."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class LoopbackOnly(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            client_host = request.client.host if request.client else ""
            if not is_loopback_host(request.url.hostname or ""):
                return JSONResponse({"error": "forbidden"}, status_code=403)
            if not is_loopback_host(client_host):
                return JSONResponse({"error": "forbidden"}, status_code=403)
            return await call_next(request)

    return LoopbackOnly


def is_loopback_host(host: str) -> bool:
    """Return whether a host is a numeric loopback address."""
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def run_transport(mcp: FastMCP) -> None:
    """Run the configured stdio or authenticated Streamable HTTP transport."""
    settings = TransportSettings.from_environment()
    settings.validate()
    if settings.transport == "stdio":
        mcp.run()
        return

    app = mcp.streamable_http_app()

    async def readiness(_request: Request) -> JSONResponse:
        status_code, body = readiness_payload()
        return JSONResponse(body, status_code=status_code)

    app.add_route("/private/health/ready", readiness, methods=["GET"])
    if settings.bearer_token:
        app.add_middleware(bearer_token_middleware(settings.bearer_token))
    else:
        app.add_middleware(loopback_only_middleware())

    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
