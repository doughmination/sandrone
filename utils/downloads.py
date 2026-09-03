import asyncio
import json
import os
import re
import secrets
import shutil
import time
from pathlib import Path
from urllib.parse import quote

from aiohttp import web

from sandrone import config
from utils.colors import cf

sweepInterval = 3600

slotPattern = re.compile(r"[A-Za-z0-9_-]{1,64}")
metaName = ".meta.json"
markerName = ".sandrone-download"

runner: web.AppRunner | None = None


def newSlot() -> Path:
    directory = config.downloadsDir / secrets.token_urlsafe(9)
    directory.mkdir(parents=True)
    (directory / markerName).touch()
    return directory


def discard(slot: Path) -> None:
    managed = managedSlot(slot)
    if managed is not None:
        shutil.rmtree(managed, ignore_errors=True)


def publicUrl(slot: Path, name: str) -> str:
    return f"{config.downloadsUrl}/{slot.name}/{quote(name, safe='')}"


def validName(name: object) -> bool:
    return (
        isinstance(name, str)
        and bool(name)
        and name not in (".", "..")
        and not name.startswith(".")
        and all(ord(char) >= 32 for char in name)
        and "/" not in name
        and "\\" not in name
    )


def managedSlot(slot: Path) -> Path | None:
    try:
        root = config.downloadsDir.resolve()
        resolved = slot.resolve()
    except (OSError, RuntimeError):
        return None
    if resolved.parent != root or not slotPattern.fullmatch(resolved.name):
        return None
    if not (resolved / markerName).is_file() and not (resolved / metaName).is_file():
        return None
    return resolved


def recordSource(slot: Path, key: str, name: str, extra: dict) -> None:
    managed = managedSlot(slot)
    if managed is None or not validName(name):
        raise ValueError("Invalid download slot or filename")
    data = {**extra, "key": key, "name": name}
    (managed / metaName).write_text(json.dumps(data) + "\n", encoding="utf-8")


def findCached(key: str) -> dict | None:
    if not config.downloadsDir.is_dir():
        return None

    cutoff = time.time() - config.downloadsRetention * 3600
    for entry in config.downloadsDir.iterdir():
        entry = managedSlot(entry)
        if entry is None:
            continue
        try:
            meta = json.loads((entry / metaName).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(meta, dict) or meta.get("key") != key:
            continue

        name = meta.get("name")
        title = meta.get("title")
        size = meta.get("size")
        if (
            not validName(name)
            or not isinstance(title, str)
            or not title.strip()
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
        ):
            continue
        target = entry / name
        try:
            if not target.is_file() or entry.stat().st_mtime < cutoff:
                continue
            now = time.time()
            os.utime(entry, (now, now))
            os.utime(target, (now, now))
        except OSError:
            continue

        return {**meta, "slot": entry}

    return None


def purgeExpired() -> int:
    if not config.downloadsDir.is_dir():
        return 0

    cutoff = time.time() - config.downloadsRetention * 3600
    removed = 0
    for entry in config.downloadsDir.iterdir():
        entry = managedSlot(entry)
        if entry is None:
            continue
        try:
            if entry.stat().st_mtime >= cutoff:
                continue
            shutil.rmtree(entry)
            removed += 1
        except OSError as error:
            print(cf.red(f"[downloads] could not remove {entry.name}: {error}"))
    return removed


async def sweepForever() -> None:
    while True:
        removed = await asyncio.to_thread(purgeExpired)
        if removed:
            print(cf.grey(f"[downloads] removed {removed} expired download(s)"))
        await asyncio.sleep(sweepInterval)


async def serve(request: web.Request) -> web.FileResponse:
    slot = request.match_info["slot"]
    name = request.match_info["name"]
    if not slotPattern.fullmatch(slot) or name.startswith(".") or not validName(name):
        raise web.HTTPNotFound

    directory = managedSlot(config.downloadsDir / slot)
    if directory is None:
        raise web.HTTPNotFound

    path = (directory / name).resolve()
    if path.parent != directory or not path.is_file():
        raise web.HTTPNotFound

    now = time.time()
    try:
        os.utime(path.parent, (now, now))
        os.utime(path, (now, now))
    except OSError:
        pass

    return web.FileResponse(path)


async def startServer() -> None:
    global runner

    if runner is not None:
        return

    config.downloadsDir.mkdir(parents=True, exist_ok=True)
    app = web.Application()
    app.router.add_get("/{slot}/{name}", serve)

    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    try:
        await web.TCPSite(runner, config.downloadsHost, config.downloadsPort).start()
    except OSError as error:
        await runner.cleanup()
        runner = None
        print(
            cf.red(f"[downloads] could not listen on {config.downloadsPort}: {error}")
        )
        return

    print(
        cf.cyan(
            f"[downloads] serving {config.downloadsDir} on "
            f"{config.downloadsHost}:{config.downloadsPort} as {config.downloadsUrl}"
        )
    )


async def stopServer() -> None:
    global runner

    if runner is not None:
        await runner.cleanup()
        runner = None
