# SAP BTP ABAP ADT MCP Server

Python + FastMCP + ASGI MCP server for SAP ABAP Development Tools access.

This server is focused on practical ADT development workflows:

- Browser SSO assisted ADT login
- Repository search
- Source and metadata read
- Controlled create, update, activate, delete
- OData V4 service binding publish

## Runtime

- Python 3.11+
- Access to an SAP ABAP system with ADT enabled
- Browser SSO access to the target system
- Change authorization for the object types you intend to modify

Install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e .
```

## Project Layout

- `sap_mcp/` - MCP server source code.
  - `server.py` - HTTP transport entrypoint.
  - `stdio_server.py` - STDIO transport entrypoint for IDEs such as Kiro.
  - `callback.py` - shared browser SSO callback routes.
  - `auth/`, `connectors/`, `services/` - authentication, ADT HTTP calls, and tool orchestration.
- `sap-mcp.example.yaml` - safe example config.
- `sap-mcp.yaml` - local private config; stores `abap_dev.system_url` and write permissions.
- `.sap-mcp-session.json` - local browser SSO session file; do not commit or share.
- `.venv/`, `__pycache__/`, `*.egg-info/` - generated local artifacts; safe to delete and recreate.

## HTTP Endpoints

- `/mcp`
- `/healthz`
- `/logon/success`

## STDIO Transport

For IDEs that launch MCP servers through STDIO, such as Kiro:

```powershell
python -m sap_mcp.stdio_server
```

The STDIO server also starts a small local callback listener for browser SSO at the configured
`abap_dev.callback_url`, so `abap_adt_login` can complete without running the HTTP MCP server.

## Supported MCP Tools

- `abap_adt_login`
- `abap_save_sso_session`
- `abap_save_sso_cookie_header`
- `abap_adt_connect`
- `abap_search_objects`
- `abap_read_source`
- `abap_create_object`
- `abap_update_source`
- `abap_activate_object`
- `abap_delete_object`
- `abap_publish_service_binding`

## Supported Object Coverage

The following object types are supported for read, create, update, and delete:

- `CLAS`, `INTF`
- `DDLS`, `DCLS`, `BDEF`, `DDLX`, `SRVD`, `SRVB`
- `TABL`, `DTEL`, `DOMA`, `DEVC`
- `PROG`, `FUGR`, `FUNC`

Notes:

- Class and interface reads aggregate local includes such as `definitions` and `implementations`.
- Standard SAP packages can be read when `readable_packages` allows them, but standard SAP objects must remain read-only in normal use.
- Create, update, activate, publish, and delete operations are restricted by `allowed_packages`.
- Backend authorizations still apply. If the SAP system blocks an object type, MCP will surface the ADT error.

## Configuration

Copy the example config:

```powershell
copy sap-mcp.example.yaml sap-mcp.yaml
```

Example:

```yaml
server:
  name: "SAP BTP ABAP ADT MCP Server"
  auth_tokens:
    - "dev-token"

abap_dev:
  system_url: "https://your-abap-instance.abap.region.hana.ondemand.com"
  callback_url: "http://localhost:8000/logon/success"
  reentrance_endpoint: "/sap/bc/sec/reentrance"
  reentrance_scenario: "FTO1"
  session_path: ".sap-mcp-session.json"
  readable_packages:
    - "*"
  allowed_packages:
    - "Z*"
  allow_write: false
  allow_activate: false
  default_timeout_seconds: 30
```

Security notes:

- Configure the ABAP system directly in `abap_dev.system_url`.
- Do not distribute `.sap-mcp-session.json`, `.env`, or your real `sap-mcp.yaml`.
- Prefer `readable_packages: ["*"]` with a narrow `allowed_packages` list for production use.

## Start

```powershell
$env:SAP_MCP_AUTH_TOKENS="dev-token"
uvicorn sap_mcp.server:app --host 127.0.0.1 --port 8000
```

## ADT Login Flow

1. Call `abap_adt_login`.
2. Complete SAP SSO in the browser.
3. The callback at `/logon/success` stores the ADT reentrance session locally.
4. Call `abap_adt_connect`.
5. Use read tools first, then enable write and activate only when needed.
