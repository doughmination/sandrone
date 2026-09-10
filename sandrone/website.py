import math
import os
import time
from pathlib import Path
from typing import Any

from aiohttp import web

from sandrone import config
from utils import downloads
from utils.colors import cf

runner: web.AppRunner | None = None

botKey: web.AppKey[Any] = web.AppKey("bot")
startedAtKey: web.AppKey[float] = web.AppKey("startedAt")


def webAsset(name: str) -> Path | None:
    """Return an existing public web asset, never a path outside ``webDir``."""
    try:
        root = config.webDir.resolve()
        path = (root / name).resolve()
        path.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None
    return path if path.is_file() else None


async def index(request: web.Request) -> web.FileResponse:
    path = webAsset("index.html")
    if path is None:
        raise web.HTTPInternalServerError(text="web/index.html is missing")
    return web.FileResponse(path)


async def serveDownload(request: web.Request) -> web.FileResponse:
    slot = request.match_info["slot"]
    name = request.match_info["name"]
    if not downloads.slotPattern.fullmatch(slot) or not downloads.validName(name):
        raise web.HTTPNotFound

    directory = downloads.managedSlot(config.downloadsDir / slot)
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

async def status(request: web.Request) -> web.Response:
    """Whatever the landing page can say about the bot without knowing who asked."""
    bot = request.app[botKey]
    payload: dict[str, Any] = {
        "version": config.version,
        "uptime": int(time.monotonic() - request.app[startedAtKey]),
    }

    if bot is not None:
        payload["servers"] = len(bot.guilds)
        if math.isfinite(bot.latency):
            payload["latency"] = round(bot.latency * 1000)

    return web.json_response(payload, headers={"Cache-Control": "no-store"})


async def openDocs(request) -> web.HTTPMovedPermanently:
    raise web.HTTPMovedPermanently("https://docs.doughmination.gay/projects/sandrone")

async def inviteBot(request) -> web.HTTPMovedPermanently:
    raise web.HTTPMovedPermanently(f"https://discord.com/oauth2/authorize?client_id={config.requireClientID()}")

async def supportServer(request) -> web.HTTPMovedPermanently:
    raise web.HTTPMovedPermanently("https://discord.gg/N8gCjS294R")

async def notFound(request: web.Request) -> web.FileResponse:
    path = webAsset("404.html")
    if path is None:
        raise web.HTTPNotFound
    return web.FileResponse(path, status=404)


async def serveAsset(request: web.Request) -> web.FileResponse:
    path = webAsset(request.match_info["asset"])
    return web.FileResponse(path) if path is not None else await notFound(request)


def createApp(bot: Any = None) -> web.Application:
    app = web.Application()
    app[botKey] = bot
    app[startedAtKey] = time.monotonic()
    app.router.add_get("/", index)
    app.router.add_get("/api/status", status)
    app.router.add_get("/docs", openDocs)
    app.router.add_get("/invite", inviteBot)
    app.router.add_get("/support", supportServer)
    app.router.add_get("/d/{slot}/{name}", serveDownload)
    app.router.add_get("/{asset:.*}", serveAsset)
    return app


async def startServer(bot: Any = None) -> None:
    global runner

    if runner is not None:
        return

    config.downloadsDir.mkdir(parents=True, exist_ok=True)
    runner = web.AppRunner(createApp(bot), access_log=None)
    await runner.setup()
    try:
        await web.TCPSite(runner, config.downloadsHost, config.downloadsPort).start()
    except OSError as error:
        await runner.cleanup()
        runner = None
        print(cf.red(f"[website] could not listen on {config.downloadsPort}: {error}"))
        return

    print(
        cf.cyan(
            f"[website] serving {config.webDir} on "
            f"{config.downloadsHost}:{config.downloadsPort} as {config.downloadsUrl}"
        )
    )


async def stopServer() -> None:
    global runner

    if runner is not None:
        await runner.cleanup()
        runner = None
