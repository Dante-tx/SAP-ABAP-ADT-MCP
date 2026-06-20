from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any

from sap_mcp.errors import ValidationError

SYSTEM_INFO_PATH = "/sap/bc/adt/system/information"
SYSTEM_COMPONENTS_PATH = "/sap/bc/adt/system/components"
SYSTEM_USERS_PATH = "/sap/bc/adt/system/users"

SYSTEM_ACCEPT = "application/xml, application/json, */*"


class SystemInfoMixin:
    async def system_info(
        self,
        action: str,
    ) -> dict[str, Any]:
        normalized = action.strip().lower()
        if normalized not in {"system", "components", "users"}:
            raise ValidationError("action must be one of: system, components, users")

        if normalized == "system":
            return await self._get_system_info()
        if normalized == "components":
            return await self._get_components()
        if normalized == "users":
            return await self._get_users()

    async def _get_system_info(self) -> dict[str, Any]:
        response = await self._request(
            "GET",
            SYSTEM_INFO_PATH,
            accept=SYSTEM_ACCEPT,
        )
        return self._parse_system_info_xml(response.text)

    async def _get_components(self) -> dict[str, Any]:
        response = await self._request(
            "GET",
            SYSTEM_COMPONENTS_PATH,
            accept=SYSTEM_ACCEPT,
        )
        return self._parse_components_xml(response.text)

    async def _get_users(self) -> dict[str, Any]:
        response = await self._request(
            "GET",
            SYSTEM_USERS_PATH,
            accept=SYSTEM_ACCEPT,
        )
        return self._parse_users_response(response.text)

    @staticmethod
    def _parse_system_info_xml(text: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "action": "system",
        }
        if not text.strip():
            result["raw"] = text
            return result

        try:
            root = ET.fromstring(text)
            for elem in root.iter():
                tag = elem.tag.split("}", 1)[-1] if "}" in elem.tag else elem.tag
                if elem.text and elem.text.strip():
                    result[tag] = elem.text.strip()
                for attr_name, attr_value in elem.attrib.items():
                    simple_name = attr_name.split("}", 1)[-1] if "}" in attr_name else attr_name
                    if attr_value and simple_name not in result:
                        result[simple_name] = attr_value
            return result
        except ET.ParseError:
            # Try JSON
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    result.update(data)
                return result
            except json.JSONDecodeError:
                result["raw"] = text
                return result

    @staticmethod
    def _parse_components_xml(text: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "action": "components",
            "components": [],
        }
        if not text.strip():
            return result

        try:
            root = ET.fromstring(text)
            for comp in root.iter():
                tag = comp.tag.split("}", 1)[-1] if "}" in comp.tag else comp.tag
                if tag in {"component", "softwareComponent", "item"}:
                    entry = dict()
                    for attr_name, attr_value in comp.attrib.items():
                        simple_name = attr_name.split("}", 1)[-1] if "}" in attr_name else attr_name
                        entry[simple_name] = attr_value
                    if comp.text and comp.text.strip():
                        entry["description"] = comp.text.strip()
                    if entry:
                        result["components"].append(entry)
            return result
        except ET.ParseError:
            try:
                data = json.loads(text)
                if isinstance(data, list):
                    result["components"] = data
                elif isinstance(data, dict):
                    items = data.get("components", data.get("results", []))
                    result["components"] = items if isinstance(items, list) else [items]
                return result
            except json.JSONDecodeError:
                result["raw"] = text
                return result

    @staticmethod
    def _parse_users_response(text: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "action": "users",
            "users": [],
        }
        if not text.strip():
            return result

        try:
            root = ET.fromstring(text)
            for user_elem in root.iter():
                tag = user_elem.tag.split("}", 1)[-1] if "}" in user_elem.tag else user_elem.tag
                if tag in {"user", "abapUser", "item"}:
                    entry = dict()
                    for attr_name, attr_value in user_elem.attrib.items():
                        simple_name = attr_name.split("}", 1)[-1] if "}" in attr_name else attr_name
                        entry[simple_name] = attr_value
                    if entry:
                        result["users"].append(entry)
            return result
        except ET.ParseError:
            try:
                data = json.loads(text)
                if isinstance(data, list):
                    result["users"] = data
                elif isinstance(data, dict):
                    items = data.get("users", data.get("results", []))
                    result["users"] = items if isinstance(items, list) else [items]
                return result
            except json.JSONDecodeError:
                result["raw"] = text
                return result
