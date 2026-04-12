import pytest
from httpx import AsyncClient
from mcps.crm_mcp.main import app

@pytest.mark.asyncio
async def test_sse_crm():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/sse", json={"operation": "add_contact", "params": {"nome": "Teste", "email": "t@t.com"}})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "data:" in response.text
