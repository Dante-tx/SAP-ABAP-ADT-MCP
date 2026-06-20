"""ADT object lock/unlock mixin (shared by create, update, delete)."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from sap_mcp.connectors.core.constants import ADT_SESSION_HEADER, ADT_SESSION_STATEFUL
from sap_mcp.errors import SapBackendError


class LockMixin:
    _LOCK_ACCEPT = "application/*,application/vnd.sap.as+xml;charset=UTF-8;dataname=com.sap.adt.lock.result"

    async def _lock_object(self, uri: str) -> str:
        self._set_adt_session_type(ADT_SESSION_STATEFUL)
        response = await self._request(
            "POST", uri,
            params={"_action": "LOCK", "accessMode": "MODIFY"},
            headers=self._stateful_headers(),
            accept=self._LOCK_ACCEPT,
        )
        handle = self._lock_handle_from_xml(response.text)
        if not handle:
            raise SapBackendError(
                "Failed to obtain lock handle — object may be locked by another user",
                details={"category": "lock_failed"},
            )
        return handle

    async def _unlock_object(self, uri: str, lock_handle: str) -> None:
        try:
            await self._request(
                "POST", uri,
                params={"_action": "UNLOCK", "lockHandle": lock_handle},
                headers=self._stateful_headers(),
                accept="application/xml, text/plain, */*",
            )
        except SapBackendError:
            pass
        finally:
            await self._restore_stateless_session()

    def _stateful_headers(self) -> dict[str, str]:
        return {ADT_SESSION_HEADER: ADT_SESSION_STATEFUL}

    @staticmethod
    def _lock_handle_from_xml(text: str) -> str | None:
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return None
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1].casefold() == "lock_handle" and element.text:
                return element.text.strip()
        return None
