import os
import subprocess
import sys
from pathlib import Path

import pytest

repoRoot = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_download_settings_use_defaults(value: str) -> None:
    env = os.environ.copy()
    env["DOWNLOADS_DIR"] = value
    env["DOWNLOADS_URL"] = value
    env["DOWNLOADS_PORT"] = "2020"

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
