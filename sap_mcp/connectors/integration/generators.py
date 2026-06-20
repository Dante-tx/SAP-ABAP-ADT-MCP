from __future__ import annotations

import json
from typing import Any

from sap_mcp.connectors.core.base import BaseMixin
from sap_mcp.connectors.core.constants import GENERATOR_ALIASES, GENERATOR_DESCRIPTIONS, GENERATOR_ACCEPT, GENERATOR_CONTENT_TYPE, GENERATOR_CONTENT_ACCEPT
from sap_mcp.errors import SapBackendError


class GeneratorsMixin(BaseMixin):
    def _generator_id(self, generator_id: str) -> str:
        if not generator_id:
            raise ValueError("generator_id is required")
        generator_id = generator_id.strip().lower()
        result = GENERATOR_ALIASES.get(generator_id)
        if result:
            return result
        for key, value in GENERATOR_ALIASES.items():
            if generator_id.replace("-", "") == key.replace("-", "") or generator_id == value:
                return value
            if generator_id == key:
                return value
        raise ValueError(f"Unknown generator: {generator_id}. Supported: {', '.join(sorted(GENERATOR_ALIASES))}")

    async def generators_list_generators(self, destination: str) -> dict[str, Any]:
        self._assert_destination(destination)
        try:
            response = await self._request(
                "GET",
                "/sap/bc/adt/businessservices/generators",
                accept=GENERATOR_ACCEPT,
            )
            generators = json.loads(response.text)
            return {"generators": generators if isinstance(generators, list) else [generators]}
        except SapBackendError:
            return {"generators": [
                {"id": key, **value} for key, value in GENERATOR_DESCRIPTIONS.items()
            ]}

    async def generators_get_schema(self, destination: str, generator_id: str, package_name: str, referenced_object_type: str | None = None, referenced_object_name: str | None = None) -> dict[str, Any]:
        self._assert_destination(destination)
        generator = self._generator_id(generator_id)
        if not package_name:
            raise ValueError("package_name is required")
        params = {"packageName": package_name.upper()}
        if referenced_object_type:
            params["referencedObjectType"] = referenced_object_type.upper()
        if referenced_object_name:
            params["referencedObjectName"] = referenced_object_name.upper()
        try:
            response = await self._request(
                "GET",
                f"/sap/bc/adt/businessservices/generators/{generator}/schema",
                params=params,
                accept=GENERATOR_ACCEPT,
            )
        except SapBackendError as error:
            return {"schema": None, "error": str(error), "details": error.details}
        try:
            schema = json.loads(response.text)
        except json.JSONDecodeError:
            schema = {"raw": response.text}
        return {"schema": schema}

    async def generators_generate_objects(
        self,
        destination: str,
        generator_id: str,
        schema_json: str,
        package_name: str,
        transport_request_number: str | None = None,
        referenced_object_type: str = "",
        referenced_object_name: str = "",
    ) -> dict[str, Any]:
        self._assert_destination(destination)
        generator = self._generator_id(generator_id)
        if not package_name:
            raise ValueError("package_name is required")
        try:
            content = json.loads(schema_json) if isinstance(schema_json, str) else schema_json
        except json.JSONDecodeError as exc:
            raise ValueError("schema_json must be a valid JSON string") from exc
        if not isinstance(content, dict):
            raise ValueError("schema_json must be a JSON object")
        params: dict[str, str] = {"packageName": package_name.upper()}
        if transport_request_number:
            params["corrNr"] = transport_request_number
        if referenced_object_type:
            params["referencedObjectType"] = referenced_object_type.upper()
        if referenced_object_name:
            params["referencedObjectName"] = referenced_object_name.upper()
        try:
            response = await self._request(
                "POST",
                f"/sap/bc/adt/businessservices/generators/{generator}/content",
                params=params,
                content=json.dumps(content).encode("utf-8"),
                headers={"Content-Type": GENERATOR_CONTENT_TYPE},
                accept=GENERATOR_CONTENT_ACCEPT,
            )
        except SapBackendError as error:
            return {"result": None, "error": str(error), "details": error.details}
        try:
            result = json.loads(response.text)
        except json.JSONDecodeError:
            result = {"raw": response.text}
        return {"result": result}
