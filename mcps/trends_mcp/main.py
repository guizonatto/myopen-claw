from __future__ import annotations

from typing import Any, AsyncGenerator

import json
import logging
import sys

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text

try:
    from .auth import verify_api_key
    from .db import get_session
except ImportError:  # pragma: no cover
    from auth import verify_api_key
    from db import get_session

app = FastAPI()

# Configuração de log para stderr
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp-trends")


@app.get("/health")
def health():
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


class SkillRequest(BaseModel):
    operation: str
    params: dict[str, Any]


def _clean_trend_names(raw: Any, *, limit: int = 200) -> list[str]:
    if not isinstance(raw, list):
        return []
    seen: set[str] = set()
    cleaned: list[str] = []
    for item in raw:
        if len(cleaned) >= limit:
            break
        name = str(item).strip()
        if not name:
            continue
        if name in seen:
            continue
        seen.add(name)
        cleaned.append(name[:280])
    return cleaned


def _replace_trends(trends: list[str]) -> dict[str, Any]:
    with get_session() as session:
        session.execute(text("DELETE FROM trends_mcp.trends"))
        for nome in trends:
            session.execute(
                text("INSERT INTO trends_mcp.trends (nome) VALUES (:nome)"),
                {"nome": nome},
            )
    return {"stored": len(trends)}


def _list_trends(limit: int) -> list[str]:
    limit = max(1, min(int(limit or 100), 500))
    with get_session() as session:
        rows = session.execute(
            text("SELECT nome FROM trends_mcp.trends ORDER BY updated_at DESC, id DESC LIMIT :limit"),
            {"limit": limit},
        ).fetchall()
    return [r[0] for r in rows]


def run_operation(operation: str, params: dict[str, Any]) -> dict[str, Any]:
    if operation == "replace_trends":
        trends = _clean_trend_names(params.get("trends"))
        result = _replace_trends(trends)
        return {"operation": operation, **result}
    if operation == "list_trends":
        limit = params.get("limit") or 100
        trends = _list_trends(int(limit))
        return {"operation": operation, "trends": trends, "count": len(trends)}
    if operation == "ping":
        return {"operation": operation, "status": "ok"}
    return {"operation": operation, "result": f"Operação {operation} executada com params {params}"}


@app.post("/execute", dependencies=[Depends(verify_api_key)])
def execute_skill(req: SkillRequest):
    return {"result": run_operation(req.operation, req.params)}


async def sse_event_generator(operation: str, params: dict) -> AsyncGenerator[str, None]:
    try:
        yield f"data: {json.dumps({'status': 'started', 'operation': operation})}\n\n"
        import asyncio

        for i in range(3):
            await asyncio.sleep(1)
            yield f"data: {json.dumps({'progress': (i+1)*33, 'msg': f'Etapa {i+1}/3', 'operation': operation})}\n\n"
        result = f"Operação {operation} executada com params {params}"
        yield f"data: {json.dumps({'status': 'done', 'result': result})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"


@app.post("/sse", dependencies=[Depends(verify_api_key)])
async def sse_skill(req: SkillRequest, request: Request):
    async def event_stream():
        async for event in sse_event_generator(req.operation, req.params):
            if await request.is_disconnected():
                break
            yield event

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# MCP STDIO Support (import-safe fora do container)
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError:  # pragma: no cover
    async def main_mcp():
        raise RuntimeError("Dependência 'mcp' não encontrada. Instale mcp[stdio] para usar via STDIO.")
else:
    mcp_server = Server("mcp-trends")

    @mcp_server.list_tools()
    async def list_tools():
        return [
            Tool(
                name="execute_trend_skill",
                description="Executa uma operação do MCP trends (ex: replace_trends, list_trends).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string"},
                        "params": {"type": "object"},
                    },
                    "required": ["operation", "params"],
                },
            )
        ]

    @mcp_server.call_tool()
    async def call_tool(name: str, arguments: dict):
        try:
            if name != "execute_trend_skill":
                raise ValueError(f"Tool not found: {name}")

            operation = arguments.get("operation")
            params = arguments.get("params") or {}
            if not isinstance(params, dict):
                raise ValueError("params must be an object")

            result = run_operation(operation, params)
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
        except Exception as e:
            logger.error("Erro ao executar ferramenta %s: %s", name, e)
            return [TextContent(type="text", text=f"Erro interno: {str(e)}")]

    async def main_mcp():
        try:
            async with stdio_server() as (read_stream, write_stream):
                await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())
        except Exception as e:
            logger.error("Falha fatal no servidor MCP trends: %s", e, exc_info=True)
            sys.exit(1)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main_mcp())
