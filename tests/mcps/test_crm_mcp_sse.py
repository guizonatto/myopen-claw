from fastapi.testclient import TestClient
from mcps.crm_mcp.main import app


def test_sse_crm(monkeypatch):
    monkeypatch.setenv("MCP_API_KEY", "test-key")
    client = TestClient(app)
    response = client.post(
        "/sse",
        json={"operation": "search_contact", "query": "teste"},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "data:" in response.text
