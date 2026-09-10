from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from sandrone import config
from utils import components
from utils.cog_state import discoverCogHandles, loadDisabled, setDisabled
from utils.colors import cf

cogsPackage = "commands.cogs"
cogsDir = Path(__file__).parent / "cogs"


def discoverCogNames() -> list[str]:
    return discoverCogHandles(cogsDir)


def ownerOnly():
    async def predicate(ctx: commands.Context) -> bool:
        return ctx.author.id in config.owners

    return commands.check(predicate)


class CogManager(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def loadAutocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=name, value=name)
            for name in discoverCogNames()
            if f"{cogsPackage}.{name}" not in self.bot.extensions
            and current.lower() in name.lower()
        ][:25]

    async def unloadAutocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=name, value=name)
            for name in discoverCogNames()
            if f"{cogsPackage}.{name}" in self.bot.extensions
            and current.lower() in name.lower()
        ][:25]

    @commands.hybrid_group(
        name="cog",
        description="Manage bot cogs",
        invoke_without_command=True,
    )
    @ownerOnly()
    async def cog(self, ctx: commands.Context) -> None:
        await ctx.send("Use `cog load`, `cog unload`, or `cog list`.", ephemeral=True)

    @cog.command(name="load", description="Load a cog from commands.cogs")
    @app_commands.describe(name="Cog module name, e.g. 'stats'")
    @app_commands.autocomplete(name=loadAutocomplete)
    @ownerOnly()
    async def load(self, ctx: commands.Context, name: str) -> None:
        await ctx.defer()

        if name not in discoverCogNames():
            await ctx.send(
                f"No cog named `{name}` in `{cogsPackage}`."
            )
            return

        extension = f"{cogsPackage}.{name}"
        if extension in self.bot.extensions:
            await ctx.send(f"`{name}` is already loaded.")
            return

        try:
            await self.bot.load_extension(extension)
        except commands.ExtensionError as e:
            print(cf.yellow(f"[cog] failed to load {extension}: {e}"))
            await ctx.send(f"Failed to load `{name}`: {e}")
            return

        setDisabled(name, False)
        print(cf.yellow(f"[cog] loaded {extension} (requested by {ctx.author})"))
        await self.bot.tree.sync()
        await ctx.send(
            f"Loaded `{name}`. Will stay loaded across restarts."
        )

    @cog.command(name="unload", description="Unload a cog from commands.cogs")
    @app_commands.describe(name="Cog module name, e.g. 'stats'")
    @app_commands.autocomplete(name=unloadAutocomplete)
    @ownerOnly()
    async def unload(self, ctx: commands.Context, name: str) -> None:
        await ctx.defer()

        extension = f"{cogsPackage}.{name}"
        if extension not in self.bot.extensions:
            await ctx.send(f"`{name}` is not loaded.")
            return

        try:
            await self.bot.unload_extension(extension)
        except commands.ExtensionError as e:
            print(cf.yellow(f"[cog] failed to unload {extension}: {e}"))
            await ctx.send(f"Failed to unload `{name}`: {e}")
            return

        setDisabled(name, True)
        print(
            cf.yellow(f"[cog] unloaded {extension} (requested by {ctx.author})")
        )
        await self.bot.tree.sync()
        await ctx.send(
            f"Unloaded `{name}`. Will stay unloaded across restarts."
        )

    @cog.command(
        name="list",
        description="Show which cogs are loaded and whether they'll survive a restart",
    )
    @ownerOnly()
    async def listCogs(self, ctx: commands.Context) -> None:
        disabled = loadDisabled()
        lines = []
        for name in discoverCogNames():
            loaded = f"{cogsPackage}.{name}" in self.bot.extensions
            if loaded:
                status = "✅ loaded"
            elif name in disabled:
                status = "⛔ unloaded (disabled — stays off across restarts)"
            else:
                status = (
                    "⚠️ unloaded (not disabled, but not loaded — check startup logs)"
                )
            lines.append(f"`{name}` — {status}")

        view = components.panel(
            title="Cog status",
            body="\n".join(lines) if lines else "No cogs found.",
            footer="Sandrone",
        )
        await ctx.send(view=view, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CogManager(bot))
