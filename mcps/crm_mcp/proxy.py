"""
MCP Proxy — crm-proxy
Função: Expõe UMA tool (crm) que encaminha qualquer operação para o mcp-crm via chamada direta.
Usar quando: agentes precisam de acesso ao CRM com schema mínimo (~500 chars vs ~14k).

ENV_VARS:
  - (nenhuma) — roda dentro do container mcp-crm, importa funções diretamente
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError:
    Server = None
    stdio_server = None
    TextContent = None
    Tool = None

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger("crm-proxy")

CRM_TOOL = Tool(
    name="crm",
    description=(
        "Execute a CRM operation. "
        "Pass action name and params dict. "
        "Available actions and params documented in AGENTS.md."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Operation name (e.g. search_contact, log_conversation_event)",
            },
            "params": {
                "type": "object",
                "description": "Operation parameters as key-value pairs",
                "additionalProperties": True,
            },
        },
        "required": ["action"],
    },
)

# Lazy-load mcp-crm execute handler to avoid circular imports at module level
_execute_handler = None


def _get_execute():
    global _execute_handler
    if _execute_handler is not None:
        return _execute_handler
    try:
        from main import execute_crm, CRMRequest
        _execute_handler = (execute_crm, CRMRequest)
    except Exception as e:
        logger.error("Failed to import mcp-crm execute_crm: %s", e)
    return _execute_handler


def _call_crm(action: str, params: dict) -> str:
    loaded = _get_execute()
    if loaded is None:
        return json.dumps({"error": "mcp-crm functions unavailable"})
    execute_crm, CRMRequest = loaded
    try:
        req = CRMRequest(operation=action, **(params or {}))
        result = execute_crm(req)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"crm error: {str(e)}"})


if Server is not None:
    mcp_server = Server("crm-proxy")

    @mcp_server.list_tools()
    async def list_tools():
        return [CRM_TOOL]

    @mcp_server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name != "crm":
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
        action = arguments.get("action", "")
        params = arguments.get("params") or {}
        result = _call_crm(action, params)
        return [TextContent(type="text", text=result)]

    async def main():
        try:
            async with stdio_server() as (read_stream, write_stream):
                await mcp_server.run(
                    read_stream, write_stream,
                    mcp_server.create_initialization_options(),
                )
        except Exception as e:
            logger.error("crm-proxy fatal: %s", e, exc_info=True)
            sys.exit(1)
else:
    async def main():
        raise RuntimeError("mcp[stdio] not installed.")


if __name__ == "__main__":
    asyncio.run(main())
