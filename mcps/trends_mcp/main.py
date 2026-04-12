
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, AsyncGenerator
from sqlalchemy import text
from db import get_session
from auth import verify_api_key

app = FastAPI()


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


@app.post("/execute", dependencies=[Depends(verify_api_key)])
def execute_skill(req: SkillRequest):
    # Exemplo: apenas ecoa a operação e parâmetros
    return {"result": f"Operação {req.operation} executada com params {req.params}"}

# --- SSE Endpoint ---
import json

async def sse_event_generator(operation: str, params: dict) -> AsyncGenerator[str, None]:
    # Simula processamento e envia updates parciais
    try:
        # Início do processamento
        yield f"data: {json.dumps({'status': 'started', 'operation': operation})}\n\n"
        # Simulação de etapas (em produção, acione lógica real)
        import asyncio
        for i in range(3):
            await asyncio.sleep(1)
            yield f"data: {json.dumps({'progress': (i+1)*33, 'msg': f'Etapa {i+1}/3', 'operation': operation})}\n\n"
        # Resultado final
        result = f"Operação {operation} executada com params {params}"
        yield f"data: {json.dumps({'status': 'done', 'result': result})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"

@app.post("/sse", dependencies=[Depends(verify_api_key)])
async def sse_skill(req: SkillRequest, request: Request):
    async def event_stream():
        async for event in sse_event_generator(req.operation, req.params):
            # Permite cancelamento pelo cliente
            if await request.is_disconnected():
                break
            yield event
    return StreamingResponse(event_stream(), media_type="text/event-stream")

# MCP STDIO Support
import sys
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configuração de log para stderr
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp-trends")

mcp_server = Server("mcp-trends")

@mcp_server.list_tools()
async def list_tools():
    return [
        Tool(
            name="execute_trend_skill",
            description="Executa uma operação de análise de tendências.",
            inputSchema={
                "type": "object",
                "properties": {
                    "operation": {"type": "string"},
                    "params": {"type": "object"}
                },
                "required": ["operation", "params"]
            }
        )
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "execute_trend_skill":
            result = f"Operação {arguments['operation']} executada com params {arguments['params']}"
            return [TextContent(type="text", text=result)]
        raise ValueError(f"Tool not found: {name}")
    except Exception as e:
        logger.error(f"Erro ao executar ferramenta {name}: {e}")
        return [TextContent(type="text", text=f"Erro interno: {str(e)}")]

async def main_mcp():
    try:
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())
    except Exception as e:
        logger.error(f"Falha fatal no servidor MCP trends: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main_mcp())
