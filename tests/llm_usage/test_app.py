import unittest

from fastapi.testclient import TestClient


class FakeProxyService:
    def __init__(self):
        self.calls = []

    async def handle_openai_request(self, request_kind, payload, headers):
        self.calls.append(
            {
                "request_kind": request_kind,
                "payload": payload,
                "headers": dict(headers),
            }
        )
        return {
            "status_code": 200,
            "body": {
                "id": "cmpl-test",
                "object": "chat.completion",
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
            },
        }

    async def handle_ollama_embedding(self, payload, headers):
        self.calls.append(
            {
                "request_kind": "ollama-embedding",
                "payload": payload,
                "headers": dict(headers),
            }
        )
        return {
            "status_code": 200,
            "body": {"embedding": [0.1, 0.2, 0.3]},
        }


class UsageProxyAppTests(unittest.TestCase):
    def test_healthz_returns_ok(self):
        from llm_usage_telemetry.app import create_app

        client = TestClient(create_app(proxy_service=FakeProxyService()))
        response = client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_chat_completions_route_forwards_payload_and_headers(self):
        from llm_usage_telemetry.app import create_app

        fake = FakeProxyService()
        client = TestClient(create_app(proxy_service=fake))

        response = client.post(
            "/v1/chat/completions",
            headers={
                "x-usage-service": "openclaw",
                "x-target-provider": "groq",
                "x-target-model": "llama-3.1-8b-instant",
            },
            json={
                "model": "usage-router/groq/llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": "oi"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0]["request_kind"], "chat")
        self.assertEqual(fake.calls[0]["payload"]["model"], "usage-router/groq/llama-3.1-8b-instant")
        self.assertEqual(fake.calls[0]["headers"]["x-usage-service"], "openclaw")

    def test_service_scoped_route_injects_service_header(self):
        from llm_usage_telemetry.app import create_app

        fake = FakeProxyService()
        client = TestClient(create_app(proxy_service=fake))

        response = client.post(
            "/memclaw/v1/embeddings",
            json={
                "model": "usage-router/ollama/qwen3-embedding:0.6b",
                "input": "abc",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0]["request_kind"], "embedding")
        self.assertEqual(fake.calls[0]["headers"]["x-usage-service"], "memclaw")
        self.assertEqual(fake.calls[0]["headers"]["x-usage-origin-type"], "service")
        self.assertEqual(fake.calls[0]["headers"]["x-usage-origin-name"], "memclaw")


if __name__ == "__main__":
    unittest.main()
