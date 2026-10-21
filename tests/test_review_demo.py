from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReviewDemoTests(unittest.TestCase):
    def test_demo_is_isolated_and_exposes_missing_data(self):
        parent = ROOT / ".tmp_tests"
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            output = Path(temporary) / "example"
            run = subprocess.run([sys.executable, str(ROOT / "tools/review_demo.py"), "--output", str(output)], cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stderr)
            summary = json.loads(run.stdout)
            self.assertEqual(summary["computed_scores"], 3)
            self.assertEqual(summary["computed_targets"], 3)
            self.assertEqual(summary["skipped_scores"], 1)
            self.assertEqual(summary["network_access"], "disabled")
            gap = next(row for row in summary["score_results"] if row["ticker"] == "DEMOGAP")
            self.assertEqual(gap["status"], "skipped")
            for key in ("config", "report", "csv", "dashboard"):
                path = Path(summary[key])
                self.assertTrue(path.is_relative_to(output))
                self.assertTrue(path.is_file())
            self.assertIn("SYNTHETIC REVIEW DEMO", Path(summary["dashboard"]).read_text(encoding="utf-8"))
            self.assertIn("DEMOA", Path(summary["csv"]).read_text(encoding="utf-8"))

    def test_existing_output_directory_is_preserved(self):
        parent = ROOT / ".tmp_tests"
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            output = Path(temporary)
            sentinel = output / "keep.txt"
            sentinel.write_text("keep", encoding="utf-8")
            run = subprocess.run([sys.executable, str(ROOT / "tools/review_demo.py"), "--output", str(output)], cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
            self.assertEqual(sorted(path.name for path in output.iterdir()), ["keep.txt"])


if __name__ == "__main__":
    unittest.main()
