import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

from aiohttp import web

from sandrone import config
from utils import downloads


class DownloadTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.directoryPatch = patch.object(config, "downloadsDir", self.root)
        self.retentionPatch = patch.object(config, "downloadsRetention", 1)
        self.directoryPatch.start()
        self.retentionPatch.start()

    def tearDown(self) -> None:
        self.retentionPatch.stop()
        self.directoryPatch.stop()
        self.temp.cleanup()

    def test_purge_only_removes_managed_slots(self) -> None:
        slot = downloads.newSlot()
        target = slot / "video.mp4"
        target.write_bytes(b"video")
        downloads.recordSource(
            slot, "key", target.name, {"size": target.stat().st_size}
        )

        unrelatedDirectory = self.root / "source"
        unrelatedDirectory.mkdir()
        unrelatedFile = self.root / "notes.txt"
        unrelatedFile.write_text("keep me", encoding="utf-8")

        old = time.time() - 7200
        for path in (slot, unrelatedDirectory, unrelatedFile):
            os.utime(path, (old, old))

        self.assertEqual(downloads.purgeExpired(), 1)
        self.assertFalse(slot.exists())
        self.assertTrue(unrelatedDirectory.exists())
        self.assertTrue(unrelatedFile.exists())

    def test_discard_ignores_unmanaged_directories(self) -> None:
        directory = self.root / "important"
        directory.mkdir()

        downloads.discard(directory)

        self.assertTrue(directory.exists())

    def test_reserved_metadata_cannot_be_overridden(self) -> None:
        slot = downloads.newSlot()
        downloads.recordSource(
            slot,
            "expected-key",
            "video.mp4",
            {"key": "other", "name": "other.mp4", "title": "Video"},
        )

        data = json.loads((slot / downloads.metaName).read_text(encoding="utf-8"))
        self.assertEqual(data["key"], "expected-key")
        self.assertEqual(data["name"], "video.mp4")

    def test_malformed_cache_metadata_is_ignored(self) -> None:
        slot = downloads.newSlot()
        (slot / downloads.metaName).write_text("[]", encoding="utf-8")

        self.assertIsNone(downloads.findCached("key"))

    async def test_server_rejects_unmanaged_directories(self) -> None:
        directory = self.root / "source"
        directory.mkdir()
        (directory / "secret.py").write_text("token = 'secret'", encoding="utf-8")
        request = SimpleNamespace(
            match_info={"slot": directory.name, "name": "secret.py"}
        )

        with self.assertRaises(web.HTTPNotFound):
            await downloads.serve(cast(web.Request, request))


if __name__ == "__main__":
    unittest.main()
