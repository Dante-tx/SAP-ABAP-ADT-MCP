from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

from sap_mcp.errors import ValidationError

# Element info endpoints by object type
ELEMENT_INFO_PATHS = {
    "DDLS": "/sap/bc/adt/ddic/ddl/sources/{name}/elementinfo",
    "SRVD": "/sap/bc/adt/ddic/srvd/sources/{name}/elementinfo",
    "CLAS": "/sap/bc/adt/oo/classes/{name}/elementinfo",
    "INTF": "/sap/bc/adt/oo/interfaces/{name}/elementinfo",
    "PROG": "/sap/bc/adt/programs/programs/{name}/elementinfo",
}

# Pretty printer endpoints by object type
PRETTY_PRINTER_PATHS = {
    "DDLS": "/sap/bc/adt/ddic/ddl/sources/{name}/prettyprinter",
    "SRVD": "/sap/bc/adt/ddic/srvd/sources/{name}/prettyprinter",
    "CLAS": "/sap/bc/adt/oo/classes/{name}/prettyprinter",
    "INTF": "/sap/bc/adt/oo/interfaces/{name}/prettyprinter",
    "PROG": "/sap/bc/adt/programs/programs/{name}/prettyprinter",
}

DEFAULT_PRETTY_PRINTER_PATH = "/sap/bc/adt/abapprettyprint"

ASSIST_ACCEPT = "application/xml, application/json, */*"


class CodeAssistMixin:
    async def code_assist(
        self,
        action: str,
        object_type: str,
        object_name: str | None = None,
        source: str | None = None,
        position: str | None = None,
    ) -> dict[str, Any]:
        normalized = action.strip().lower()
        if normalized not in {"element_info", "format"}:
            raise ValidationError("action must be one of: element_info, format")

        obj_type = object_type.strip().upper()
        obj_name = object_name.strip().upper() if object_name else ""

        if normalized == "element_info":
            return await self._element_info(obj_type, obj_name, source, position)
        if normalized == "format":
            return await self._format_source(obj_type, obj_name, source)

    async def _element_info(
        self,
        object_type: str,
        name: str,
        source: str | None,
        position: str | None,
    ) -> dict[str, Any]:
        if not source:
            raise ValidationError("source is required for element_info action")
        if not position:
            raise ValidationError("position is required for element_info action (format: line:col)")

        path_template = ELEMENT_INFO_PATHS.get(object_type)
        if not path_template:
            raise ValidationError(
                f"element_info not supported for object_type={object_type}. "
                f"Supported: {', '.join(sorted(ELEMENT_INFO_PATHS))}"
            )

        encoded_name = quote(name, safe="")
        path = path_template.replace("{name}", encoded_name)

        parts = position.strip().split(":")
        line = 0
        col = 0
        if len(parts) >= 2:
            try:
                line = int(parts[0])
                col = int(parts[1])
            except ValueError:
                raise ValidationError("position must be in format 'line:col' (e.g., '10:5')")

        body = source
        try:
            response = await self._request(
                "POST",
                path,
                content=body.encode("utf-8"),
                headers={
                    "Content-Type": "text/plain; charset=utf-8",
                    "X-ADT-Position-Line": str(line),
                    "X-ADT-Position-Column": str(col),
                },
                accept=ASSIST_ACCEPT,
            )
            return self._parse_element_info_response(response.text, name, position, object_type)
        except Exception as e:
            return {
                "action": "element_info",
                "name": name,
                "object_type": object_type,
                "position": position,
                "info": None,
                "error": str(e),
            }

    async def _format_source(
        self,
        object_type: str,
        name: str,
        source: str | None,
    ) -> dict[str, Any]:
        src = source
        path_template = PRETTY_PRINTER_PATHS.get(object_type)

        if path_template and name:
            encoded_name = quote(name, safe="")
            path = path_template.replace("{name}", encoded_name)
        else:
            path = DEFAULT_PRETTY_PRINTER_PATH

        if not source:
            raise ValidationError("source is required for format action")

        try:
            response = await self._request(
                "POST",
                path,
                content=src.encode("utf-8"),
                headers={
                    "Content-Type": "text/plain; charset=utf-8",
                },
                accept="text/plain, application/xml, */*",
            )
            formatted = response.text
            normalized = formatted.replace("\r\n", "\n") if formatted else src
            mode = "adt_prettyprinter"
            error = None
        except Exception as exc:
            normalized = src.replace("\r\n", "\n")
            mode = "local_fallback"
            error = str(exc)

        return {
            "action": "format",
            "object_type": object_type,
            "name": name or "(inline source)",
            "formatted_source": normalized,
            "changed": normalized.strip() != src.replace("\r\n", "\n").strip(),
            "mode": mode,
            "error": error,
        }

    @staticmethod
    def _parse_element_info_response(
        text: str, name: str, position: str, object_type: str
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "action": "element_info",
            "name": name,
            "object_type": object_type,
            "position": position,
            "info": None,
        }
        if not text.strip():
            return result

        # Try JSON
        try:
            data = json.loads(text)
            result["info"] = data
            return result
        except json.JSONDecodeError:
            pass

        # Try XML
        try:
            root = ET.fromstring(text)
            info: dict[str, Any] = {}

            # Try to extract element details from Atom/XML
            for elem in root.iter():
                tag = elem.tag.split("}", 1)[-1] if "}" in elem.tag else elem.tag
                if tag in {"longText", "quickInfo", "description"}:
                    info[tag] = elem.text or ""
                for attr_name, attr_value in elem.attrib.items():
                    simple_name = attr_name.split("}", 1)[-1] if "}" in attr_name else attr_name
                    if attr_value and simple_name not in info:
                        info[simple_name] = attr_value

            if info:
                result["info"] = info
                return result
        except ET.ParseError:
            pass

        result["raw"] = text
        return result
