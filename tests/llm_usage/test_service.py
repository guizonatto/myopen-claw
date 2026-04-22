import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class _FakeAsyncClient:
    response = None
    error = None
    last_request = None

    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.get("timeout")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, json=None):
        type(self).last_request = {
            "url": url,
            "headers": dict(headers or {}),
            "json": dict(json or {}),
        }
        if type(self).error is not None:
            raise type(self).error
        return type(self).response


class MetricsProxyServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        return None

    def tearDown(self):
        return None

    def _settings(self, db_name="usage.sqlite3"):
        from llm_usage_telemetry.settings import TelemetrySettings

        return TelemetrySettings(
            db_path=":memory:",
            capture_payloads="off",
            proxy_timeout_seconds=5,
            estimate_chat_tokens=False,
            report_timezone="America/Sao_Paulo",
            retention_days=30,
            gateway_url="http://gateway.local",
            gateway_token="",
            gateway_password="",
            discord_bot_token="",
            discord_channel_id="",
        )

    async def test_records_exact_usage_for_successful_chat_completion(self):
        from llm_usage_telemetry.service import MetricsProxyService
        from llm_usage_telemetry.storage import summarize_usage

        _FakeAsyncClient.response = _FakeResponse(
            200,
            {
                "id": "resp-1",
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 3,
                    "total_tokens": 13,
                },
            },
        )
        _FakeAsyncClient.error = None
        _FakeAsyncClient.last_request = None

        service = MetricsProxyService(self._settings("usage-chat.sqlite3"))
        try:
            with patch("llm_usage_telemetry.service.httpx.AsyncClient", _FakeAsyncClient):
                result = await service.handle_openai_request(
                    request_kind="chat",
                    payload={
                        "model": "usage-router/groq/llama-3.1-8b-instant",
                        "messages": [{"role": "user", "content": "oi"}],
                    },
                    headers={"x-usage-service": "openclaw"},
                )

            rows = summarize_usage(
                service.conn,
                start_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
                end_at=datetime(2100, 1, 1, tzinfo=timezone.utc),
            )
        finally:
            service.close()

        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].service, "openclaw")
        self.assertEqual(rows[0].provider, "groq")
        self.assertEqual(rows[0].model, "llama-3.1-8b-instant")
        self.assertEqual(rows[0].total_tokens_exact, 13)
        self.assertEqual(rows[0].token_quality, "exact")
        self.assertEqual(_FakeAsyncClient.last_request["json"]["model"], "llama-3.1-8b-instant")

    async def test_clamps_max_completion_tokens_when_model_limit_present(self):
        from llm_usage_telemetry.service import MetricsProxyService
        from llm_usage_telemetry.storage import upsert_model_limits

        _FakeAsyncClient.response = _FakeResponse(200, {"id": "resp-2"})
        _FakeAsyncClient.error = None
        _FakeAsyncClient.last_request = None

        service = MetricsProxyService(self._settings("usage-clamp.sqlite3"))
        try:
            upsert_model_limits(
                service.conn,
                "groq",
                "llama-3.1-8b-instant",
                max_output_tokens=7,
            )
            with patch("llm_usage_telemetry.service.httpx.AsyncClient", _FakeAsyncClient):
                result = await service.handle_openai_request(
                    request_kind="chat",
                    payload={
                        "model": "usage-router/groq/llama-3.1-8b-instant",
                        "messages": [{"role": "user", "content": "oi"}],
                        "max_completion_tokens": 32,
                    },
                    headers={"x-usage-service": "openclaw"},
                )
        finally:
            service.close()

        self.assertEqual(result.status_code, 200)
        self.assertEqual(_FakeAsyncClient.last_request["json"]["max_completion_tokens"], 7)

    async def test_rate_limiter_returns_429_without_calling_upstream(self):
        from llm_usage_telemetry.service import MetricsProxyService
        from llm_usage_telemetry.storage import upsert_model_limits

        _FakeAsyncClient.response = _FakeResponse(200, {"id": "resp-3"})
        _FakeAsyncClient.error = None
        _FakeAsyncClient.last_request = None

        service = MetricsProxyService(self._settings("usage-ratelimit.sqlite3"))
        try:
            upsert_model_limits(
                service.conn,
                "groq",
                "llama-3.1-8b-instant",
                rpm=0,
            )
            with patch("llm_usage_telemetry.service.httpx.AsyncClient", _FakeAsyncClient):
                result = await service.handle_openai_request(
                    request_kind="chat",
                    payload={
                        "model": "usage-router/groq/llama-3.1-8b-instant",
                        "messages": [{"role": "user", "content": "oi"}],
                    },
                    headers={"x-usage-service": "openclaw"},
                )
        finally:
            service.close()

        self.assertEqual(result.status_code, 429)
        self.assertIsNotNone(result.body.get("error"))
        self.assertIsNone(_FakeAsyncClient.last_request)

    async def test_records_estimated_tokens_for_embedding_without_usage(self):
        from llm_usage_telemetry.service import MetricsProxyService
        from llm_usage_telemetry.storage import summarize_usage

        _FakeAsyncClient.response = _FakeResponse(
            200,
            {
                "data": [{"embedding": [0.1, 0.2]}],
            },
        )
        _FakeAsyncClient.error = None
        _FakeAsyncClient.last_request = None

        service = MetricsProxyService(self._settings("usage-embedding.sqlite3"))
        try:
            with patch("llm_usage_telemetry.service.httpx.AsyncClient", _FakeAsyncClient):
                result = await service.handle_openai_request(
                    request_kind="embedding",
                    payload={
                        "model": "usage-router/ollama/qwen3-embedding:0.6b",
                        "input": "texto curto",
                    },
                    headers={"x-usage-service": "memclaw"},
                )

            rows = summarize_usage(
                service.conn,
                start_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
                end_at=datetime(2100, 1, 1, tzinfo=timezone.utc),
            )
        finally:
            service.close()

        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].service, "memclaw")
        self.assertEqual(rows[0].provider, "ollama")
        self.assertGreater(rows[0].total_tokens_estimated, 0)
        self.assertEqual(rows[0].token_quality, "estimated")

    async def test_records_estimated_tokens_for_successful_chat_without_usage_when_flag_enabled(self):
        from llm_usage_telemetry.service import MetricsProxyService
        from llm_usage_telemetry.storage import summarize_usage

        _FakeAsyncClient.response = _FakeResponse(
            200,
            {
                "id": "resp-estimated-chat",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Resposta curta estimada.",
                        },
                    }
                ],
            },
        )
        _FakeAsyncClient.error = None
        _FakeAsyncClient.last_request = None

        settings = self._settings("usage-chat-estimated.sqlite3")
        settings.estimate_chat_tokens = True
        service = MetricsProxyService(settings)
        try:
            with patch("llm_usage_telemetry.service.httpx.AsyncClient", _FakeAsyncClient):
                result = await service.handle_openai_request(
                    request_kind="chat",
                    payload={
                        "model": "usage-router/mistral/mistral-large-latest",
                        "messages": [{"role": "user", "content": "Me responda em uma frase curta."}],
                    },
                    headers={"x-usage-service": "openclaw"},
                )

            rows = summarize_usage(
                service.conn,
                start_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
                end_at=datetime(2100, 1, 1, tzinfo=timezone.utc),
            )
        finally:
            service.close()

        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(rows), 1)
        self.assertGreater(rows[0].total_tokens_estimated, 0)
        self.assertEqual(rows[0].total_tokens_exact, 0)
        self.assertEqual(rows[0].token_quality, "estimated")

    async def test_captures_full_payloads_and_size_metrics_when_enabled(self):
        from llm_usage_telemetry.service import MetricsProxyService

        _FakeAsyncClient.response = _FakeResponse(
            200,
            {
                "id": "resp-capture",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Resposta auditada completa.",
                        },
                    }
                ],
            },
        )
        _FakeAsyncClient.error = None
        _FakeAsyncClient.last_request = None

        settings = self._settings("usage-capture.sqlite3")
        settings.capture_payloads = "full"
        settings.estimate_chat_tokens = True
        service = MetricsProxyService(settings)
        try:
            with patch("llm_usage_telemetry.service.httpx.AsyncClient", _FakeAsyncClient):
                result = await service.handle_openai_request(
                    request_kind="chat",
                    payload={
                        "model": "usage-router/mistral/mistral-large-latest",
                        "messages": [{"role": "user", "content": "Audite esta chamada por favor."}],
                    },
                    headers={"x-usage-service": "openclaw"},
                )

            row = service.conn.execute(
                """
                select
                  input_chars, input_words, input_estimated_tokens,
                  response_chars, response_words, response_estimated_tokens,
                  request_payload, response_payload
                from usage_events
                order by id desc
                limit 1
                """
            ).fetchone()
        finally:
            service.close()

        self.assertEqual(result.status_code, 200)
        self.assertGreater(row["input_chars"], 0)
        self.assertGreater(row["input_words"], 0)
        self.assertGreater(row["input_estimated_tokens"], 0)
        self.assertGreater(row["response_chars"], 0)
        self.assertGreater(row["response_words"], 0)
        self.assertGreater(row["response_estimated_tokens"], 0)
        self.assertIn("Audite esta chamada por favor.", row["request_payload"])
        self.assertIn("Resposta auditada completa.", row["response_payload"])

    async def test_records_failures_for_http_errors_and_timeouts(self):
        from llm_usage_telemetry.service import MetricsProxyService
        from llm_usage_telemetry.storage import summarize_usage

        for response_status in (429, 500):
            with self.subTest(status=response_status):
                _FakeAsyncClient.response = _FakeResponse(
                    response_status,
                    {
                        "error": {
                            "code": f"http_{response_status}",
                            "message": "upstream failed",
                        }
                    },
                )
                _FakeAsyncClient.error = None
                _FakeAsyncClient.last_request = None

                service = MetricsProxyService(self._settings(f"usage-http-{response_status}.sqlite3"))
                try:
                    with patch("llm_usage_telemetry.service.httpx.AsyncClient", _FakeAsyncClient):
                        result = await service.handle_openai_request(
                            request_kind="chat",
                            payload={
                                "model": "usage-router/groq/llama-3.1-8b-instant",
                                "messages": [{"role": "user", "content": "oi"}],
                            },
                            headers={"x-usage-service": "openclaw"},
                        )

                    rows = summarize_usage(
                        service.conn,
                        start_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
                        end_at=datetime(2100, 1, 1, tzinfo=timezone.utc),
                    )
                finally:
                    service.close()

                self.assertEqual(result.status_code, response_status)
                self.assertEqual(rows[0].failures, 1)
                self.assertEqual(rows[0].attempts, 1)
                self.assertEqual(rows[0].token_quality, "n/a")

        _FakeAsyncClient.response = None
        _FakeAsyncClient.error = httpx.TimeoutException("timed out")
        _FakeAsyncClient.last_request = None

        service = MetricsProxyService(self._settings("usage-timeout.sqlite3"))
        try:
            with patch("llm_usage_telemetry.service.httpx.AsyncClient", _FakeAsyncClient):
                result = await service.handle_openai_request(
                    request_kind="chat",
                    payload={
                        "model": "usage-router/groq/llama-3.1-8b-instant",
                        "messages": [{"role": "user", "content": "oi"}],
                    },
                    headers={"x-usage-service": "openclaw"},
                )

            rows = summarize_usage(
                service.conn,
                start_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
                end_at=datetime(2100, 1, 1, tzinfo=timezone.utc),
            )
        finally:
            service.close()

        self.assertEqual(result.status_code, 504)
        self.assertEqual(rows[0].failures, 1)
        self.assertEqual(rows[0].attempts, 1)
        self.assertEqual(rows[0].token_quality, "n/a")

