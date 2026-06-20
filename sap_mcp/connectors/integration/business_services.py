from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

from sap_mcp.connectors.core.base import BaseMixin


SRVB_NS = "http://www.sap.com/adt/ddic/ServiceBindings"
ADT_NS = "http://www.sap.com/adt/core"


class BusinessServicesMixin(BaseMixin):
    async def business_services_fetch_services(self, destination: str, service_binding_name: str) -> dict[str, Any]:
        self._assert_destination(destination)
        binding = service_binding_name.strip()
        if not binding:
            raise ValueError("service_binding_name is required")
        encoded = quote(binding, safe="")
        response = await self._request(
            "GET",
            f"/sap/bc/adt/businessservices/bindings/{encoded}",
            accept="application/vnd.sap.adt.businessservices.v2+xml, application/xml, */*",
        )
        return self._parse_srvb_response(response.text, binding)

    async def business_services_fetch_service_information(
        self,
        destination: str,
        service_binding_name: str,
        service_name: str | None = None,
        service_definition: str | None = None,
        service_version: str | None = None,
        odata_info_uri: str | None = None,
        odata_version: str | None = None,
        is_published: bool | None = None,
    ) -> dict[str, Any]:
        self._assert_destination(destination)
        binding = service_binding_name.strip()
        if not binding:
            raise ValueError("service_binding_name is required")
        encoded = quote(binding, safe="")
        response = await self._request(
            "GET",
            f"/sap/bc/adt/businessservices/bindings/{encoded}",
            accept="application/vnd.sap.adt.businessservices.v2+xml, application/xml, */*",
        )
        return self._parse_srvb_response(response.text, binding)

    def _parse_srvb_response(self, xml_text: str, binding_name: str) -> dict[str, Any]:
        """Parse SRVB XML response into structured data."""
        if not xml_text.strip():
            return {"service_binding": binding_name, "services": [], "count": 0}

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return {"service_binding": binding_name, "services": [], "count": 0,
                    "error": "Failed to parse XML response"}

        tag = root.tag.rsplit("}", 1)[-1]
        if tag != "serviceBinding":
            return {"service_binding": binding_name, "services": [], "count": 0,
                    "error": f"Unexpected root element: {tag}"}

        attrs = {k.rsplit("}", 1)[-1]: v for k, v in root.attrib.items()}
        result: dict[str, Any] = {
            "service_binding": attrs.get("name", binding_name),
            "description": attrs.get("description"),
            "type": attrs.get("type"),
            "version": attrs.get("version", "active"),
            "abap_language_version": attrs.get("abapLanguageVersion"),
            "published": attrs.get("published"),
            "allowed_action": attrs.get("allowedAction"),
            "services": [],
            "binding_type": None,
            "binding_version": None,
            "count": 0,
        }

        # Parse <srvb:services>
        srvb_services = root.find(f"{{{SRVB_NS}}}services")
        if srvb_services is not None:
            srvb_name = srvb_services.attrib.get(f"{{{SRVB_NS}}}name", binding_name)
            for content_elem in srvb_services.findall(f"{{{SRVB_NS}}}content"):
                version = content_elem.attrib.get(f"{{{SRVB_NS}}}version", "")
                minor = content_elem.attrib.get(f"{{{SRVB_NS}}}minorVersion", "")
                sd = content_elem.find(f"{{{SRVB_NS}}}serviceDefinition")
                service_def_name = sd.attrib.get(f"{{{ADT_NS}}}name") if sd is not None else None
                service_def_uri = sd.attrib.get(f"{{{ADT_NS}}}uri") if sd is not None else None
                result["services"].append({
                    "name": srvb_name,
                    "version": version,
                    "minor_version": minor,
                    "service_definition": service_def_name,
                    "service_definition_uri": service_def_uri,
                })

        # Parse <srvb:binding>
        srvb_binding = root.find(f"{{{SRVB_NS}}}binding")
        if srvb_binding is not None:
            result["binding_type"] = srvb_binding.attrib.get(f"{{{SRVB_NS}}}type")
            result["binding_version"] = srvb_binding.attrib.get(f"{{{SRVB_NS}}}version")

        result["count"] = len(result["services"])
        return result
