import asyncio
import contextlib
import signal
from pathlib import Path

import discord
from discord.ext import commands
from watchfiles import Change, awatch

from sandrone import config
from sandrone.errors import handleAppCommandError
from utils import downloads
from utils.cog_state import loadDisabled
from utils.colors import cf
from utils.doughmination import dough


def discoverExtensions(directory: Path, package: str) -> list[str]:
    return sorted(
        f"{package}.{path.stem}"
        for path in directory.glob("*.py")
        if path.stem != "__init__"
    )


class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._profileSet = False

        self.tree.allowed_contexts.guild = True
        self.tree.allowed_contexts.dm_channel = True
        self.tree.allowed_contexts.private_channel = True
        self.tree.allowed_installs.guild = True
        self.tree.allowed_installs.user = True

        self.tree.error(handleAppCommandError)

    async def setup_hook(self) -> None:
        disabled = loadDisabled()
        extensions = discoverExtensions(
            config.commandsDir, "commands"
        ) + discoverExtensions(config.cogsDir, "commands.cogs")
        for extension in extensions:
            if (
                extension.startswith("commands.cogs.")
                and extension.removeprefix("commands.cogs.") in disabled
            ):
                print(
                    cf.grey(f"[startup] skipped {extension} (disabled via /cog unload)")
                )
                continue

            try:
                await self.load_extension(extension)
                print(cf.green(f"[startup] loaded {extension}"))
            except commands.ExtensionError as e:
                print(cf.red(f"[startup] failed to load {extension}: {e}"))

        await self.tree.sync()

        await downloads.startServer()
        self.loop.create_task(downloads.sweepForever())

        if config.devMode:
            self.loop.create_task(self.watchCogs())
            print(cf.magenta("[dev-reload] watching commands/cogs for changes"))

    async def watchCogs(self) -> None:
        async for changes in awatch(config.cogsDir):
            reloaded = False
            disabled = loadDisabled()
            for change, path in changes:
                if change == Change.deleted or not path.endswith(".py"):
                    continue

                name = Path(path).stem
                if name in disabled:
                    print(
                        cf.grey(
                            f"[dev-reload] skipped commands.cogs.{name} (disabled via /cog unload)"
                        )
                    )
                    continue

                extension = f"commands.cogs.{name}"
                try:
                    if extension in self.extensions:
                        await self.reload_extension(extension)
                    else:
                        await self.load_extension(extension)
                    reloaded = True
                    print(cf.grey(f"[dev-reload] reloaded {extension}"))
                except commands.ExtensionError as e:
                    print(cf.red(f"[dev-reload] failed to reload {extension}: {e}"))

            if reloaded:
                await self.tree.sync()

    async def on_ready(self) -> None:
        if not self._profileSet:
            self._profileSet = True
            try:
                avatar_bytes = await asyncio.to_thread(
                    (config.assetsDir / "avatar.png").read_bytes
                )
                banner_bytes = await asyncio.to_thread(
                    (config.assetsDir / "banner.png").read_bytes
                )
                if self.user is not None:
                    await self.user.edit(avatar=avatar_bytes, banner=banner_bytes)
                print(cf.yellow("Avatar and Banner loaded!"))
            except (discord.HTTPException, OSError) as e:
                print(cf.red(f"Failed to set avatar/banner: {e}"))
        print(cf.magenta(f"Logged in as {self.user}"))


def createBot() -> Bot:
    intents = discord.Intents.default()
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="Columbina <3",
    )
    return Bot(command_prefix=config.prefix, intents=intents, activity=activity)


async def runBot() -> None:
    bot = createBot()

    async with bot:
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        def requestShutdown() -> None:
            print(cf.grey("\n[shutdown] signal received, closing bot..."))
            stop_event.set()

        try:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, requestShutdown)
        except NotImplementedError:

            def _handle(signum, frame):
                loop.call_soon_threadsafe(requestShutdown)

            signal.signal(signal.SIGINT, _handle)
            if hasattr(signal, "SIGBREAK"):
                signal.signal(signal.SIGBREAK, _handle)
            print(cf.blue("Windows machine detected, shutdown may not be graceful"))

        start_task = asyncio.create_task(bot.start(config.requireToken()))
        stop_task = asyncio.create_task(stop_event.wait())

        done, _ = await asyncio.wait(
            {start_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
        )

        if stop_task in done:
            await bot.close()
            start_task.cancel()
        else:
            stop_task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await start_task

        await downloads.stopServer()
        await dough.close()
        print(cf.grey("[shutdown] bot closed"))
