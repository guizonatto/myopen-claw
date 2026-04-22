import unittest


class UsageReportingTests(unittest.TestCase):
    def test_formats_exact_mixed_and_na_token_labels(self):
        from llm_usage_telemetry.reporting import format_token_quality

        self.assertEqual(format_token_quality(140, 0), "140 (exact)")
        self.assertEqual(format_token_quality(0, 60), "60 (estimated)")
        self.assertEqual(
            format_token_quality(140, 60),
            "200 (mixed: 140 exact + 60 estimated)",
        )
        self.assertEqual(format_token_quality(0, 0), "n/a")

    def test_builds_discord_report_with_both_sections(self):
        from llm_usage_telemetry.reporting import UsageSummaryRow, build_discord_report

        row = UsageSummaryRow(
            service="openclaw",
            provider="groq",
            model="llama-3.1-8b-instant",
            request_kind="chat",
            attempts=3,
            successes=2,
            failures=1,
            rpm_avg=0.05,
            rpm_peak=1,
            input_tokens_exact=100,
            output_tokens_exact=40,
            total_tokens_exact=140,
            input_tokens_estimated=50,
            output_tokens_estimated=10,
            total_tokens_estimated=60,
            token_quality="mixed",
        )

        report = build_discord_report(
            last_hour_rows=[row],
            day_rows=[row],
            timezone_name="America/Sao_Paulo",
            bucket_label="2026-04-16 11:00-11:59",
        )

        self.assertIn("Ultima hora", report)
        self.assertIn("Acumulado do dia", report)
        self.assertIn("openclaw", report)
        self.assertIn("groq/llama-3.1-8b-instant", report)
        self.assertIn("mixed", report)


if __name__ == "__main__":
    unittest.main()