class PayloadNormalizationTests(unittest.TestCase):
    def test_google_openai_compat_url_avoids_duplicate_v1_segment(self):
        from llm_usage_telemetry.service import _join_upstream_url

        self.assertEqual(
            _join_upstream_url(
                "https://generativelanguage.googleapis.com/v1beta/openai",
                "/v1/chat/completions",
            ),
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        )

    def test_google_payload_strips_incompatible_fields(self):
        from llm_usage_telemetry.service import _normalize_upstream_payload

        payload = _normalize_upstream_payload(
            provider="google",
            payload={
                "model": "usage-router/google/gemini-2.5-flash",
                "messages": [{"role": "user", "content": "oi"}],
                "store": True,
                "seed": 123,
            },
        )

        self.assertNotIn("store", payload)
        self.assertNotIn("seed", payload)
        self.assertEqual(payload["model"], "usage-router/google/gemini-2.5-flash")

    def test_google_native_chat_request_uses_interactions_shape(self):
        from llm_usage_telemetry.service import _build_google_native_request

        url, body = _build_google_native_request(
            request_kind="chat",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-2.5-flash",
            payload={
                "messages": [
                    {"role": "system", "content": "You are concise."},
                    {"role": "user", "content": "Say hi"},
                    {"role": "assistant", "content": "Hello."},
                    {"role": "user", "content": "Now say bye"},
                ],
                "temperature": 0.2,
                "max_completion_tokens": 32,
            },
        )

        self.assertEqual(
            url,
            "https://generativelanguage.googleapis.com/v1beta/interactions",
        )
        self.assertEqual(body["model"], "gemini-2.5-flash")
        self.assertEqual(body["input"][0]["role"], "user")
        self.assertIn("You are concise.", body["input"][0]["content"])
        self.assertEqual(body["input"][1]["role"], "model")
        self.assertEqual(body["input"][1]["content"], "Hello.")
        self.assertEqual(body["input"][2]["role"], "user")
        self.assertEqual(body["input"][2]["content"], "Now say bye")

    def test_non_openai_payload_strips_store(self):
        from llm_usage_telemetry.service import _normalize_upstream_payload

        payload = _normalize_upstream_payload(
            provider="groq",
            payload={"model": "x", "messages": [{"role": "user", "content": "oi"}], "store": True},
        )

        self.assertNotIn("store", payload)

    def test_error_extraction_handles_google_list_shape(self):
        from llm_usage_telemetry.service import _extract_error_details

        code, message = _extract_error_details(
            status_code=400,
            response_json=[
                {
                    "error": {
                        "code": 400,
                        "message": 'Invalid JSON payload received. Unknown name "store": Cannot find field.',
                        "status": "INVALID_ARGUMENT",
                    }
                }
            ],
            response_text="",
        )

        self.assertEqual(code, "400")
        self.assertIn("Unknown name", message)

    def test_google_native_chat_response_is_translated_to_openai_shape(self):
        from llm_usage_telemetry.service import _translate_google_native_response

        translated = _translate_google_native_response(
            request_kind="chat",
            model="gemini-2.5-flash",
            response_json={
                "id": "interaction-123",
                "outputs": [
                    {"type": "google_search_result", "text": ""},
                    {
                        "type": "text",
                        "text": "Hi there.",
                    }
                ],
                "usage_metadata": {
                    "input_tokens": 11,
                    "output_tokens": 3,
                    "totalTokenCount": 14,
                },
            },
        )

        self.assertEqual(translated["id"], "interaction-123")
        self.assertEqual(translated["choices"][0]["message"]["content"], "Hi there.")
        self.assertEqual(translated["usage"]["prompt_tokens"], 11)
        self.assertEqual(translated["usage"]["completion_tokens"], 3)
        self.assertEqual(translated["usage"]["total_tokens"], 14)

    def test_google_native_embedding_request_uses_embed_content_shape(self):
        from llm_usage_telemetry.service import _build_google_native_request

        url, body = _build_google_native_request(
            request_kind="embedding",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-embedding-001",
            payload={"input": "hello world"},
        )

        self.assertEqual(
            url,
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent",
        )
        self.assertEqual(body["model"], "models/gemini-embedding-001")
        self.assertEqual(body["content"]["parts"][0]["text"], "hello world")

    def test_strips_telemetry_marker_and_infers_skill_from_prompt(self):
        from llm_usage_telemetry.service import _infer_skill_name, _sanitize_payload_provenance

        payload, marker_meta, prompt_text = _sanitize_payload_provenance(
            {
                "model": "usage-router/groq/llama-3.1-8b-instant",
                "messages": [
                    {
                        "role": "user",
                        "content": "[telemetry trigger_type=cron trigger_name=Daily%20Content%20Creator%20%E2%80%94%20IA] Execute a skill daily-content-creator com topic='IA'.",
                    }
                ],
            }
        )

        self.assertEqual(marker_meta["trigger_type"], "cron")
        self.assertEqual(marker_meta["trigger_name"], "Daily Content Creator — IA")
        self.assertNotIn("[telemetry", payload["messages"][0]["content"])
        self.assertEqual(_infer_skill_name(prompt_text), "daily-content-creator")


if __name__ == "__main__":
    unittest.main()
