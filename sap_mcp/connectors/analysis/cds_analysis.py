from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

from sap_mcp.errors import ValidationError

DDL_DEPENDENCIES_PATH = "/sap/bc/adt/ddic/ddl/dependencies/graphdata"
DDL_RELATED_OBJECTS_PATH = "/sap/bc/adt/ddic/ddl/relatedObjects"
DDL_ACTIVE_OBJECT_PATH = "/sap/bc/adt/ddic/ddl/activeobject"
DDL_CREATE_SQL_PATH = "/sap/bc/adt/ddic/ddl/createstatements"
OBJECT_RELATIONS_PATH = "/sap/bc/adt/objectrelations"

ANALYSIS_ACCEPT = "application/xml, application/json, */*"


class CdsAnalysisMixin:
    async def cds_analysis(
        self,
        action: str,
        object_type: str = "DDLS",
        object_name: str | None = None,
        relation_type: str = "network",
    ) -> dict[str, Any]:
        normalized = action.strip().lower()
        if normalized not in {"dependencies", "related_objects", "active_object", "create_sql", "object_relations"}:
            raise ValidationError(
                "action must be one of: dependencies, related_objects, active_object, create_sql, object_relations"
            )

        obj_name = object_name.strip().upper() if object_name else ""
        obj_type = object_type.strip().upper()

        if normalized == "dependencies":
            return await self._cds_dependencies(obj_name)
        if normalized == "related_objects":
            return await self._cds_related_objects(obj_name)
        if normalized == "active_object":
            return await self._cds_active_object(obj_name)
        if normalized == "create_sql":
            return await self._cds_create_sql(obj_name)
        if normalized == "object_relations":
            return await self._object_relations(obj_type, obj_name, relation_type)

    async def _cds_dependencies(self, name: str) -> dict[str, Any]:
        if not name:
            raise ValidationError("object_name is required for dependencies action")
        encoded = quote(name, safe="/")
        response = await self._request(
            "GET",
            f"{DDL_DEPENDENCIES_PATH}?name={encoded}",
            accept=ANALYSIS_ACCEPT,
        )
        return self._parse_graph_response(response.text, "dependencies", name)

    async def _cds_related_objects(self, name: str) -> dict[str, Any]:
        if not name:
            raise ValidationError("object_name is required for related_objects action")
        encoded = quote(name, safe="/")
        response = await self._request(
            "GET",
            f"{DDL_RELATED_OBJECTS_PATH}?name={encoded}",
            accept=ANALYSIS_ACCEPT,
        )
        return self._parse_related_response(response.text, name)

    async def _cds_active_object(self, name: str) -> dict[str, Any]:
        if not name:
            raise ValidationError("object_name is required for active_object action")
        encoded = quote(name, safe="/")
        response = await self._request(
            "GET",
            f"{DDL_ACTIVE_OBJECT_PATH}?name={encoded}",
            accept=ANALYSIS_ACCEPT,
        )
        return self._parse_active_object_response(response.text, name)

    async def _cds_create_sql(self, name: str) -> dict[str, Any]:
        if not name:
            raise ValidationError("object_name is required for create_sql action")
        response = await self._request(
            "POST",
            DDL_CREATE_SQL_PATH,
            params={"object_name": name},
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
            accept="text/plain, application/xml, */*",
        )
        return {
            "action": "create_sql",
            "name": name,
            "sql": response.text.strip() if response.text else "",
            "content_type": response.content_type,
        }

    async def _object_relations(
        self, object_type: str, name: str, relation_type: str
    ) -> dict[str, Any]:
        if not name:
            raise ValidationError("object_name is required for object_relations action")
        encoded_name = quote(name, safe="/")
        encoded_type = quote(object_type, safe="/")
        normalized_relation = relation_type.strip().lower()

        if normalized_relation == "components":
            path = f"{OBJECT_RELATIONS_PATH}/{encoded_type}/{encoded_name}/components"
        else:
            path = f"{OBJECT_RELATIONS_PATH}/{encoded_type}/{encoded_name}/network"

        response = await self._request(
            "GET",
            path,
            accept=ANALYSIS_ACCEPT,
        )
        return self._parse_graph_response(response.text, "object_relations", name)

    def _parse_graph_response(self, text: str, action: str, name: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "action": action,
            "name": name,
            "nodes": [],
            "edges": [],
        }
        if not text.strip():
            return result

        # Try JSON
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                result["nodes"] = data.get("nodes", data.get("vertices", []))
                result["edges"] = data.get("edges", data.get("links", []))
            elif isinstance(data, list):
                result["nodes"] = data
            return result
        except json.JSONDecodeError:
            pass

        # Try XML
        try:
            root = ET.fromstring(text)
            nodes = []
            edges = []
            for vertex in root.iter("vertex"):
                node = dict(vertex.attrib)
                if node:
                    nodes.append(node)
            for edge in root.iter("edge"):
                e = dict(edge.attrib)
                if e:
                    edges.append(e)
            if nodes:
                result["nodes"] = nodes
                result["edges"] = edges
                return result
        except ET.ParseError:
            pass

        result["raw"] = text
        return result

    def _parse_related_response(self, text: str, name: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "action": "related_objects",
            "name": name,
            "related_objects": [],
        }
        if not text.strip():
            return result

        try:
            root = ET.fromstring(text)
            objects = []
            for obj in root.iter("relatedObject"):
                entry = dict(obj.attrib)
                if entry:
                    objects.append(entry)
            if objects:
                result["related_objects"] = objects
                return result

            # Try simple list
            for entry in root.iter():
                tag = entry.tag.split("}", 1)[-1] if "}" in entry.tag else entry.tag
                if tag in {"ddicObject", "object", "item"}:
                    d = dict(entry.attrib)
                    if d:
                        objects.append(d)
            if objects:
                result["related_objects"] = objects
                return result
        except ET.ParseError:
            pass

        # Try JSON
        try:
            data = json.loads(text)
            if isinstance(data, list):
                result["related_objects"] = data
            elif isinstance(data, dict):
                items = data.get("objects", data.get("relatedObjects", data.get("results", [])))
                result["related_objects"] = items if isinstance(items, list) else [items]
            return result
        except json.JSONDecodeError:
            pass

        result["raw"] = text
        return result

    def _parse_active_object_response(self, text: str, name: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "action": "active_object",
            "name": name,
            "active_name": name,
            "source": None,
        }
        if not text.strip():
            return result

        try:
            root = ET.fromstring(text)
            # Look for the resolved active object name
            for elem in root.iter():
                tag = elem.tag.split("}", 1)[-1] if "}" in elem.tag else elem.tag
                if tag in {"activeObject", "ddlSource", "source"}:
                    active_name = elem.attrib.get("name") or elem.attrib.get("adtcore:name", "")
                    if active_name:
                        result["active_name"] = active_name
                    source = elem.text
                    if source:
                        result["source"] = source.strip()
                    return result

            # If the response is plain text source
            if root.tag and not root.attrib:
                result["source"] = text.strip()
                return result
        except ET.ParseError:
            pass

        # Plain text source fallback
        if text.strip().upper().startswith(("DEFINE", "SELECT", "@")):
            result["source"] = text.strip()
            return result

        result["raw"] = text
        return result
