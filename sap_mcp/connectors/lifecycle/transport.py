from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

from sap_mcp.connectors.core.base import BaseMixin
from sap_mcp.connectors.core.registry import ADT_BASE_PATH
from sap_mcp.errors import SapBackendError


class TransportsMixin(BaseMixin):
    async def transport_get(self, destination: str, development_package: str, object_name: str, object_type: str, is_creation: bool) -> dict[str, Any]:
        self._assert_destination(destination)
        registration = self._find_path_registration(object_type)
        search_type = registration.search_type if registration else object_type
        params = {
            "DEVCLASS": development_package.upper(),
            "OPERATION": "S" if is_creation else "W",
            "OBJECTNAME": object_name.upper(),
            "OBJECTTYPE": search_type.upper(),
            "IGNORE_ACTIVATION": "false",
        }
        try:
            response = await self._request(
                "GET",
                f"{ADT_BASE_PATH}/cts/transportcheck",
                params=params,
                accept="application/vnd.sap.as+xml, application/xml, */*",
            )
        except SapBackendError:
            return {"transportRequests": [], "informationMessages": [{"type": "Info", "text": "Transport check failed; recording may be required"}], "isRecordingRequired": True}

        records = self._parse_asx_data(response.text)
        transport_requests = []
        info_messages = []
        if records:
            transport_requests = [{"number": records.get("TRANSPORTREQUESTNUMBER", ""), "text": records.get("REQUEST_TEXT", ""), "target": records.get("TARGET", ""), "owner": records.get("AUTHOR", "")}] if records.get("TRANSPORTREQUESTNUMBER") else []
            short_text = records.get("SHORT_TEXT", "")
            if short_text:
                info_messages.append({"type": records.get("SEVERITY", "INFO"), "text": short_text})
        is_recording = not transport_requests or any(
            m.get("text", "").strip().upper().startswith("RECORDING") for m in info_messages
        )
        return {"transportRequests": transport_requests, "informationMessages": info_messages, "isRecordingRequired": is_recording}

    async def transport_create(self, destination: str, development_package: str, owner: str, description: str) -> dict[str, Any]:
        self._assert_destination(destination)
        xml_body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<abapXml><asx:abap xmlns:asx="http://www.sap.com/abapxml" version="1.0">'
            "<asx:values>"
            f"<DEVC>{self._xml_escape(development_package.upper())}</DEVC>"
            f"<AS4USER>{self._xml_escape(owner.upper())}</AS4USER>"
            f"<AS4TEXT>{self._xml_escape(description)}</AS4TEXT>"
            "<CATEGORY>customizing</CATEGORY>"
            "<RELEASE_FIX>F</RELEASE_FIX>"
            "</asx:values></asx:abap></abapXml>"
        )
        try:
            response = await self._request(
                "POST",
                f"{ADT_BASE_PATH}/cts/transportrequests",
                content=xml_body.encode("utf-8"),
                headers={"Content-Type": "application/vnd.sap.adt.cts.transportrequests.v3+xml; charset=utf-8"},
                accept="application/vnd.sap.adt.cts.transportrequests.v3+xml, application/xml, */*",
            )
        except SapBackendError as error:
            details = error.details
            return {"transportRequestNumber": "", "number": "", "message": "Failed to create transport request", "error": str(error), "details": details}
        root = ET.fromstring(response.text)
        request_number = ""
        for element in root.iter():
            tag = element.tag.rsplit("}", 1)[-1]
            if tag == "entry":
                request_number = element.attrib.get("title", element.attrib.get("name", ""))
                break
        return {
            "transportRequestNumber": request_number,
            "number": request_number,
            "message": f"Transport request {request_number} created",
            "status_code": response.status_code,
        }

    async def transport_list_tasks(self, transport_request_number: str) -> dict[str, Any]:
        """List tasks under a transport request.

        ADT: GET /sap/bc/adt/cts/transportrequests/{tr_number}/tasks
        """
        tr_number = transport_request_number.strip().upper()
        response = await self._request(
            "GET",
            f"{ADT_BASE_PATH}/cts/transportrequests/{quote(tr_number)}/tasks",
            accept="application/atom+xml, application/xml, */*",
        )
        tasks = self._parse_transport_collection(response.text, "task")
        return {
            "transportRequestNumber": tr_number,
            "tasks": tasks,
            "count": len(tasks),
            "status_code": response.status_code,
        }

    async def transport_list_objects(self, transport_request_number: str) -> dict[str, Any]:
        """List objects in a transport request.

        ADT: GET /sap/bc/adt/cts/transportrequests/{tr_number}/items
        """
        tr_number = transport_request_number.strip().upper()
        response = await self._request(
            "GET",
            f"{ADT_BASE_PATH}/cts/transportrequests/{quote(tr_number)}/items",
            accept="application/atom+xml, application/xml, */*",
        )
        items = self._parse_transport_collection(response.text, "item")
        return {
            "transportRequestNumber": tr_number,
            "items": items,
            "count": len(items),
            "status_code": response.status_code,
        }

    async def transport_release(self, transport_request_number: str) -> dict[str, Any]:
        """Release a transport request.

        ADT: POST /sap/bc/adt/cts/transportrequests/{tr_number}?action=release
        """
        tr_number = transport_request_number.strip().upper()
        response = await self._request(
            "POST",
            f"{ADT_BASE_PATH}/cts/transportrequests/{quote(tr_number)}",
            params={"action": "release"},
            accept="application/xml, */*",
        )
        return {
            "transportRequestNumber": tr_number,
            "released": response.status_code < 400,
            "message": f"Transport request {tr_number} released",
            "status_code": response.status_code,
        }

    def _parse_transport_collection(self, text: str, entry_kind: str) -> list[dict[str, Any]]:
        """Parse Atom feed for transport tasks or items."""
        if not text.strip():
            return []
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return [{"raw": text.strip()}]
        entries = []
        for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
            item = {}
            title = entry.find("{http://www.w3.org/2005/Atom}title")
            if title is not None and title.text:
                item["title"] = title.text.strip()
            for child in entry:
                tag = child.tag.rsplit("}", 1)[-1]
                if tag == "category":
                    item.setdefault("category", child.attrib.get("term", ""))
                elif tag == "link":
                    item.setdefault("uri", child.attrib.get("href", ""))
                    item.setdefault("type", child.attrib.get("type", ""))
                elif child.text and child.text.strip():
                    item[tag] = child.text.strip()
            if item:
                item["kind"] = entry_kind
                entries.append(item)
        return entries
