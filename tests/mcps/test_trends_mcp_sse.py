import pytest
from httpx import AsyncClient
from mcps.trends_mcp.main import app

@pytest.mark.asyncio
async def test_sse_trends():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/sse", json={"operation": "test_op", "params": {}})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        # Checa se pelo menos um evento SSE foi retornado
        assert "data:" in response.text
