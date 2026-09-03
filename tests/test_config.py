import os
import subprocess
import sys
import unittest
from pathlib import Path

repoRoot = Path(__file__).resolve().parent.parent


class ConfigTests(unittest.TestCase):
    def test_blank_download_settings_use_defaults(self) -> None:
        env = os.environ.copy()
        env["DOWNLOADS_DIR"] = ""
        env["DOWNLOADS_URL"] = ""

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from sandrone import config; "
                    "print(config.downloadsDir.resolve()); "
                    "print(config.downloadsUrl)"
                ),
            ],
            cwd=repoRoot,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

        directory, url = result.stdout.splitlines()
        self.assertEqual(Path(directory), repoRoot / "downloads")
        self.assertEqual(url, "http://localhost:2020")


if __name__ == "__main__":
    unittest.main()
