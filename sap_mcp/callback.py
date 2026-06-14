from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from sap_mcp.auth.browser_sso import BrowserSsoSessionManager
from sap_mcp.config import AppConfig


async def healthz(_request):
    return JSONResponse({"status": "ok"})


def create_callback_app(config: AppConfig, *, client_name: str) -> Starlette:
    async def adt_redirect(request):
        params = {key: value for key, value in request.query_params.multi_items()}
        BrowserSsoSessionManager(config.abap_dev).save_reentrance_callback(params)
        fields = ", ".join(sorted(params)) or "none"
        return HTMLResponse(
            "<!doctype html><html><head><title>ABAP Development Tools</title></head>"
            '<body style="font-family: Arial, sans-serif; margin: 0;">'
            '<div style="background:#31495f;color:white;padding:12px 24px;font-weight:700;">ABAP Development Tools</div>'
            '<main style="margin:96px auto;max-width:660px;border:1px solid #ddd;padding:32px;box-shadow:0 1px 6px #ccc;">'
            "<h1>You have been successfully logged on</h1>"
            f"<p>You can close this page and continue in {client_name}.</p>"
            f"<p>Captured fields: {fields}</p>"
            "</main></body></html>"
        )

    return Starlette(
        routes=[
            Route("/healthz", healthz, methods=["GET"]),
            Route("/adt/redirect", adt_redirect, methods=["GET"]),
            Route("/logon/success", adt_redirect, methods=["GET"]),
        ]
    )
