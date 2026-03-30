
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Literal, Optional
from contatos import add_contato, search_contatos
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

class CRMRequest(BaseModel):
    operation: Literal["add_contact", "search_contact"]
    nome: Optional[str] = Field(default=None, description="Nome do contato (para adicionar)")
    email: Optional[str] = Field(default=None, description="Email do contato (para adicionar)")
    query: Optional[str] = Field(default=None, description="Busca por nome/empresa")

@app.post("/execute", dependencies=[Depends(verify_api_key)])
def execute_crm(req: CRMRequest):
    if req.operation == "add_contact":
        if not req.nome or not req.email:
            return {"result": "Erro: nome e email obrigatórios para adicionar contato."}
        contato_id = add_contato(nome=req.nome, email=req.email)
        return {"result": f"Contato '{req.nome}' <{req.email}> adicionado.", "id": contato_id}
    elif req.operation == "search_contact":
        if not req.query:
            return {"result": "Erro: query obrigatória para busca."}
        contatos = search_contatos(req.query)
        return {"result": contatos}
    else:
        return {"result": "Operação não suportada."}

# MCP STDIO Support
import sys
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

# Configuração de log para stderr
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp-crm")

mcp_server = Server("mcp-crm")

@mcp_server.list_tools()
async def list_tools():
    return [
        Tool(
            name="add_contact",
            description="Adiciona um novo contato ao CRM.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nome": {"type": "string", "description": "Nome do contato"},
                    "email": {"type": "string", "description": "Email do contato"}
                },
                "required": ["nome", "email"]
            }
        ),
        Tool(
            name="search_contact",
            description="Busca contatos no CRM por nome ou empresa.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Termo de busca"}
                },
                "required": ["query"]
            }
        )
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "add_contact":
            contato_id = add_contato(
                nome=arguments["nome"],
                email=arguments["email"]
            )
            return [TextContent(type="text", text=f"Contato adicionado com ID: {contato_id}")]
        elif name == "search_contact":
            contatos = search_contatos(arguments["query"])
            return [TextContent(type="text", text=str(contatos))]
        raise ValueError(f"Tool not found: {name}")
    except Exception as e:
        logger.error(f"Erro ao executar ferramenta {name}: {e}")
        return [TextContent(type="text", text=f"Erro interno: {str(e)}")]

async def main_mcp():
    try:
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())
    except Exception as e:
        logger.error(f"Falha fatal no servidor MCP crm: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main_mcp())
