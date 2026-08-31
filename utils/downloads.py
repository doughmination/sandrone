"""Disk-backed store, and web server, for files too big to attach to Discord.

Each download gets its own directory under ``config.downloadsDir`` so names
can never collide in a URL, and a small aiohttp server hands those files back
out on ``config.downloadsPort``. A sweep drops anything past the retention
window. Nothing here touches Discord, so the yt-dlp cog stays thin and the
server and sweep can both be driven from the bot's startup hook.
"""

import asyncio
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


def purgeExpired() -> int:
    """Delete every slot past the retention window. Returns how many went."""
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
    """Hand back one stored file.

    Slot names are generated here, so anything that doesn't look like one is a
    probe. The resolve check below is what actually stops traversal, since a
    percent-encoded ``..`` survives routing.
    """
    slot = request.match_info["slot"]
    if not slotPattern.fullmatch(slot):
        raise web.HTTPNotFound

    root = config.downloadsDir.resolve()
    path = (root / slot / request.match_info["name"]).resolve()
    if root not in path.parents or not path.is_file():
        raise web.HTTPNotFound

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
        # A busy port shouldn't take the whole bot down; large downloads just
        # can't be handed out until it is free.
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
