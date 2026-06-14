from __future__ import annotations

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount, Route

from sap_mcp.callback import create_callback_app, healthz
from sap_mcp.config import get_config
from sap_mcp.mcp_server import create_mcp
from sap_mcp.security import BearerAuthMiddleware, token_values


config = get_config()
mcp = create_mcp(config)
mcp_app = mcp.streamable_http_app()
callback_app = create_callback_app(config, client_name="Codex")


app = Starlette(
    routes=[
        Route("/healthz", healthz, methods=["GET"]),
        *callback_app.routes[1:],
        Mount("/", app=mcp_app),
    ],
    lifespan=mcp_app.router.lifespan_context,
)
app.add_middleware(BearerAuthMiddleware, allowed_tokens=token_values(config))


def main() -> None:
    uvicorn.run("sap_mcp.server:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
