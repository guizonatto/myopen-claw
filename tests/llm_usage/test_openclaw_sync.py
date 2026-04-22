import json
import os
import tempfile
import unittest


class OpenClawSyncTests(unittest.TestCase):
    def setUp(self):
        self.conn = None

    def tearDown(self):
        if self.conn is not None:
            self.conn.close()

    def test_sync_seeds_allowlist_and_disables_extras_when_strict(self):
        from llm_usage_telemetry.openclaw_sync import (
            MIRROR_DISABLED_REASON,
            sync_model_limits_from_openclaw_config_path,
        )
        from llm_usage_telemetry.storage import connect_db, get_model_limits, initialize_schema, upsert_model_limits

        self.conn = connect_db(":memory:")
        initialize_schema(self.conn)

        upsert_model_limits(self.conn, "google", "gemini-2-flash", rpm=10)

        openclaw_config = {
            "agents": {
                "defaults": {
                    "model": {
                        "primary": "usage-router/groq/llama-3.1-8b-instant",
                        "fallbacks": ["usage-router/google/gemini-2.5-flash"],
                    },
                    "models": {
                        "usage-router/groq/llama-3.1-8b-instant": {"alias": "llama"},
                        "usage-router/google/gemini-2.5-flash": {"alias": "gemini"},
                    },
                }
            }
        }

        fd, path = tempfile.mkstemp(suffix=".openclaw.json")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(openclaw_config, handle)

            result = sync_model_limits_from_openclaw_config_path(
                self.conn,
                path,
                default_rpm_by_provider={"groq": 30, "mistral": 20, "ollama": 60},
                rpm_fallback=10,
                strict=True,
            )
        finally:
            os.unlink(path)

        self.assertTrue(result["ok"])
        self.assertEqual(result["allowlist_models"], 2)
        self.assertEqual(result["created"], 2)

        groq_limits = get_model_limits(self.conn, "groq", "llama-3.1-8b-instant")
        self.assertIsNotNone(groq_limits)
        self.assertEqual(groq_limits.rpm, 30)

        gemini_limits = get_model_limits(self.conn, "google", "gemini-2.5-flash")
        self.assertIsNotNone(gemini_limits)
        self.assertEqual(gemini_limits.rpm, 10)

        extra_limits = get_model_limits(self.conn, "google", "gemini-2-flash")
        self.assertIsNotNone(extra_limits)
        self.assertFalse(extra_limits.enabled)
        self.assertEqual(extra_limits.disabled_reason, MIRROR_DISABLED_REASON)

    def test_sync_applies_model_limits_catalog_when_provided(self):
        from llm_usage_telemetry.openclaw_sync import sync_model_limits_from_openclaw_config_path
        from llm_usage_telemetry.storage import connect_db, get_model_limits, initialize_schema

        self.conn = connect_db(":memory:")
        initialize_schema(self.conn)

        openclaw_config = {
            "agents": {
                "defaults": {
                    "model": {
                        "primary": "usage-router/groq/llama-3.1-8b-instant",
                        "fallbacks": ["usage-router/google/gemini-2.5-flash"],
                    },
                    "models": {
                        "usage-router/groq/llama-3.1-8b-instant": {"alias": "llama"},
                        "usage-router/google/gemini-2.5-flash": {"alias": "gemini"},
                    },
                }
            }
        }
        catalog = {
            "version": "test",
            "providers": {
                "google": {"defaults": {"rpm": 5, "tpm": 250000, "rpd": 20}},
                "groq": {"defaults": {"rpm": 30}},
            },
        }

        fd_cfg, cfg_path = tempfile.mkstemp(suffix=".openclaw.json")
        os.close(fd_cfg)
        fd_cat, cat_path = tempfile.mkstemp(suffix=".model-limits.json")
        os.close(fd_cat)
        try:
            with open(cfg_path, "w", encoding="utf-8") as handle:
                json.dump(openclaw_config, handle)
            with open(cat_path, "w", encoding="utf-8") as handle:
                json.dump(catalog, handle)

            result = sync_model_limits_from_openclaw_config_path(
                self.conn,
                cfg_path,
                default_rpm_by_provider={"groq": 30, "mistral": 20, "ollama": 60},
                rpm_fallback=10,
                strict=False,
                catalog_path=cat_path,
            )
        finally:
            os.unlink(cfg_path)
            os.unlink(cat_path)

        self.assertTrue(result["ok"], msg=result)
        self.assertTrue(result.get("catalog", {}).get("loaded"), msg=result)

        groq_limits = get_model_limits(self.conn, "groq", "llama-3.1-8b-instant")
        self.assertIsNotNone(groq_limits)
        self.assertEqual(groq_limits.rpm, 30)

        gemini_limits = get_model_limits(self.conn, "google", "gemini-2.5-flash")
        self.assertIsNotNone(gemini_limits)
        self.assertEqual(gemini_limits.rpm, 5)
        self.assertEqual(gemini_limits.rpd, 20)
        self.assertEqual(gemini_limits.tpm, 250000)

    def test_sync_overrides_placeholder_rpm_when_catalog_differs(self):
        from llm_usage_telemetry.openclaw_sync import sync_model_limits_from_openclaw_config_path
        from llm_usage_telemetry.storage import connect_db, get_model_limits, initialize_schema, upsert_model_limits

        self.conn = connect_db(":memory:")
        initialize_schema(self.conn)

        # Simulate old seed using rpm_fallback (10) before the catalog was introduced.
        upsert_model_limits(self.conn, "google", "gemini-2.5-flash", rpm=10)

        openclaw_config = {
            "agents": {
                "defaults": {
                    "model": {
                        "primary": "usage-router/google/gemini-2.5-flash",
                        "fallbacks": [],
                    },
                    "models": {
                        "usage-router/google/gemini-2.5-flash": {"alias": "gemini"},
                    },
                }
            }
        }
        catalog = {
            "version": "test",
            "providers": {
                "google": {"defaults": {"rpm": 5, "tpm": 250000, "rpd": 20}},
            },
        }

        fd_cfg, cfg_path = tempfile.mkstemp(suffix=".openclaw.json")
        os.close(fd_cfg)
        fd_cat, cat_path = tempfile.mkstemp(suffix=".model-limits.json")
        os.close(fd_cat)
        try:
            with open(cfg_path, "w", encoding="utf-8") as handle:
                json.dump(openclaw_config, handle)
            with open(cat_path, "w", encoding="utf-8") as handle:
                json.dump(catalog, handle)

            result = sync_model_limits_from_openclaw_config_path(
                self.conn,
                cfg_path,
                default_rpm_by_provider={"groq": 30, "mistral": 20, "ollama": 60},
                rpm_fallback=10,
                strict=False,
                catalog_path=cat_path,
            )
        finally:
            os.unlink(cfg_path)
            os.unlink(cat_path)

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result.get("rpm_overridden"), 1, msg=result)

        gemini_limits = get_model_limits(self.conn, "google", "gemini-2.5-flash")
        self.assertIsNotNone(gemini_limits)
        self.assertEqual(gemini_limits.rpm, 5)
        self.assertEqual(gemini_limits.rpd, 20)
        self.assertEqual(gemini_limits.tpm, 250000)
