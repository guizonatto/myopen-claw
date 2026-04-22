import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class UsageReportCliTests(unittest.TestCase):
    def test_script_runs_from_repo_root_and_renders_sections(self):
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmpdir:
            env = dict(os.environ)
            env["MODEL_USAGE_DB_PATH"] = str(Path(tmpdir) / "usage.sqlite3")
            env["MODEL_USAGE_REPORT_TIMEZONE"] = "America/Sao_Paulo"

            result = subprocess.run(
                [sys.executable, "scripts/model_usage_report.py"],
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Ultima hora", result.stdout)
        self.assertIn("Acumulado do dia", result.stdout)


if __name__ == "__main__":
    unittest.main()
