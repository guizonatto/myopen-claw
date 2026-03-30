from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import Any
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

# MCP STDIO Support
import sys
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

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
