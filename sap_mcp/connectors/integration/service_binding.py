from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

from sap_mcp.connectors.core.registry import ADT_BASE_PATH
from sap_mcp.errors import SapBackendError, ValidationError


class AdtServiceBindingMixin:
    async def _service_binding_operation(self, name: str, reason: str, action: str = "publish", odata_version: str | None = None) -> dict[str, Any]:
        action_title = action.capitalize()
        self._assert_write_allowed(reason)
        if not reason.strip():
            raise ValidationError(f"{action_title} reason is required")
        await self._assert_object_write_allowed("SRVB", name)
        object_name = name.upper()
        metadata = await self.read_source("SRVB", object_name)
        detected_version = self._service_binding_odata_version(metadata["source"], default=None)
        version = self._normalize_odata_version(odata_version or detected_version, default="V4")
        if odata_version and detected_version and version != detected_version:
            raise ValidationError(f"Service binding {object_name} is {detected_version}; requested {action} version was {version}")
        odata_path = f"odata{version.lower()}"
        currently_published = self._service_binding_published(metadata["source"])
        if action == "publish" and currently_published:
            return {"published": True, "changed": False, "object_type": "SRVB", "name": object_name, "odata_version": version, "status_code": metadata.get("status_code", 200)}
        if action == "unpublish" and not currently_published:
            return {"published": False, "changed": False, "object_type": "SRVB", "name": object_name, "odata_version": version, "status_code": metadata.get("status_code", 200)}
        uri = f"{ADT_BASE_PATH}/businessservices/{odata_path}/{quote(object_name)}?servicename={quote(object_name)}"
        body = self._object_references_xml([{"uri": uri, "type": "SRVB/SVB", "name": object_name}])
        response = await self._request(
            "POST", f"{ADT_BASE_PATH}/businessservices/{odata_path}/{action}jobs",
            params={"servicename": object_name},
            content=body.encode("utf-8"),
            headers={"Content-Type": "application/xml; charset=utf-8"},
            accept="application/xml, application/*, */*",
        )
        status = self._parse_status_messages(response.text)
        has_error = any(m.get("severity", "").upper() == "ERROR" for m in status)
        if has_error:
            messages = "; ".join(m.get("text", "") for m in status if m.get("text"))
            raise SapBackendError(f"Service binding {action} failed: {messages or response.text[:500]}")
        return {"published": action == "publish", "changed": True, "object_type": "SRVB", "name": object_name, "odata_version": version, "status_code": response.status_code, "messages": status}

    async def publish_service_binding(self, name: str, reason: str, odata_version: str | None = None) -> dict[str, Any]:
        return await self._service_binding_operation(name, reason, "publish", odata_version)

    async def unpublish_service_binding(self, name: str, reason: str, odata_version: str | None = None) -> dict[str, Any]:
        return await self._service_binding_operation(name, reason, "unpublish", odata_version)

    def _normalize_odata_version(self, version: str | None, default: str | None = "V4") -> str:
        raw_value = version or default
        if not raw_value:
            raise ValidationError("OData version must be V2 or V4")
        raw = raw_value.strip().upper().replace("ODATA", "").replace("\\", "").replace("/", "").strip()
        if raw in {"2", "V2"}:
            return "V2"
        if raw in {"4", "V4"}:
            return "V4"
        raise ValidationError("OData version must be V2 or V4")

    def _service_binding_odata_version(self, text: str, default: str | None = "V4") -> str | None:
        try:
            root = ET.fromstring(text)
        except (ET.ParseError, TypeError):
            lower = (text or "").lower()
            if "odatav2" in lower or "odata\\v2" in lower or 'version="v2"' in lower:
                return "V2"
            if "odatav4" in lower or "odata\\v4" in lower or 'version="v4"' in lower:
                return "V4"
            return self._normalize_odata_version(default) if default else None
        for element in root.iter():
            if self._xml_local_name(element.tag) == "binding":
                attrs = {self._xml_local_name(k): v for k, v in element.attrib.items()}
                if attrs.get("version"):
                    return self._normalize_odata_version(attrs["version"], default=default)
        return self._normalize_odata_version(default) if default else None

    def _service_binding_published(self, text: str) -> bool:
        try:
            root = ET.fromstring(text)
        except (ET.ParseError, TypeError):
            return 'published="true"' in (text or "").lower() or "published='true'" in (text or "").lower()
        for element in root.iter():
            attrs = {self._xml_local_name(k): v for k, v in element.attrib.items()}
            if attrs.get("published", "").lower() == "true":
                return True
        return False
