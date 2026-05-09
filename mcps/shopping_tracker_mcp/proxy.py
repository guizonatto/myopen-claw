"""
MCP Proxy para shopping_tracker_mcp.
Expõe 1 tool unificada 'shopping' em vez de registrar_compra + listar_wishlist.
Reduz schema injection: ~3k chars -> ~400 chars.
"""
from __future__ import annotations
import json
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import asyncio

_server: Server | None = None

def _get_server() -> Server:
    global _server
    if _server is None:
        _server = Server("shopping-proxy")
    return _server

SHOPPING_TOOL = Tool(
    name="shopping",
    description=(
        "Gerencia lista de compras e wishlist. "
        "action='add': adiciona item (params: nome, quantidade, unidade, wishlist=true/false, preco, loja, marca). "
        "action='list_wishlist': lista a wishlist. "
        "action='list_compras': lista compras recentes."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["add", "list_wishlist", "list_compras"]},
            "params": {"type": "object", "additionalProperties": True}
        },
        "required": ["action"]
    }
)


def _call_shopping(action: str, params: dict) -> str:
    import importlib.util, os, sys as _sys
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in _sys.path:
        _sys.path.insert(0, app_dir)

    if action == "add":
        from db.models import SessionLocal, Compra  # type: ignore
        compras_data = params if isinstance(params.get("nome"), str) else params.get("compras", [params])
        if isinstance(compras_data, dict):
            compras_data = [compras_data]
        db = SessionLocal()
        try:
            for item in compras_data:
                c = Compra(
                    nome=item.get("nome"),
                    quantidade=item.get("quantidade", 1),
                    unidade=item.get("unidade", "unidade"),
                    wishlist=item.get("wishlist", False),
                    preco=item.get("preco"),
                    loja=item.get("loja"),
                    marca=item.get("marca"),
                    volume_embalagem=item.get("volume_embalagem"),
                )
                db.add(c)
            db.commit()
            return json.dumps({"ok": True, "message": "Compras registradas com sucesso.", "count": len(compras_data)}, ensure_ascii=False)
        finally:
            db.close()

    elif action == "list_wishlist":
        from db.models import SessionLocal, Compra  # type: ignore
        db = SessionLocal()
        try:
            items = db.query(Compra).filter(Compra.wishlist == True).all()
            return json.dumps([{"nome": i.nome, "quantidade": i.quantidade, "unidade": i.unidade} for i in items], ensure_ascii=False)
        finally:
            db.close()

    elif action == "list_compras":
        from db.models import SessionLocal, Compra  # type: ignore
        db = SessionLocal()
        try:
            items = db.query(Compra).order_by(Compra.id.desc()).limit(20).all()
            return json.dumps([{"nome": i.nome, "quantidade": i.quantidade, "wishlist": i.wishlist, "ultima_compra": str(i.ultima_compra)} for i in items], ensure_ascii=False)
        finally:
            db.close()

    return json.dumps({"error": f"action '{action}' desconhecida"})


async def main() -> None:
    srv = _get_server()

    @srv.list_tools()
    async def list_tools():
        return [SHOPPING_TOOL]

    @srv.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name != "shopping":
            return [TextContent(type="text", text=json.dumps({"error": f"tool '{name}' desconhecida"}))]
        action = arguments.get("action", "")
        params = arguments.get("params", {})
        result = _call_shopping(action, params)
        return [TextContent(type="text", text=result)]

    async with stdio_server() as (r, w):
        await srv.run(r, w, srv.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
