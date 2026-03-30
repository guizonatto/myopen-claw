from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from api.endpoints import router
from db.models import engine, get_session, Compra, Wishlist
from typing import List

app = FastAPI(title="Shopping Tracker MCP")

app.include_router(router)


@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/")
def root():
    return {"status": "ok", "message": "Shopping Tracker MCP running"}

# MCP STDIO Support
import sys
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

# Configuração de log para stderr
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp-shopping")

mcp_server = Server("mcp-shopping")

@mcp_server.list_tools()
async def list_tools():
    return [
        Tool(
            name="registrar_compra",
            description="Registra uma ou mais compras no sistema.",
            inputSchema={
                "type": "object",
                "properties": {
                    "compras": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "nome": {"type": "string"},
                                "quantidade": {"type": "number"},
                                "unidade": {"type": "string", "default": "unidade"},
                                "wishlist": {"type": "boolean", "default": False},
                                "preco": {"type": "number"},
                                "loja": {"type": "string"},
                                "marca": {"type": "string"},
                                "volume_embalagem": {"type": "string"}
                            },
                            "required": ["nome", "quantidade"]
                        }
                    }
                },
                "required": ["compras"]
            }
        ),
        Tool(
            name="listar_wishlist",
            description="Lista os itens da wishlist.",
            inputSchema={"type": "object", "properties": {}}
        )
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "registrar_compra":
            with get_session() as session:
                for item in arguments["compras"]:
                    compra = Compra(
                        nome=item["nome"],
                        quantidade=item["quantidade"],
                        unidade=item.get("unidade", "unidade"),
                        wishlist=item.get("wishlist", False),
                        preco=item.get("preco"),
                        loja=item.get("loja"),
                        marca=item.get("marca"),
                        volume_embalagem=item.get("volume_embalagem")
                    )
                    session.add(compra)
                session.commit()
            return [TextContent(type="text", text="Compras registradas com sucesso.")]
        elif name == "listar_wishlist":
            with get_session() as session:
                items = session.query(Wishlist).all()
                result = [item.to_dict() for item in items]
            return [TextContent(type="text", text=str(result))]
        raise ValueError(f"Tool not found: {name}")
    except Exception as e:
        logger.error(f"Erro ao executar ferramenta {name}: {e}")
        return [TextContent(type="text", text=f"Erro interno: {str(e)}")]

async def main_mcp():
    try:
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())
    except Exception as e:
        logger.error(f"Falha fatal no servidor MCP shopping: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main_mcp())
