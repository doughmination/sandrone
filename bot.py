import asyncio
import contextlib
import os
import signal
from pathlib import Path

import discord
from discord.ext import commands
from dotenvx import load_dotenv
from watchfiles import Change, awatch

load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
PREFIX = os.getenv('BOT_PREFIX', '!')
DEV_MODE = os.getenv('DEV_MODE', 'false').lower() == 'true'

COMMANDS_DIR = Path(__file__).parent / "commands"
COGS_DIR = COMMANDS_DIR / "cogs"

def discover_extensions(directory: Path, package: str) -> list[str]:
    return sorted(
        f"{package}.{path.stem}"
        for path in directory.glob("*.py")
        if path.stem != "__init__"
    )

class Bot(commands.Bot):
    async def setup_hook(self) -> None:
        extensions = discover_extensions(COMMANDS_DIR, "commands") + discover_extensions(
            COGS_DIR, "commands.cogs"
        )
        for extension in extensions:
            try:
                await self.load_extension(extension)
                print(f"[startup] loaded {extension}")
            except commands.ExtensionError as e:
                print(f"[startup] failed to load {extension}: {e}")

        await self.tree.sync()

        if DEV_MODE:
            self.loop.create_task(self.watch_cogs())
            print("[dev-reload] watching commands/cogs for changes")

    async def watch_cogs(self) -> None:
        async for changes in awatch(COGS_DIR):
            reloaded = False
            for change, path in changes:
                if change == Change.deleted or not path.endswith(".py"):
                    continue

                extension = f"commands.cogs.{Path(path).stem}"
                try:
                    if extension in self.extensions:
                        await self.reload_extension(extension)
                    else:
                        await self.load_extension(extension)
                    reloaded = True
                    print(f"[dev-reload] reloaded {extension}")
                except commands.ExtensionError as e:
                    print(f"[dev-reload] failed to reload {extension}: {e}")

            if reloaded:
                await self.tree.sync()

intents = discord.Intents.default()
bot = Bot(command_prefix=PREFIX, intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

async def main():
    async with bot:
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        def request_shutdown() -> None:
            print("\n[shutdown] signal received, closing bot...")
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, request_shutdown)

        start_task = asyncio.create_task(bot.start(TOKEN))
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

        print("[shutdown] bot closed")

if TOKEN is not None:
    asyncio.run(main())
else:
    print("The Bot Token is not set, please configure .env")
