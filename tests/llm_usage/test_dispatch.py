import sqlite3
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch


class UsageDispatchTests(unittest.TestCase):
    def test_build_reporting_windows_uses_closed_previous_hour(self):
        from llm_usage_telemetry.dispatcher import build_reporting_windows

        now_utc = datetime(2026, 4, 16, 15, 5, tzinfo=timezone.utc)
        windows = build_reporting_windows(now_utc, "America/Sao_Paulo")

        self.assertEqual(windows.bucket_start_utc, datetime(2026, 4, 16, 14, 0, tzinfo=timezone.utc))
        self.assertEqual(windows.bucket_end_utc, datetime(2026, 4, 16, 15, 0, tzinfo=timezone.utc))
        self.assertIn("11:00-11:59", windows.bucket_label)

    def test_dispatch_hourly_report_is_idempotent_per_bucket(self):
        from llm_usage_telemetry.dispatcher import dispatch_hourly_report
        from llm_usage_telemetry.settings import TelemetrySettings

        async def run_test():
            class ConnectionProxy:
                def __init__(self) -> None:
                    self._conn = sqlite3.connect(":memory:")
                    self._conn.row_factory = sqlite3.Row

                def __getattr__(self, name):
                    return getattr(self._conn, name)

                def close(self) -> None:
                    return None

            conn = ConnectionProxy()
            settings = TelemetrySettings(
                db_path="unused-for-test",
                capture_payloads="off",
                proxy_timeout_seconds=5,
                estimate_chat_tokens=False,
                report_timezone="America/Sao_Paulo",
                retention_days=30,
                gateway_url="http://gateway.local",
                gateway_token="",
                gateway_password="",
                discord_bot_token="",
                discord_channel_id="discord-channel-id",
            )

            with (
                patch("llm_usage_telemetry.dispatcher.connect_db", return_value=conn),
                patch(
                    "llm_usage_telemetry.dispatcher._send_gateway_message",
                    return_value=True,
                ) as send_gateway_message,
            ):
                try:
                    first = await dispatch_hourly_report(
                        settings=settings,
                        now_utc=datetime(2026, 4, 16, 15, 5, tzinfo=timezone.utc),
                    )
                    second = await dispatch_hourly_report(
                        settings=settings,
                        now_utc=datetime(2026, 4, 16, 15, 5, tzinfo=timezone.utc),
                    )
                finally:
                    conn._conn.close()

            self.assertTrue(first)
            self.assertFalse(second)
            self.assertEqual(send_gateway_message.await_count, 1)

        import asyncio

        asyncio.run(run_test())

    def test_send_gateway_message_uses_tools_invoke(self):
        from llm_usage_telemetry.dispatcher import _send_gateway_message
        from llm_usage_telemetry.settings import TelemetrySettings

        async def run_test():
            settings = TelemetrySettings(
                db_path=":memory:",
                capture_payloads="off",
                proxy_timeout_seconds=5,
                estimate_chat_tokens=False,
                report_timezone="America/Sao_Paulo",
                retention_days=30,
                gateway_url="http://gateway.local",
                gateway_token="secret-token",
                gateway_password="",
                discord_bot_token="",
                discord_channel_id="123456789",
            )

            response = AsyncMock()
            response.status_code = 200

            client = AsyncMock()
            client.post = AsyncMock(return_value=response)
            client.__aenter__.return_value = client
            client.__aexit__.return_value = False

            with patch("llm_usage_telemetry.dispatcher.httpx.AsyncClient", return_value=client):
                sent = await _send_gateway_message(settings, "hello world")

            self.assertTrue(sent)
            client.post.assert_awaited_once_with(
                "http://gateway.local/tools/invoke",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer secret-token",
                },
                json={
                    "tool": "message",
                    "action": "send",
                    "args": {
                        "channel": "discord",
                        "target": "channel:123456789",
                        "message": "hello world",
                    },
                    "sessionKey": "main",
                },
            )

        import asyncio

        asyncio.run(run_test())

    def test_split_discord_content_chunks_on_line_boundaries(self):
        from llm_usage_telemetry.dispatcher import _split_discord_content

        content = "header\n" + "\n".join([f"line-{index}-{'x' * 20}" for index in range(12)])
        chunks = _split_discord_content(content, limit=120)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 120 for chunk in chunks))
        self.assertEqual("\n".join(chunks), content)

    def test_send_gateway_message_falls_back_to_legacy_api_message(self):
        from llm_usage_telemetry.dispatcher import _send_gateway_message
        from llm_usage_telemetry.settings import TelemetrySettings

        async def run_test():
            settings = TelemetrySettings(
                db_path=":memory:",
                capture_payloads="off",
                proxy_timeout_seconds=5,
                estimate_chat_tokens=False,
                report_timezone="America/Sao_Paulo",
                retention_days=30,
                gateway_url="http://gateway.local/",
                gateway_token="",
                gateway_password="",
                discord_bot_token="",
                discord_channel_id="123456789",
            )

            tools_response = AsyncMock()
            tools_response.status_code = 404
            legacy_response = AsyncMock()
            legacy_response.status_code = 200

            client = AsyncMock()
            client.post = AsyncMock(side_effect=[tools_response, legacy_response])
            client.__aenter__.return_value = client
            client.__aexit__.return_value = False

            with patch("llm_usage_telemetry.dispatcher.httpx.AsyncClient", return_value=client):
                sent = await _send_gateway_message(settings, "hello world")

            self.assertTrue(sent)
            self.assertEqual(client.post.await_count, 2)
            first_call = client.post.await_args_list[0]
            second_call = client.post.await_args_list[1]
            self.assertEqual(first_call.args[0], "http://gateway.local/tools/invoke")
            self.assertEqual(second_call.args[0], "http://gateway.local/api/message")
            self.assertEqual(
                second_call.kwargs["json"],
                {
                    "channel": "discord",
                    "to": "channel:123456789",
                    "content": "hello world",
                },
            )

        import asyncio

        asyncio.run(run_test())

    def test_send_gateway_message_retries_with_gateway_password_after_401(self):
        from llm_usage_telemetry.dispatcher import _send_gateway_message
        from llm_usage_telemetry.settings import TelemetrySettings

        async def run_test():
            settings = TelemetrySettings(
                db_path=":memory:",
                capture_payloads="off",
                proxy_timeout_seconds=5,
                estimate_chat_tokens=False,
                report_timezone="America/Sao_Paulo",
                retention_days=30,
                gateway_url="http://gateway.local",
                gateway_token="stale-token",
                gateway_password="real-password",
                discord_bot_token="",
                discord_channel_id="123456789",
            )

            unauthorized = AsyncMock()
            unauthorized.status_code = 401
            success = AsyncMock()
            success.status_code = 200

            client = AsyncMock()
            client.post = AsyncMock(side_effect=[unauthorized, success])
            client.__aenter__.return_value = client
            client.__aexit__.return_value = False

            with patch("llm_usage_telemetry.dispatcher.httpx.AsyncClient", return_value=client):
                sent = await _send_gateway_message(settings, "hello world")

            self.assertTrue(sent)
            self.assertEqual(client.post.await_count, 2)
            first_call = client.post.await_args_list[0]
            second_call = client.post.await_args_list[1]
            self.assertEqual(
                first_call.kwargs["headers"]["Authorization"],
                "Bearer real-password",
            )
            self.assertEqual(
                second_call.kwargs["headers"]["Authorization"],
                "Bearer stale-token",
            )

        import asyncio

        asyncio.run(run_test())

    def test_send_gateway_message_uses_direct_discord_api_when_bot_token_is_available(self):
        from llm_usage_telemetry.dispatcher import _send_gateway_message
        from llm_usage_telemetry.settings import TelemetrySettings

        async def run_test():
            settings = TelemetrySettings(
                db_path=":memory:",
                capture_payloads="off",
                proxy_timeout_seconds=5,
                estimate_chat_tokens=False,
                report_timezone="America/Sao_Paulo",
                retention_days=30,
                gateway_url="http://gateway.local",
                gateway_token="stale-token",
                gateway_password="real-password",
                discord_bot_token="discord-bot-token",
                discord_channel_id="123456789",
            )

            response = AsyncMock()
            response.status_code = 200

            client = AsyncMock()
            client.post = AsyncMock(return_value=response)
            client.__aenter__.return_value = client
            client.__aexit__.return_value = False

            with patch("llm_usage_telemetry.dispatcher.httpx.AsyncClient", return_value=client):
                sent = await _send_gateway_message(settings, "hello discord")

            self.assertTrue(sent)
            client.post.assert_awaited_once_with(
                "https://discord.com/api/v10/channels/123456789/messages",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bot discord-bot-token",
                },
                json={"content": "hello discord"},
            )

        import asyncio

        asyncio.run(run_test())

    def test_send_gateway_message_splits_long_discord_reports(self):
        from llm_usage_telemetry.dispatcher import _send_gateway_message
        from llm_usage_telemetry.settings import TelemetrySettings

        async def run_test():
            settings = TelemetrySettings(
                db_path=":memory:",
                capture_payloads="off",
                proxy_timeout_seconds=5,
                estimate_chat_tokens=False,
                report_timezone="America/Sao_Paulo",
                retention_days=30,
                gateway_url="http://gateway.local",
                gateway_token="stale-token",
                gateway_password="real-password",
                discord_bot_token="discord-bot-token",
                discord_channel_id="123456789",
            )

            response = AsyncMock()
            response.status_code = 200

            client = AsyncMock()
            client.post = AsyncMock(return_value=response)
            client.__aenter__.return_value = client
            client.__aexit__.return_value = False

            content = "header\n" + "\n".join([f"line-{index}-{'x' * 120}" for index in range(20)])

            with patch("llm_usage_telemetry.dispatcher.httpx.AsyncClient", return_value=client):
                sent = await _send_gateway_message(settings, content)

            self.assertTrue(sent)
            self.assertGreater(client.post.await_count, 1)
            for call in client.post.await_args_list:
                self.assertLessEqual(len(call.kwargs["json"]["content"]), 1900)

        import asyncio

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
