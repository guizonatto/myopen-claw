
import sys
import logging
import asyncio
import threading
from typing import Literal, Optional, AsyncGenerator
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse

from pydantic import BaseModel, Field
from sqlalchemy import text


from sqlalchemy import text

from typing import AsyncGenerator
# Importações do seu projeto local
from memories import add_memory, get_memory
from db import get_session
from auth import verify_api_key

# Importações Oficiais do MCP
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# --- CONFIGURAÇÃO DE LOGS ---
# IMPORTANTE: Redirecionamos logs para stderr. 
# O stdout deve ser EXCLUSIVO para o protocolo JSON-RPC do MCP.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("mcp-memories")

app = FastAPI()
mcp_server = Server("mcp-memories")

# --- PARTE 1: API HTTP (FastAPI) ---

@app.get("/health")
def health():
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

class MemoryRequest(BaseModel):
    operation: Literal["save_memory_long", "get_memory_long"]
    conteudo: Optional[str] = Field(default=None)
    tipo: Optional[str] = Field(default=None)
    contato_id: Optional[str] = Field(default=None)
    categoria: Optional[str] = Field(default=None)
    limit: Optional[int] = Field(default=10)

@app.post("/execute", dependencies=[Depends(verify_api_key)])
def execute_memory(req: MemoryRequest):
    if req.operation == "save_memory_long":
        if not req.conteudo:
            return {"result": "Erro: conteudo obrigatório."}
        mid = add_memory(conteudo=req.conteudo, tipo=req.tipo or "semantica", contato_id=req.contato_id, categoria=req.categoria)
        return {"result": "Memória salva.", "id": mid}
    elif req.operation == "get_memory_long":
        return {"result": get_memory(limit=req.limit, tipo=req.tipo, contato_id=req.contato_id, categoria=req.categoria)}
    return {"result": "Operação não suportada."}

# --- PARTE 2: MCP (STDIO) ---

@mcp_server.list_tools()
async def list_tools():
    return [
        Tool(
            name="save_memory_long",
            description="Salva uma nova memória de longo prazo no banco de dados.",
            inputSchema={
                "type": "object",
                "properties": {
                    "conteudo": {"type": "string"},
                    "tipo": {"type": "string"},
                    "contato_id": {"type": "string"},
                    "categoria": {"type": "string"}
                },
                "required": ["conteudo"]
            }
        ),
        Tool(
            name="get_memory_long",
            description="Recupera memórias de longo prazo salvas.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                    "tipo": {"type": "string"},
                    "contato_id": {"type": "string"},
                    "categoria": {"type": "string"}
                }
            }
        )
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "save_memory_long":
            mid = add_memory(
                conteudo=arguments["conteudo"],
                tipo=arguments.get("tipo", "semantica"),
                contato_id=arguments.get("contato_id"),
                categoria=arguments.get("categoria")
            )
            return [TextContent(type="text", text=f"Memória salva com ID: {mid}")]
        
        elif name == "get_memory_long":
            mems = get_memory(
                limit=arguments.get("limit", 10),
                tipo=arguments.get("tipo"),
                contato_id=arguments.get("contato_id"),
                categoria=arguments.get("categoria")
            )
            return [TextContent(type="text", text=str(mems))]
            
    except Exception as e:
        logger.error(f"Erro na tool {name}: {e}")
        return [TextContent(type="text", text=f"Erro: {str(e)}")]

# --- PARTE 3: EXECUÇÃO HÍBRIDA ---

def run_mcp_loop():
    """Roda o servidor MCP STDIO em um loop de eventos separado"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def _run():
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.run(
                read_stream, 
                write_stream, 
                mcp_server.create_initialization_options()
            )
    
    try:
        loop.run_until_complete(_run())
    except Exception as e:
        logger.error(f"Erro no loop MCP: {e}")

if __name__ == "__main__":
    import uvicorn

    # 1. Inicia o MCP em uma Thread separada (Daemon para fechar junto com o app)
    mcp_thread = threading.Thread(target=run_mcp_loop, daemon=True)
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
    async def sse_memory(req: MemoryRequest, request: Request):
        async def event_stream():
            async for event in sse_event_generator(req.operation, req.dict()):
                if await request.is_disconnected():
                    break
                yield event
        return StreamingResponse(event_stream(), media_type="text/event-stream")
    mcp_thread.start()

    # 2. Roda o FastAPI (Silenciamos o log do uvicorn para não quebrar o STDIO)
    # IMPORTANTE: host 0.0.0.0 para funcionar dentro do Docker
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")