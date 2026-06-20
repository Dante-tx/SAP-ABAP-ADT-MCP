from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from sap_mcp.connectors.core.registry import ADT_BASE_PATH, ADT_PATH_REGISTRATIONS
from sap_mcp.errors import AuthorizationError, ValidationError


class AdtActivationMixin:
    async def activate_object(self, object_type: str, name: str, reason: str) -> dict[str, Any]:
        result = await self.activate_objects([{"type": object_type, "name": name}], reason)
        obj_results = result.get("object_results", [])
        my_result = obj_results[0] if obj_results else {}
        return {
            "activated": result.get("activated", True),
            "object_type": object_type, "name": name.upper(),
            "status_code": result["status_code"],
            "activation_state": my_result.get("state"),
            "activation_state_text": my_result.get("state_text"),
            "messages": my_result.get("messages", []),
        }

    async def activate_objects(self, objects: list[dict[str, str]], reason: str) -> dict[str, Any]:
        if not self.config.allow_activate:
            raise AuthorizationError("ABAP activation is disabled by configuration")
        if not reason.strip():
            raise ValidationError("Activation reason is required")
        references = []
        for item in objects or []:
            object_type = (item.get("type") or item.get("object_type") or "").strip()
            name = (item.get("name") or "").strip()
            if not object_type or not name:
                raise ValidationError("Each object must contain name and type/object_type")
            uri = self._object_path(object_type, name)
            await self._assert_object_write_allowed(object_type, name)
            references.append({"object_type": object_type.upper(), "name": name.upper(), "uri": uri})
        if not references:
            raise ValidationError("At least one object is required")
        body = self._object_references_xml(references)
        response = await self._request(
            "POST", f"{ADT_BASE_PATH}/activation", params={"method": "activate"},
            content=body.encode("utf-8"), headers={"Content-Type": "application/xml"},
        )
        object_results, all_activated = self._parse_activation_result(response.text, references)
        return {
            "activated": all_activated, "count": len(references), "objects": references,
            "object_results": object_results,
            "messages": [m for r in object_results for m in r["messages"]],
            "status_code": response.status_code,
        }

    async def activate_uris(self, uris: list[str], reason: str) -> dict[str, Any]:
        objects = []
        for uri in uris:
            ref = self._object_ref_from_any_uri(uri)
            objects.append({"type": ref["type"], "name": ref["name"]})
        return await self.activate_objects(objects, reason)

    def _parse_activation_result(self, xml_text: str, references: list[dict[str, str]]) -> tuple[list[dict[str, Any]], bool]:
        try:
            root = ET.fromstring(xml_text)
        except (ET.ParseError, TypeError):
            return self._activation_fallback_results(references, "Could not parse activation result")
        messages = [
            self._activation_message(element)
            for element in root.iter()
            if self._xml_local_name(element.tag) in {"msg", "message"}
        ]
        messages = [m for m in messages if m]
        error_types = {"A", "E", "X", "ERROR"}
        has_errors = any(
            (m.get("type") or m.get("severity") or "").upper() in error_types for m in messages)
        has_failed_state = any(
            (e.attrib.get("state") or self._activation_attr(e, "state")).upper() in error_types
            for e in root.iter())
        activation_executed = not any(
            self._xml_local_name(e.tag) == "properties"
            and (e.attrib.get("activationExecuted") or "").lower() == "false"
            for e in root.iter())
        all_activated = activation_executed and not has_errors and not has_failed_state
        state = "S" if all_activated else "E"
        state_text = "Activated" if all_activated else "Activation failed"
        object_results = []
        for ref in references:
            related = [
                m for m in messages
                if len(references) == 1 or ref["uri"] in (m.get("href") or "") or ref["name"] in (m.get("objDescr") or "").upper()
            ]
            object_results.append({
                "object_type": ref["object_type"], "name": ref["name"],
                "state": state, "state_text": state_text,
                "activated": all_activated and not any(
                    (m.get("type") or "").upper() in error_types for m in related),
                "messages": related,
            })
        return object_results, all(r["activated"] for r in object_results)

    def _activation_fallback_results(self, references: list[dict[str, str]], state_text: str) -> tuple[list[dict[str, Any]], bool]:
        return [
            {"object_type": r["object_type"], "name": r["name"],
             "state": "UNKNOWN", "state_text": state_text, "activated": False, "messages": []}
            for r in references
        ], False

    def _activation_message(self, element: ET.Element) -> dict[str, str]:
        message = {self._xml_local_name(key): value for key, value in element.attrib.items()}
        text_parts = []
        if element.text and element.text.strip():
            text_parts.append(element.text.strip())
        for child in element.iter():
            if child is not element and child.text and child.text.strip():
                text_parts.append(child.text.strip())
        if text_parts:
            message["text"] = " ".join(text_parts)
        hint = self._activation_message_hint(message.get("text", ""))
        if hint:
            message["hint"] = hint
        return message

    def _activation_attr(self, element: ET.Element, name: str) -> str:
        return next((v for k, v in element.attrib.items() if self._xml_local_name(k) == name), "")

    def _activation_message_hint(self, text: str) -> str | None:
        normalized = text.casefold()
        if "reported was already declared" in normalized or "failed was already declared" in normalized:
            return "In RAP handler methods, REPORTED and FAILED are framework context identifiers; do not redeclare them as local DATA variables."
        if "statement before modify" in normalized and "period missing" in normalized:
            return "The parser may report a missing period for unsupported strict-mode EML syntax. Check the MODIFY statement shape before only adding punctuation."
        if "field @lt_items is unknown" in normalized or "field @lt_" in normalized:
            return "In EML UPDATE/MODIFY payload clauses, host-variable @ prefixes are often not used the same way as ABAP SQL."
        return None
