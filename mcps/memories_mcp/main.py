
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Literal, Optional
from memories import add_memory, get_memory
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

class MemoryRequest(BaseModel):
    operation: Literal["save_memory", "get_memory"]
    conteudo: Optional[str] = Field(default=None, description="Conteúdo da memória (para salvar)")
    tipo: Optional[str] = Field(default=None, description="Tipo da memória (semantica, episodica, etc)")
    contato_id: Optional[str] = Field(default=None, description="ID do contato relacionado")
    categoria: Optional[str] = Field(default=None, description="Categoria da memória")
    limit: Optional[int] = Field(default=10, description="Limite de resultados para busca")

@app.post("/execute", dependencies=[Depends(verify_api_key)])
def execute_memory(req: MemoryRequest):
    if req.operation == "save_memory":
        if not req.conteudo:
            return {"result": "Erro: conteudo obrigatório para salvar memória."}
        memory_id = add_memory(conteudo=req.conteudo, tipo=req.tipo or "semantica", contato_id=req.contato_id, categoria=req.categoria)
        return {"result": f"Memória salva.", "id": memory_id}
    elif req.operation == "get_memory":
        mems = get_memory(limit=req.limit or 10, tipo=req.tipo, contato_id=req.contato_id, categoria=req.categoria)
        return {"result": mems}
    else:
        return {"result": "Operação não suportada."}

# MCP STDIO Support
import sys
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

# Configuração de log para stderr para não quebrar o protocolo STDIO (que usa stdout)
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp-memories")

mcp_server = Server("mcp-memories")

@mcp_server.list_tools()
async def list_tools():
    return [
        Tool(
            name="save_memory",
            description="Salva uma nova memória no banco de dados.",
            inputSchema={
                "type": "object",
                "properties": {
                    "conteudo": {"type": "string", "description": "Conteúdo da memória"},
                    "tipo": {"type": "string", "description": "Tipo da memória (semantica, episodica, etc)"},
                    "contato_id": {"type": "string", "description": "ID do contato relacionado"},
                    "categoria": {"type": "string", "description": "Categoria da memória"}
                },
                "required": ["conteudo"]
            }
        ),
        Tool(
            name="get_memory",
            description="Recupera memórias do banco de dados.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Limite de resultados"},
                    "tipo": {"type": "string", "description": "Tipo da memória"},
                    "contato_id": {"type": "string", "description": "ID do contato"},
                    "categoria": {"type": "string", "description": "Categoria"}
                }
            }
        )
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "save_memory":
            memory_id = add_memory(
                conteudo=arguments["conteudo"],
                tipo=arguments.get("tipo", "semantica"),
                contato_id=arguments.get("contato_id"),
                categoria=arguments.get("categoria")
            )
            return [TextContent(type="text", text=f"Memória salva com ID: {memory_id}")]
        elif name == "get_memory":
            mems = get_memory(
                limit=arguments.get("limit", 10),
                tipo=arguments.get("tipo"),
                contato_id=arguments.get("contato_id"),
                categoria=arguments.get("categoria")
            )
            return [TextContent(type="text", text=str(mems))]
        raise ValueError(f"Tool not found: {name}")
    except Exception as e:
        logger.error(f"Erro ao executar ferramenta {name}: {e}")
        return [TextContent(type="text", text=f"Erro interno: {str(e)}")]

async def main_mcp():
    try:
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())
    except Exception as e:
        logger.error(f"Falha fatal no servidor MCP memories: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main_mcp())
