from __future__ import annotations

import logging
import threading
from urllib.parse import urlparse

import uvicorn

from sap_mcp.callback import create_callback_app
from sap_mcp.config import AppConfig, get_config
from sap_mcp.mcp_server import create_mcp


def _callback_host_port(config: AppConfig) -> tuple[str, int]:
    parsed = urlparse(config.abap_dev.callback_url)
    return parsed.hostname or "127.0.0.1", parsed.port or 8000


def start_callback_server(config: AppConfig) -> None:
    host, port = _callback_host_port(config)
    server_config = uvicorn.Config(
        create_callback_app(config, client_name="IDE"),
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(server_config)
    thread = threading.Thread(target=server.run, name="sap-mcp-sso-callback", daemon=True)
    thread.start()


def main() -> None:
    logging.getLogger("mcp").setLevel(logging.WARNING)
    logging.getLogger("mcp.server").setLevel(logging.WARNING)
    config = get_config()
    start_callback_server(config)
    create_mcp(config, stateless_http=False).run(transport="stdio")


if __name__ == "__main__":
    main()
