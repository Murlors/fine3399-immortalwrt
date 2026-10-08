import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ToolEntrypointTests(unittest.TestCase):
    def test_archive_tools_work_when_run_as_scripts(self):
        for name in ("extract_ophub_headers.py", "import_ophub_kernel.py"):
            with self.subTest(name=name):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "tools" / name), "--help"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
