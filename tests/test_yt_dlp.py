import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from discord.ext import commands

from commands.cogs.yt_dlp import Result, YtDlp
from sandrone import config
from utils import downloads


class YtDlpTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_metadata_write_discards_download(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cog = YtDlp(cast(commands.Bot, object()))

            def fakeDownload(url: str, container: str, slot: Path) -> Result:
                target = slot / "video.mp4"
                target.write_bytes(b"too large")
                return Result(target, "Video", 720)

            with (
                patch.object(config, "downloadsDir", root),
                patch.object(cog, "download", side_effect=fakeDownload),
                patch.object(downloads, "recordSource", side_effect=OSError("full")),
            ):
                message, attachment = await cog.getVideoOrAudio(
                    "https://youtu.be/dQw4w9WgXcQ", "mp4", 1
                )

            self.assertIn("Something went wrong", message)
            self.assertIsNone(attachment)
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
