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

runner: web.AppRunner | None = None


def newSlot() -> Path:
    directory = config.downloadsDir / secrets.token_urlsafe(9)
    directory.mkdir(parents=True)
    return directory


def discard(slot: Path) -> None:
    shutil.rmtree(slot, ignore_errors=True)


def publicUrl(slot: Path, name: str) -> str:
    return f"{config.downloadsUrl}/{slot.name}/{quote(name)}"


metaName = ".meta.json"


def recordSource(slot: Path, key: str, name: str, extra: dict) -> None:
    (slot / metaName).write_text(json.dumps({"key": key, "name": name, **extra}) + "\n")


def findCached(key: str) -> dict | None:
    if not config.downloadsDir.is_dir():
        return None

    cutoff = time.time() - config.downloadsRetention * 3600
    for entry in config.downloadsDir.iterdir():
        if not entry.is_dir():
            continue
        try:
            meta = json.loads((entry / metaName).read_text())
        except OSError, json.JSONDecodeError:
            continue
        if meta.get("key") != key:
            continue

        target = entry / meta.get("name", "")
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
        try:
            if entry.stat().st_mtime >= cutoff:
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
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
    if not slotPattern.fullmatch(slot) or name.startswith("."):
        raise web.HTTPNotFound

    root = config.downloadsDir.resolve()
    path = (root / slot / name).resolve()
    if root not in path.parents or not path.is_file():
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
