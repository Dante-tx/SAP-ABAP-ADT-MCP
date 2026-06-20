from __future__ import annotations

from sap_mcp.connectors.core.base import BaseMixin


class DestinationsMixin(BaseMixin):
    async def list_destinations(self) -> list[str]:
        destination = self._destination_id()
        return [destination] if destination else ["default"]
