import os
import subprocess
import sys
from pathlib import Path

repoRoot = Path(__file__).resolve().parent.parent


def test_blank_download_settings_use_defaults() -> None:
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
    assert Path(directory) == repoRoot / "downloads"
    assert url == "http://localhost:2020"
