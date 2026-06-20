from __future__ import annotations

from html import escape
from urllib.parse import quote

from sap_mcp.connectors.core.registry import ADT_BASE_PATH, DEFAULT_ABAP_LANGUAGE_VERSION


class AdtXmlMixin:
    def _clean_xml_name(self, name: str) -> str:
        return name.rsplit("}", 1)[-1] if "}" in name else name.split(":", 1)[-1]

    _xml_local_name = _clean_xml_name

    def _xml_escape(self, value: str) -> str:
        return escape(value, quote=True)

    def _package_ref_xml(self, package: str) -> str:
        package_name = package.upper()
        package_uri = quote(package.lower())
        return (
            f'<adtcore:packageRef adtcore:uri="{ADT_BASE_PATH}/packages/{package_uri}" '
            f'adtcore:type="DEVC/K" adtcore:name="{package_name}"/>'
        )

    def _container_ref_xml(self, uri: str, adt_type: str, name: str) -> str:
        return (
            f'<adtcore:containerRef adtcore:uri="{self._xml_escape(uri)}" '
            f'adtcore:type="{self._xml_escape(adt_type)}" adtcore:name="{self._xml_escape(name.upper())}"/>'
        )

    def _object_reference_xml(self, reference: dict[str, str]) -> str:
        attrs = [f'adtcore:uri="{self._xml_escape(reference["uri"])}"']
        if reference.get("type"):
            attrs.append(f'adtcore:type="{self._xml_escape(reference["type"])}"')
        if reference.get("name"):
            attrs.append(f'adtcore:name="{self._xml_escape(reference["name"].upper())}"')
        return f'<adtcore:objectReference {" ".join(attrs)} />'

    def _object_references_xml(self, references: list[dict[str, str]]) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">'
            f'{"".join(self._object_reference_xml(reference) for reference in references)}'
            "</adtcore:objectReferences>"
        )

    def _repository_metadata_xml(
        self,
        root_name: str,
        namespace_attrs: str,
        object_name: str,
        adt_type: str,
        description: str,
        package: str,
        body: str = "",
        *,
        abap_language_version: str | None = DEFAULT_ABAP_LANGUAGE_VERSION,
        extra_attrs: str | None = None,
        include_package_ref: bool = True,
    ) -> str:
        version_attr = f' adtcore:abapLanguageVersion="{abap_language_version}"' if abap_language_version else ""
        additional_attrs = f" {extra_attrs}" if extra_attrs else ""
        package_ref = self._package_ref_xml(package) if include_package_ref else ""
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<{root_name} {namespace_attrs} "
            'xmlns:adtcore="http://www.sap.com/adt/core" '
            f'adtcore:name="{object_name}" adtcore:type="{adt_type}" '
            f'adtcore:description="{self._xml_escape(description)}"'
            f"{version_attr}{additional_attrs}>"
            f"{package_ref}"
            f"{body}"
            f"</{root_name}>"
        )

    def _dictionary_blue_xml(
        self,
        blue_namespace: str,
        object_name: str,
        adt_type: str,
        description: str,
        package: str,
        body: str,
    ) -> str:
        return self._repository_metadata_xml(
            "blue:wbobj",
            f'xmlns:blue="{blue_namespace}"',
            object_name,
            adt_type,
            description,
            package,
            body,
        )
