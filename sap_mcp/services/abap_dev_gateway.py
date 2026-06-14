from __future__ import annotations

from typing import Any

from sap_mcp.auth.browser_sso import BrowserSsoSessionManager
from sap_mcp.config import AbapDevConfig
from sap_mcp.connectors.adt import AdtConnector
from sap_mcp.errors import AuthorizationError, ConfigError
from sap_mcp.security import UserContext, authorize_tool


class AbapDevGateway:
    def __init__(self, config: AbapDevConfig):
        self.config = config
        self.sessions = BrowserSsoSessionManager(config)

    async def login(self, user: UserContext) -> dict[str, Any]:
        authorize_tool(user, "abap_adt_login")
        return await self.sessions.login()

    def save_session(self, user: UserContext, cookies: dict[str, str], headers: dict[str, str] | None = None) -> dict[str, Any]:
        authorize_tool(user, "abap_save_sso_session", write=True)
        return self.sessions.save_session(cookies, headers)

    def save_cookie_header(self, user: UserContext, cookie_header: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        authorize_tool(user, "abap_save_sso_cookie_header", write=True)
        return self.sessions.save_cookie_header(cookie_header, headers)

    async def connect(self, user: UserContext) -> dict[str, Any]:
        authorize_tool(user, "abap_adt_connect")
        _connector, discovery = await self._authenticated_connector()
        return discovery

    async def search_objects(
        self,
        user: UserContext,
        query: str,
        max_results: int = 20,
        object_type: str | None = None,
        package: str | None = None,
    ) -> list[dict[str, Any]]:
        authorize_tool(user, "abap_search_objects")
        connector, _discovery = await self._authenticated_connector()
        try:
            return await connector.search_objects(query, max_results, object_type, package)
        except AuthorizationError as exc:
            raise self._login_required_error("The saved SSO session expired while searching ABAP objects.") from exc

    async def read_source(self, user: UserContext, object_type: str, name: str) -> dict[str, Any]:
        authorize_tool(user, "abap_read_source")
        connector, _discovery = await self._authenticated_connector()
        try:
            return await connector.read_source(object_type, name)
        except AuthorizationError as exc:
            raise self._login_required_error("The saved SSO session expired while reading ABAP source.") from exc

    async def create_object(
        self,
        user: UserContext,
        object_type: str,
        name: str,
        package: str,
        description: str,
        reason: str,
        source: str | None = None,
    ) -> dict[str, Any]:
        authorize_tool(user, "abap_create_object", write=True)
        connector, _discovery = await self._authenticated_connector()
        try:
            return await connector.create_object(object_type, name, package, description, reason, source)
        except AuthorizationError as exc:
            raise self._login_required_error("The saved SSO session expired while creating the ABAP object.") from exc

    async def update_source(
        self,
        user: UserContext,
        object_type: str,
        name: str,
        source: str,
        etag: str,
        reason: str,
    ) -> dict[str, Any]:
        authorize_tool(user, "abap_update_source", write=True)
        connector, _discovery = await self._authenticated_connector()
        try:
            return await connector.update_source(object_type, name, source, etag, reason)
        except AuthorizationError as exc:
            raise self._login_required_error("The saved SSO session expired while updating ABAP source.") from exc

    async def activate_object(self, user: UserContext, object_type: str, name: str, reason: str) -> dict[str, Any]:
        authorize_tool(user, "abap_activate_object", write=True)
        connector, _discovery = await self._authenticated_connector()
        try:
            return await connector.activate_object(object_type, name, reason)
        except AuthorizationError as exc:
            raise self._login_required_error("The saved SSO session expired while activating the ABAP object.") from exc

    async def delete_object(self, user: UserContext, object_type: str, name: str, reason: str) -> dict[str, Any]:
        authorize_tool(user, "abap_delete_object", write=True)
        connector, _discovery = await self._authenticated_connector()
        try:
            return await connector.delete_object(object_type, name, reason)
        except AuthorizationError as exc:
            raise self._login_required_error("The saved SSO session expired while deleting the ABAP object.") from exc

    async def publish_service_binding(self, user: UserContext, name: str, reason: str) -> dict[str, Any]:
        authorize_tool(user, "abap_publish_service_binding", write=True)
        connector, _discovery = await self._authenticated_connector()
        try:
            return await connector.publish_service_binding(name, reason)
        except AuthorizationError as exc:
            raise self._login_required_error("The saved SSO session expired while publishing the service binding.") from exc

    async def _authenticated_connector(self) -> tuple[AdtConnector, dict[str, Any]]:
        try:
            session = self.sessions.load_session()
        except ConfigError as exc:
            raise self._login_required_error("No usable local SSO session was found.") from exc

        connector = AdtConnector(self.config, session)
        try:
            discovery = await connector.discovery()
        except AuthorizationError as exc:
            raise self._login_required_error("The saved SSO session is not authorized or has expired.") from exc
        return connector, discovery

    def _login_required_error(self, reason: str) -> AuthorizationError:
        login_result = self.sessions.open_login("auto_login_required")
        return AuthorizationError(
            f"{reason} Opened the ABAP ADT SSO login URL. Complete browser authentication, then retry the tool. "
            f"login_url={login_result['login_url']} session_path={login_result['session_path']}"
        )
