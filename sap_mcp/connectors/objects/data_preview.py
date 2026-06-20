from __future__ import annotations

import json
from typing import Any

from sap_mcp.errors import ValidationError

CDS_PREVIEW_PATH = "/sap/bc/adt/datapreview/cds"
DDIC_PREVIEW_PATH = "/sap/bc/adt/datapreview/ddic"
FREESTYLE_PREVIEW_PATH = "/sap/bc/adt/datapreview/freestyle"
PREVIEW_ACCEPT = "application/json, application/xml, */*"


class DataPreviewMixin:
    async def data_preview(
        self,
        action: str,
        object_name: str | None = None,
        top: int = 100,
        select_fields: str | None = None,
        filter: str | None = None,
        orderby: str | None = None,
    ) -> dict[str, Any]:
        normalized = action.strip().lower()
        if normalized not in {"cds", "ddic", "freestyle"}:
            raise ValidationError("action must be one of: cds, ddic, freestyle")

        if normalized in {"cds", "ddic"}:
            if not object_name:
                raise ValidationError("object_name is required for cds/ddic actions")
            obj_name = object_name.strip().upper()

        if normalized == "cds":
            return await self._preview(obj_name, top, select_fields, filter, orderby, CDS_PREVIEW_PATH, "ddlSourceName")
        if normalized == "ddic":
            return await self._preview(obj_name, top, select_fields, filter, orderby, DDIC_PREVIEW_PATH, "ddicEntityName")
        if normalized == "freestyle":
            return await self._preview(object_name or "", top, select_fields, filter, orderby, FREESTYLE_PREVIEW_PATH, "sql")

    async def _preview(
        self,
        name: str,
        top: int,
        select_fields: str | None,
        filter: str | None,
        orderby: str | None,
        path: str,
        param_name: str,
    ) -> dict[str, Any]:
        params = self._build_preview_params(name, top, select_fields, filter, orderby, param_name)
        preview_type = "cds" if "cds" in path else ("ddic" if "ddic" in path else "freestyle")
        content = None
        headers = None
        if preview_type == "freestyle":
            params.pop(param_name, None)
            content = name.encode("utf-8")
            headers = {"Content-Type": "text/plain; charset=utf-8"}
        response = await self._request("POST", path, params=params, content=content, headers=headers, accept=PREVIEW_ACCEPT)
        return self._parse_preview_response(response.text, name, preview_type)

    @staticmethod
    def _build_preview_params(
        entity: str,
        top: int,
        select_fields: str | None,
        filter: str | None,
        orderby: str | None,
        param_name: str,
    ) -> dict[str, str]:
        params: dict[str, str] = {
            param_name: entity,
            "top": str(max(1, min(top, 1000))),
            "$format": "json",
        }
        if select_fields:
            params["$select"] = select_fields
        if filter:
            params["$filter"] = filter
        if orderby:
            params["$orderby"] = orderby
        return params

    def _parse_preview_response(
        self,
        text: str,
        name: str,
        preview_type: str,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "preview_type": preview_type,
            "name": name,
            "rows": [],
            "count": 0,
        }
        if not text.strip():
            return result

        # Try JSON first (OData-style response)
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                results = data.get("d", {}).get("results", data.get("value", []))
                if isinstance(results, list):
                    result["rows"] = results
                    result["count"] = len(results)
                else:
                    result["rows"] = [data]
                    result["count"] = 1
            elif isinstance(data, list):
                result["rows"] = data
                result["count"] = len(data)
            return result
        except json.JSONDecodeError:
            pass

        # Try SAP ADT dataPreview XML format
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(text)
            dp_ns = "http://www.sap.com/adt/dataPreview"

            def _dp_attr(elem, name):
                """Get attribute by local name, handling namespace prefix."""
                full = f"{{{dp_ns}}}{name}"
                val = elem.attrib.get(full)
                if val is not None:
                    return val
                # try prefixed form
                for k, v in elem.attrib.items():
                    if k.endswith(f"}}:{name}") or k == name:
                        return v
                return ""

            columns = root.findall(f".//{{{dp_ns}}}columns")
            if columns:
                col_names = []
                col_values = []
                for col in columns:
                    metas = col.findall(f".//{{{dp_ns}}}metadata")
                    if metas:
                        col_names.append(_dp_attr(metas[0], "name"))
                    vals = []
                    dataset = col.find(f"{{{dp_ns}}}dataSet")
                    if dataset is not None:
                        for data_el in dataset.findall(f"{{{dp_ns}}}data"):
                            vals.append(data_el.text or "")
                    col_values.append(vals)
                if col_names:
                    max_rows = max((len(v) for v in col_values), default=0)
                    rows = []
                    for i in range(max_rows):
                        row = {}
                        for j, name in enumerate(col_names):
                            row[name] = col_values[j][i] if i < len(col_values[j]) else ""
                        rows.append(row)
                    result["rows"] = rows
                    result["count"] = len(rows)
                    total_el = root.find(f"{{{dp_ns}}}totalRows")
                    if total_el is not None and total_el.text:
                        result["total_rows"] = int(total_el.text)
                    return result
        except ET.ParseError:
            pass

        # Try Atom/XML response (legacy)
        try:
            root = ET.fromstring(text)
            ns = {"atom": "http://www.w3.org/2005/Atom",
                  "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
                  "d": "http://schemas.microsoft.com/ado/2007/08/dataservices"}
            entries = root.findall(".//atom:entry", ns)
            if entries:
                rows = []
                for entry in entries:
                    props = entry.find(".//m:properties", ns)
                    if props is None:
                        props = entry.find(".//atom:content/m:properties", ns)
                    if props is not None:
                        row = {}
                        for child in list(props):
                            tag = child.tag.split("}", 1)[-1] if "}" in child.tag else child.tag
                            row[tag] = child.text or ""
                        rows.append(row)
                if rows:
                    result["rows"] = rows
                    result["count"] = len(rows)
                    return result
        except ET.ParseError:
            pass

        result["raw"] = text
        return result
