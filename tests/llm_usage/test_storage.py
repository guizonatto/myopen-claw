import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


class UsageStorageTests(unittest.TestCase):
    def setUp(self):
        self.db_path = ":memory:"
        self.conn = None

    def tearDown(self):
        if self.conn is not None:
            self.conn.close()

    def test_aggregates_exact_estimated_and_unavailable_tokens(self):
        from llm_usage_telemetry.storage import (
            UsageEvent,
            connect_db,
            initialize_schema,
            record_usage_event,
            summarize_usage,
        )

        now = datetime(2026, 4, 16, 15, 0, tzinfo=timezone.utc)
        self.conn = connect_db(self.db_path)
        initialize_schema(self.conn)

        record_usage_event(
            self.conn,
            UsageEvent(
                timestamp=now - timedelta(minutes=10),
                service="openclaw",
                provider="groq",
                model="llama-3.1-8b-instant",
                request_kind="chat",
                success=True,
                http_status=200,
                latency_ms=120,
                attempt_number=1,
                input_tokens=100,
                output_tokens=40,
                total_tokens=140,
                token_accuracy="exact",
                origin_type="skill",
                origin_name="daily-content-creator",
                trigger_type="cron",
                trigger_name="Daily Content Creator — IA",
                agent_name="default",
                error_code=None,
                error_message=None,
                request_id="req-1",
                logical_request_id="logical-1",
            ),
        )
        record_usage_event(
            self.conn,
            UsageEvent(
                timestamp=now - timedelta(minutes=9),
                service="openclaw",
                provider="groq",
                model="llama-3.1-8b-instant",
                request_kind="chat",
                success=True,
                http_status=200,
                latency_ms=130,
                attempt_number=1,
                input_tokens=50,
                output_tokens=10,
                total_tokens=60,
                token_accuracy="estimated",
                origin_type="skill",
                origin_name="daily-content-creator",
                trigger_type="cron",
                trigger_name="Daily Content Creator — IA",
                agent_name="default",
                error_code=None,
                error_message=None,
                request_id="req-2",
                logical_request_id="logical-2",
            ),
        )
        record_usage_event(
            self.conn,
            UsageEvent(
                timestamp=now - timedelta(minutes=8),
                service="openclaw",
                provider="groq",
                model="llama-3.1-8b-instant",
                request_kind="chat",
                success=False,
                http_status=429,
                latency_ms=90,
                attempt_number=1,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                token_accuracy="unavailable",
                origin_type="skill",
                origin_name="daily-content-creator",
                trigger_type="cron",
                trigger_name="Daily Content Creator — IA",
                agent_name="default",
                error_code="rate_limited",
                error_message="Too many requests",
                request_id="req-3",
                logical_request_id="logical-3",
            ),
        )

        rows = summarize_usage(
            self.conn,
            start_at=now - timedelta(hours=1),
            end_at=now,
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.service, "openclaw")
        self.assertEqual(row.provider, "groq")
        self.assertEqual(row.model, "llama-3.1-8b-instant")
        self.assertEqual(row.attempts, 3)
        self.assertEqual(row.successes, 2)
        self.assertEqual(row.failures, 1)
        self.assertEqual(row.input_tokens_exact, 100)
        self.assertEqual(row.output_tokens_exact, 40)
        self.assertEqual(row.total_tokens_exact, 140)
        self.assertEqual(row.input_tokens_estimated, 50)
        self.assertEqual(row.output_tokens_estimated, 10)
        self.assertEqual(row.total_tokens_estimated, 60)
        self.assertEqual(row.token_quality, "mixed")

    def test_marks_and_detects_report_dispatches(self):
        from llm_usage_telemetry.storage import (
            connect_db,
            initialize_schema,
            mark_report_dispatched,
            was_report_dispatched,
        )

        bucket = datetime(2026, 4, 16, 14, 0, tzinfo=timezone.utc)
        self.conn = connect_db(self.db_path)
        initialize_schema(self.conn)

        self.assertFalse(
            was_report_dispatched(
                self.conn,
                report_key="hourly-discord",
                bucket_start=bucket,
                channel="discord",
                target="channel:abc123",
            )
        )

        mark_report_dispatched(
            self.conn,
            report_key="hourly-discord",
            bucket_start=bucket,
            channel="discord",
            target="channel:abc123",
        )

        self.assertTrue(
            was_report_dispatched(
                self.conn,
                report_key="hourly-discord",
                bucket_start=bucket,
                channel="discord",
                target="channel:abc123",
            )
        )

    def test_reports_estimated_quality_when_window_has_only_estimated_tokens(self):
        from llm_usage_telemetry.storage import (
            UsageEvent,
            connect_db,
            initialize_schema,
            record_usage_event,
            summarize_usage,
        )

        now = datetime(2026, 4, 16, 15, 0, tzinfo=timezone.utc)
        self.conn = connect_db(self.db_path)
        initialize_schema(self.conn)

        record_usage_event(
            self.conn,
            UsageEvent(
                timestamp=now - timedelta(minutes=5),
                service="memclaw",
                provider="ollama",
                model="qwen3-embedding:0.6b",
                request_kind="embedding",
                success=True,
                http_status=200,
                latency_ms=45,
                attempt_number=1,
                input_tokens=24,
                output_tokens=0,
                total_tokens=24,
                token_accuracy="estimated",
                origin_type="service",
                origin_name="memclaw",
                trigger_type=None,
                trigger_name=None,
                agent_name=None,
                error_code=None,
                error_message=None,
                request_id="req-4",
                logical_request_id="logical-4",
            ),
        )

        rows = summarize_usage(
            self.conn,
            start_at=now - timedelta(hours=1),
            end_at=now,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].token_quality, "estimated")

    def test_schema_adds_provenance_columns_for_existing_db(self):
        from llm_usage_telemetry.storage import connect_db, initialize_schema

        self.conn = connect_db(self.db_path)
        self.conn.execute(
            """
            CREATE TABLE usage_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              timestamp TEXT NOT NULL,
              service TEXT NOT NULL,
              provider TEXT NOT NULL,
              model TEXT NOT NULL,
              request_kind TEXT NOT NULL,
              success INTEGER NOT NULL,
              http_status INTEGER,
              latency_ms INTEGER,
              attempt_number INTEGER NOT NULL,
              input_tokens INTEGER,
              output_tokens INTEGER,
              total_tokens INTEGER,
              token_accuracy TEXT NOT NULL,
              error_code TEXT,
              error_message TEXT,
              request_id TEXT,
              logical_request_id TEXT
            )
            """
        )
        self.conn.commit()

        initialize_schema(self.conn)

        columns = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(usage_events)").fetchall()
        }
        self.assertIn("origin_type", columns)
        self.assertIn("origin_name", columns)
        self.assertIn("trigger_type", columns)
        self.assertIn("trigger_name", columns)
        self.assertIn("agent_name", columns)
        self.assertIn("input_chars", columns)
        self.assertIn("input_words", columns)
        self.assertIn("input_estimated_tokens", columns)
        self.assertIn("response_chars", columns)
        self.assertIn("response_words", columns)
        self.assertIn("response_estimated_tokens", columns)
        self.assertIn("request_payload", columns)
        self.assertIn("response_payload", columns)


if __name__ == "__main__":
    unittest.main()
