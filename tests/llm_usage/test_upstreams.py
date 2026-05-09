import os
import unittest


class UpstreamResolverTests(unittest.TestCase):
    def test_resolves_known_provider_to_openai_compatible_upstream(self):
        from llm_usage_telemetry.upstreams import parse_target_model, resolve_upstream

        env = {
            "GROQ_API_KEY": "groq-key",
        }

        target = parse_target_model("usage-router/groq/llama-3.1-8b-instant")
        upstream = resolve_upstream(target, env=env)

        self.assertEqual(target.provider, "groq")
        self.assertEqual(target.model, "llama-3.1-8b-instant")
        self.assertEqual(upstream.base_url, "https://api.groq.com/openai/v1")
        self.assertEqual(upstream.api_key, "groq-key")
        self.assertEqual(upstream.upstream_model, "llama-3.1-8b-instant")
        self.assertEqual(upstream.auth_mode, "bearer")

    def test_google_defaults_to_native_gemini_api_key_auth(self):
        from llm_usage_telemetry.upstreams import parse_target_model, resolve_upstream

        env = {"GEMINI_API_KEY": "g-key"}
        target = parse_target_model("usage-router/google/gemini-2.5-flash-lite")
        upstream = resolve_upstream(target, env=env)

        self.assertEqual(upstream.provider, "google")
        self.assertEqual(upstream.api_key, "g-key")
        self.assertEqual(upstream.base_url, "https://generativelanguage.googleapis.com/v1beta")
        self.assertEqual(upstream.auth_mode, "x-goog-api-key")

    def test_google_vertex_mode_uses_oauth_token_and_custom_endpoint(self):
        from llm_usage_telemetry.upstreams import parse_target_model, resolve_upstream

        env = {
            "GOOGLE_AUTH_MODE": "vertex_oauth",
            "GOOGLE_OAUTH_TOKEN": "oauth-token",
            "GOOGLE_OPENAI_BASE_URL": "https://aiplatform.googleapis.com/v1/projects/test/locations/global/endpoints/openapi",
        }
        target = parse_target_model("usage-router/google/gemini-2.5-flash-lite")
        upstream = resolve_upstream(target, env=env)

        self.assertEqual(upstream.api_key, "oauth-token")
        self.assertEqual(
            upstream.base_url,
            "https://aiplatform.googleapis.com/v1/projects/test/locations/global/endpoints/openapi",
        )
        self.assertEqual(upstream.auth_mode, "bearer")

    def test_rejects_non_usage_router_model_refs(self):
        from llm_usage_telemetry.upstreams import parse_target_model

        with self.assertRaises(ValueError):
            parse_target_model("groq/llama-3.1-8b-instant")

    def test_resolves_zai_to_openai_compatible_upstream(self):
        from llm_usage_telemetry.upstreams import parse_target_model, resolve_upstream

        env = {"ZAI_API_KEY": "zai-key"}
        target = parse_target_model("usage-router/zai/glm-4.6")
        upstream = resolve_upstream(target, env=env)

        self.assertEqual(target.provider, "zai")
        self.assertEqual(target.model, "glm-4.6")
        self.assertEqual(upstream.base_url, "https://api.z.ai/api/paas/v4")
        self.assertEqual(upstream.api_key, "zai-key")
        self.assertEqual(upstream.upstream_model, "glm-4.6")
        self.assertEqual(upstream.auth_mode, "bearer")


if __name__ == "__main__":
    unittest.main()
