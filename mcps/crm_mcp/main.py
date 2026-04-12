

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, AsyncGenerator
from contatos import add_contato, search_contatos, update_contato, list_contacts_to_follow_up
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
    operation: Literal["add_contact", "search_contact", "update_contact", "list_contacts_to_follow_up"]
    nome: Optional[str] = Field(default=None, description="Nome do contato (para adicionar)")
    email: Optional[str] = Field(default=None, description="Email do contato (para adicionar)")
    cnpj: Optional[str] = Field(default=None, description="CNPJ da empresa")
    cnaes: Optional[List[str]] = Field(default=None, description="Lista de CNAEs")
    query: Optional[str] = Field(default=None, description="Busca por nome/empresa")
    contact_id: Optional[str] = Field(default=None, description="UUID do contato (para update)")
    apelido: Optional[str] = Field(default=None)
    tipo: Optional[str] = Field(default=None)
    whatsapp: Optional[str] = Field(default=None)
    telefone: Optional[str] = Field(default=None)
    linkedin: Optional[str] = Field(default=None)
    instagram: Optional[str] = Field(default=None)
    empresa: Optional[str] = Field(default=None)
    cargo: Optional[str] = Field(default=None)
    setor: Optional[str] = Field(default=None)
    pipeline_status: Optional[str] = Field(default=None, description="Status no funil: lead | qualificado | interesse | proposta | fechado | perdido")
    stage: Optional[str] = Field(default=None, description="Intent/estágio atual da venda")
    icp_type: Optional[str] = Field(default=None, description="Perfil do cliente: A, B ou Hesitante")
    nota: Optional[str] = Field(default=None, description="Nota a ser appendada com timestamp")
    hours_since_last_contact: Optional[int] = Field(default=24, description="Horas desde o último contato (para list_contacts_to_follow_up)")
    limit: Optional[int] = Field(default=10, description="Limite de contatos retornados")


@app.post("/execute", dependencies=[Depends(verify_api_key)])
def execute_crm(req: CRMRequest):
    if req.operation == "add_contact":
        if not req.nome or not req.email:
            return {"result": "Erro: nome e email obrigatórios para adicionar contato."}
        contato_id = add_contato(nome=req.nome, email=req.email, cnpj=req.cnpj, cnaes=req.cnaes)
        return {"result": f"Contato '{req.nome}' <{req.email}> adicionado.", "id": contato_id}
    elif req.operation == "search_contact":
        if not req.query:
            return {"result": "Erro: query obrigatória para busca."}
        contatos = search_contatos(req.query)
        return {"result": contatos}
    elif req.operation == "update_contact":
        if not req.contact_id:
            return {"result": "Erro: contact_id obrigatório para atualizar contato."}
        result = update_contato(
            contact_id=req.contact_id,
            apelido=req.apelido, tipo=req.tipo, whatsapp=req.whatsapp,
            email=req.email, telefone=req.telefone, linkedin=req.linkedin,
            instagram=req.instagram, empresa=req.empresa, cargo=req.cargo,
            setor=req.setor, pipeline_status=req.pipeline_status,
            stage=req.stage, icp_type=req.icp_type, nota=req.nota,
        )
        if "error" in result:
            return {"result": result["error"]}
        return {"result": result}
    elif req.operation == "list_contacts_to_follow_up":
        contacts = list_contacts_to_follow_up(
            hours_since_last_contact=req.hours_since_last_contact or 24,
            limit=req.limit or 10,
        )
        return {"result": contacts}
    else:
        return {"result": "Operação não suportada."}

# --- SSE Endpoint ---
import json

async def sse_event_generator(operation: str, params: dict) -> AsyncGenerator[str, None]:
    import asyncio
    try:
        yield f"data: {json.dumps({'status': 'started', 'operation': operation})}\n\n"
        for i in range(3):
            await asyncio.sleep(1)
            yield f"data: {json.dumps({'progress': (i+1)*33, 'msg': f'Etapa {i+1}/3', 'operation': operation})}\n\n"
        # Resultado final (simples)
        result = f"Operação {operation} executada com params {params}"
        yield f"data: {json.dumps({'status': 'done', 'result': result})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"

@app.post("/sse", dependencies=[Depends(verify_api_key)])
async def sse_crm(req: CRMRequest, request: Request):
    async def event_stream():
        async for event in sse_event_generator(req.operation, req.dict()):
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
                    "email": {"type": "string", "description": "Email do contato"},
                    "cnpj": {"type": "string", "description": "CNPJ da empresa (formato XX.XXX.XXX/XXXX-XX)"},
                    "cnaes": {"type": "array", "items": {"type": "string"}, "description": "Lista de CNAEs"}
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
        ),
        Tool(
            name="list_contacts_to_follow_up",
            description="Lista contatos elegíveis para abordagem proativa: pipeline não fechado/perdido e sem contato há X horas.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hours_since_last_contact": {"type": "integer", "description": "Horas desde o último contato (default: 24)"},
                    "limit": {"type": "integer", "description": "Máximo de contatos retornados (default: 10)"}
                },
                "required": []
            }
        ),
        Tool(
            name="update_contact",
            description="Atualiza campos de um contato existente. Notas são appendadas com timestamp.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "UUID do contato"},
                    "pipeline_status": {"type": "string", "enum": ["lead", "qualificado", "interesse", "proposta", "fechado", "perdido"], "description": "Status no funil de vendas"},
                    "stage": {"type": "string", "description": "Intent da última interação (ex: caos_operacional, curiosidade_ativa, aceite)"},
                    "icp_type": {"type": "string", "enum": ["A", "B", "Hesitante"], "description": "Perfil do cliente"},
                    "nota": {"type": "string", "description": "Nota a ser appendada com timestamp no histórico"},
                    "whatsapp": {"type": "string"},
                    "email": {"type": "string"},
                    "empresa": {"type": "string"},
                    "cargo": {"type": "string"},
                    "tipo": {"type": "string"}
                },
                "required": ["contact_id"]
            }
        ),
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "add_contact":
            contato_id = add_contato(
                nome=arguments["nome"],
                email=arguments["email"],
                cnpj=arguments.get("cnpj"),
                cnaes=arguments.get("cnaes"),
            )
            return [TextContent(type="text", text=f"Contato adicionado com ID: {contato_id}")]
        elif name == "search_contact":
            contatos = search_contatos(arguments["query"])
            return [TextContent(type="text", text=str(contatos))]
        elif name == "update_contact":
            result = update_contato(
                contact_id=arguments["contact_id"],
                pipeline_status=arguments.get("pipeline_status"),
                stage=arguments.get("stage"),
                icp_type=arguments.get("icp_type"),
                nota=arguments.get("nota"),
                whatsapp=arguments.get("whatsapp"),
                email=arguments.get("email"),
                empresa=arguments.get("empresa"),
                cargo=arguments.get("cargo"),
                tipo=arguments.get("tipo"),
            )
            return [TextContent(type="text", text=str(result))]
        elif name == "list_contacts_to_follow_up":
            contacts = list_contacts_to_follow_up(
                hours_since_last_contact=arguments.get("hours_since_last_contact", 24),
                limit=arguments.get("limit", 10),
            )
            return [TextContent(type="text", text=str(contacts))]
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
