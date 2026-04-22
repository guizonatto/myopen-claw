from mcps.trends_mcp.main import app
import asyncio
import httpx
import os


def test_sse_trends():
    async def _run():
        os.environ["MCP_API_KEY"] = "test-key"
        headers = {"X-API-Key": "test-key"}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/sse", json={"operation": "test_op", "params": {}}, headers=headers)
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            assert "data:" in response.text

    asyncio.run(_run())
