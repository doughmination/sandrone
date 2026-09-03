import asyncio
from pathlib import Path
from typing import cast

import pytest
from discord.ext import commands

from commands.cogs.yt_dlp import Result, YtDlp
from sandrone import config
from utils import downloads


def test_failed_metadata_write_discards_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cog = YtDlp(cast(commands.Bot, object()))

    def fakeDownload(url: str, container: str, slot: Path) -> Result:
        target = slot / "video.mp4"
        target.write_bytes(b"too large")
        return Result(target, "Video", 720)

    def failRecordSource(slot: Path, key: str, name: str, extra: dict) -> None:
        raise OSError("full")

    monkeypatch.setattr(config, "downloadsDir", tmp_path)
    monkeypatch.setattr(cog, "download", fakeDownload)
    monkeypatch.setattr(downloads, "recordSource", failRecordSource)

    message, attachment = asyncio.run(
        cog.getVideoOrAudio("https://youtu.be/dQw4w9WgXcQ", "mp4", 1)
    )

    assert "Something went wrong" in message
    assert attachment is None
    assert list(tmp_path.iterdir()) == []
