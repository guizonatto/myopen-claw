"""
MCP Proxy — leads-proxy
Função: Expõe UMA tool (leads) com schema mínimo e encaminha para o mcp-leads local.
Usar quando: agentes precisam de prospecção sem injetar schema grande no prompt.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

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
logger = logging.getLogger("leads-proxy")

def _build_leads_tool():
    return Tool(
        name="leads",
        description=(
            "Execute a leads operation with compact schema. "
            "Use action (e.g. sindico_leads) and optional params."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Operation name (e.g. sindico_leads)",
                },
                "params": {
                    "type": "object",
                    "description": "Operation parameters",
                    "additionalProperties": True,
                },
            },
            "required": ["action"],
        },
    )

_runner = None


def _get_runner():
    global _runner
    if _runner is not None:
        return _runner
    try:
        try:
            from .main import run_operation  # type: ignore
        except Exception:
            from main import run_operation  # type: ignore
        _runner = run_operation
    except Exception as exc:
        logger.error("Failed to import mcp-leads run_operation: %s", exc)
        _runner = None
    return _runner


def _call_leads(action: str, params: dict[str, Any]) -> str:
    runner = _get_runner()
    if runner is None:
        return json.dumps({"error": "mcp-leads functions unavailable"})
    try:
        result = runner(action, params or {})
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": f"leads error: {str(exc)}"})


if Server is not None:
    mcp_server = Server("leads-proxy")

    @mcp_server.list_tools()
    async def list_tools():
        return [_build_leads_tool()]

    @mcp_server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name != "leads":
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
        action = arguments.get("action", "")
        params = arguments.get("params") or {}
        result = _call_leads(action, params)
        return [TextContent(type="text", text=result)]

    async def main():
        try:
            async with stdio_server() as (read_stream, write_stream):
                await mcp_server.run(
                    read_stream,
                    write_stream,
                    mcp_server.create_initialization_options(),
                )
        except Exception as exc:
            logger.error("leads-proxy fatal: %s", exc, exc_info=True)
            sys.exit(1)
else:
    async def main():
        raise RuntimeError("mcp[stdio] not installed.")


if __name__ == "__main__":
    asyncio.run(main())
