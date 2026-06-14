# SAP BTP ABAP ADT MCP Server

这是一个基于 Python、FastMCP 和 ADT HTTP API 的 SAP ABAP MCP 服务端。

## 当前能力

- 浏览器 SSO 登录 ADT
- ABAP Repository 搜索
- 源码和元数据读取
- 受控创建、修改、激活、删除
- OData V4 Service Binding 发布
- HTTP 和 STDIO 两种 MCP Transport

## 运行要求

- Python 3.11+
- 目标 SAP ABAP 系统已启用 ADT
- 可以通过浏览器完成 SAP SSO
- 对需要修改的对象具备后端开发权限

## 项目结构

- `sap_mcp/`：MCP 服务端源码。
  - `server.py`：HTTP Transport 入口。
  - `stdio_server.py`：STDIO Transport 入口，适合 Kiro 等 IDE 启动。
  - `callback.py`：共享的 SSO 回调路由。
  - `auth/`、`connectors/`、`services/`：认证、ADT 请求和工具编排。
- `sap-mcp.example.yaml`：安全的示例配置。
- `sap-mcp.yaml`：本地私有配置，保存 `abap_dev.system_url` 和写入权限等设置。
- `.sap-mcp-session.json`：本地浏览器 SSO 会话文件，不要提交或分享。

## 配置

复制示例配置：

```powershell
copy sap-mcp.example.yaml sap-mcp.yaml
```

示例：

```yaml
server:
  name: "SAP BTP Trial ABAP ADT MCP Server"
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

请在 `abap_dev.system_url` 中直接配置 SAP ABAP 系统地址。不要分发 `.sap-mcp-session.json`、`.env` 或真实的 `sap-mcp.yaml`。

## 启动

HTTP：

```powershell
uvicorn sap_mcp.server:app --host 127.0.0.1 --port 8000
```

STDIO：

```powershell
python -m sap_mcp.stdio_server
```

STDIO 模式会同时启动一个本地 SSO 回调监听器，监听地址来自 `abap_dev.callback_url`。

## MCP Tools

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

## 当前支持范围

- `CLAS`、`INTF`
- `DDLS`、`DCLS`、`BDEF`、`DDLX`、`SRVD`、`SRVB`
- `TABL`、`DTEL`、`DOMA`、`DEVC`
- `PROG`、`FUGR`、`FUNC`

## 登录流程

1. 调用 `abap_adt_login`。
2. 在浏览器中完成 SAP SSO。
3. `/logon/success` 回调保存 `.sap-mcp-session.json`。
4. 调用 `abap_adt_connect` 验证连接。
5. 建议先读后写，只有确实需要时再开启 `allow_write` 和 `allow_activate`。
