import pytest
from httpx import AsyncClient
from mcps.shopping_tracker_mcp.main import app

@pytest.mark.asyncio
async def test_sse_shopping():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/sse", json={"operation": "registrar_compra", "params": {"compras": [{"nome": "Arroz", "quantidade": 1}]}})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "data:" in response.text
