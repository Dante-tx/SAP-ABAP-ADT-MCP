from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

from sap_mcp.errors import ValidationError

PROGRAM_RUN_PATH = "/sap/bc/adt/programs/programrun"
CLASS_RUN_PATH = "/sap/bc/adt/oo/classrun"

EXECUTION_ACCEPT = "application/xml, application/json, */*"


class ExecutionMixin:
    async def execute(
        self,
        action: str,
        object_name: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = action.strip().lower()
        if normalized not in {"program", "class"}:
            raise ValidationError("action must be one of: program, class")

        obj_name = object_name.strip().upper()
        if not obj_name:
            raise ValidationError("object_name is required")

        if normalized == "program":
            return await self._execute_program(obj_name, parameters)
        if normalized == "class":
            return await self._execute_class(obj_name, parameters)

    async def _execute_program(
        self,
        name: str,
        parameters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        encoded = quote(name, safe="")
        path = f"{PROGRAM_RUN_PATH}/{encoded}"

        body = ""
        if parameters:
            parts = []
            for key, value in parameters.items():
                parts.append(f"{key}={quote(str(value), safe='')}")
            body = "&".join(parts)

        response = await self._request(
            "POST",
            path,
            content=body.encode("utf-8") if body else b"",
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"
                if body else "text/plain; charset=utf-8",
            },
            accept=EXECUTION_ACCEPT,
        )
        return self._parse_execution_response(response.text, name, "program")

    async def _execute_class(
        self,
        name: str,
        parameters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        encoded = quote(name, safe="")
        path = f"{CLASS_RUN_PATH}/{encoded}"

        body = ""
        if parameters:
            parts = []
            for key, value in parameters.items():
                parts.append(f"{key}={quote(str(value), safe='')}")
            body = "&".join(parts)

        response = await self._request(
            "POST",
            path,
            content=body.encode("utf-8") if body else b"",
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"
                if body else "text/plain; charset=utf-8",
            },
            accept=EXECUTION_ACCEPT,
        )
        return self._parse_execution_response(response.text, name, "class")

    @staticmethod
    def _parse_execution_response(text: str, name: str, exec_type: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "action": exec_type,
            "name": name,
            "executed": True,
            "output": text if text else "",
        }
        # Try JSON
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                result["result"] = data
                result["output"] = data.get("output", data.get("message", text))
            return result
        except json.JSONDecodeError:
            pass

        return result
