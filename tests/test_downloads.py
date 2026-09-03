import asyncio
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from aiohttp import web

from sandrone import config
from utils import downloads


@pytest.fixture
def downloadRoot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "downloadsDir", tmp_path)
    monkeypatch.setattr(config, "downloadsRetention", 1)
    return tmp_path


def test_purge_only_removes_managed_slots(downloadRoot: Path) -> None:
    slot = downloads.newSlot()
    target = slot / "video.mp4"
    target.write_bytes(b"video")
    downloads.recordSource(
        slot,
        "key",
        target.name,
        {"title": "Video", "size": target.stat().st_size},
    )

    unrelatedDirectory = downloadRoot / "source"
    unrelatedDirectory.mkdir()
    unrelatedFile = downloadRoot / "notes.txt"
    unrelatedFile.write_text("keep me", encoding="utf-8")

    old = time.time() - 7200
    for path in (slot, unrelatedDirectory, unrelatedFile):
        os.utime(path, (old, old))

    assert downloads.purgeExpired() == 1
    assert not slot.exists()
    assert unrelatedDirectory.exists()
    assert unrelatedFile.exists()


def test_discard_ignores_unmanaged_directories(downloadRoot: Path) -> None:
    directory = downloadRoot / "important"
    directory.mkdir()

    downloads.discard(directory)

    assert directory.exists()


def test_reserved_metadata_cannot_be_overridden(downloadRoot: Path) -> None:
    slot = downloads.newSlot()
    downloads.recordSource(
        slot,
        "expected-key",
        "video.mp4",
        {"key": "other", "name": "other.mp4", "title": "Video"},
    )

    data = json.loads((slot / downloads.metaName).read_text(encoding="utf-8"))
    assert data["key"] == "expected-key"
    assert data["name"] == "video.mp4"


@pytest.mark.parametrize(
    "metadata",
    [
        pytest.param([], id="not-an-object"),
        pytest.param(
            {"key": "key", "name": "video.mp4", "size": 5}, id="missing-title"
        ),
        pytest.param(
            {"key": "key", "name": "video.mp4", "title": "Video"},
            id="missing-size",
        ),
        pytest.param(
            {"key": "key", "name": "video.mp4", "title": "Video", "size": "5"},
            id="invalid-size",
        ),
        pytest.param(
            {"key": "key", "name": "video.mp4", "title": 123, "size": 5},
            id="invalid-title",
        ),
        pytest.param(
            {"key": "key", "name": "video.mp4", "title": "Video", "size": True},
            id="boolean-size",
        ),
    ],
)
def test_invalid_cache_metadata_is_ignored(
    downloadRoot: Path, metadata: object
) -> None:
    slot = downloads.newSlot()
    target = slot / "video.mp4"
    target.write_bytes(b"video")
    (slot / downloads.metaName).write_text(json.dumps(metadata), encoding="utf-8")

    assert downloads.findCached("key") is None


def test_valid_cache_metadata_is_returned(downloadRoot: Path) -> None:
    slot = downloads.newSlot()
    target = slot / "video.mp4"
    target.write_bytes(b"video")
    downloads.recordSource(
        slot,
        "key",
        target.name,
        {"title": "Video", "size": target.stat().st_size},
    )

    cached = downloads.findCached("key")

    assert cached is not None
    assert cached["title"] == "Video"
    assert cached["size"] == 5


def test_server_rejects_unmanaged_directories(downloadRoot: Path) -> None:
    directory = downloadRoot / "source"
    directory.mkdir()
    (directory / "secret.py").write_text("token = 'secret'", encoding="utf-8")
    request = SimpleNamespace(match_info={"slot": directory.name, "name": "secret.py"})

    with pytest.raises(web.HTTPNotFound):
        asyncio.run(downloads.serve(cast(web.Request, request)))
