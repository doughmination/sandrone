from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from bot.errors import handleAppCommandError
from utils.cog_state import loadDisabled, setDisabled
import colorful as cf

cf.use_true_colors()

cogsPackage = "commands.cogs"
cogsDir = Path(__file__).parent / "cogs"


def discoverCogNames() -> list[str]:
    return sorted(path.stem for path in cogsDir.glob("*.py") if path.stem != "__init__")


def ownerOnly():
    async def predicate(interaction: discord.Interaction) -> bool:
        return await interaction.client.is_owner(interaction.user)

    return app_commands.check(predicate)


class CogManager(commands.GroupCog, name="cog", description="Manage bot cogs"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    async def loadAutocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=name, value=name)
            for name in discoverCogNames()
            if f"{cogsPackage}.{name}" not in self.bot.extensions and current.lower() in name.lower()
        ][:25]

    async def unloadAutocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=name, value=name)
            for name in discoverCogNames()
            if f"{cogsPackage}.{name}" in self.bot.extensions and current.lower() in name.lower()
        ][:25]

    @app_commands.command(name="load", description="Load a cog from commands.cogs")
    @app_commands.describe(name="Cog module name, e.g. 'stats'")
    @app_commands.autocomplete(name=loadAutocomplete)
    @ownerOnly()
    async def load(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.defer(ephemeral=True)

        if name not in discoverCogNames():
            await interaction.followup.send(
                f"No cog named `{name}` in `{cogsPackage}`.", ephemeral=True
            )
            return

        extension = f"{cogsPackage}.{name}"
        if extension in self.bot.extensions:
            await interaction.followup.send(f"`{name}` is already loaded.", ephemeral=True)
            return

        try:
            await self.bot.load_extension(extension)
        except commands.ExtensionError as e:
            print(cf.yellow(f"[cog] failed to load {extension}: {e}"))
            await interaction.followup.send(f"Failed to load `{name}`: {e}", ephemeral=True)
            return

        setDisabled(name, False)
        print(cf.yellow(f"[cog] loaded {extension} (requested by {interaction.user})"))
        await self.bot.tree.sync()
        await interaction.followup.send(f"Loaded `{name}`. Will stay loaded across restarts.", ephemeral=True)

    @app_commands.command(name="unload", description="Unload a cog from commands.cogs")
    @app_commands.describe(name="Cog module name, e.g. 'stats'")
    @app_commands.autocomplete(name=unloadAutocomplete)
    @ownerOnly()
    async def unload(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.defer(ephemeral=True)

        extension = f"{cogsPackage}.{name}"
        if extension not in self.bot.extensions:
            await interaction.followup.send(f"`{name}` is not loaded.", ephemeral=True)
            return

        try:
            await self.bot.unload_extension(extension)
        except commands.ExtensionError as e:
            print(cf.yellow(f"[cog] failed to unload {extension}: {e}"))
            await interaction.followup.send(f"Failed to unload `{name}`: {e}", ephemeral=True)
            return

        setDisabled(name, True)
        print(cf.yellow(f"[cog] unloaded {extension} (requested by {interaction.user})"))
        await self.bot.tree.sync()
        await interaction.followup.send(f"Unloaded `{name}`. Will stay unloaded across restarts.", ephemeral=True)

    @app_commands.command(name="list", description="Show which cogs are loaded and whether they'll survive a restart")
    @ownerOnly()
    async def listCogs(self, interaction: discord.Interaction) -> None:
        disabled = loadDisabled()
        lines = []
        for name in discoverCogNames():
            loaded = f"{cogsPackage}.{name}" in self.bot.extensions
            if loaded:
                status = "✅ loaded"
            elif name in disabled:
                status = "⛔ unloaded (disabled — stays off across restarts)"
            else:
                status = "⚠️ unloaded (not disabled, but not loaded — check startup logs)"
            lines.append(f"`{name}` — {status}")

        embed = discord.Embed(
            title="Cog status",
            description="\n".join(lines) if lines else "No cogs found.",
            color=discord.Color.fuchsia(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        await handleAppCommandError(interaction, error)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CogManager(bot))
