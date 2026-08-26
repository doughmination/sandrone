from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from sandrone import config, doughchecks
from utils.cog_state import loadDisabled, setDisabled
from utils.colors import cf

cogsPackage = "commands.cogs"
cogsDir = Path(__file__).parent / "cogs"


def discoverCogNames() -> list[str]:
    return sorted(path.stem for path in cogsDir.glob("*.py") if path.stem != "__init__")


def ownerOnly():
    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.id in config.owners

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

    @app_commands.command(name="load", description="Load a cog from commands.cogs")
    @app_commands.describe(name="Cog module name, e.g. 'stats'")
    @app_commands.autocomplete(name=loadAutocomplete)
    @ownerOnly()
    async def load(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.defer()

        if name not in discoverCogNames():
            await interaction.followup.send(
                f"No cog named `{name}` in `{cogsPackage}`."
            )
            return

        extension = f"{cogsPackage}.{name}"
        if extension in self.bot.extensions:
            await interaction.followup.send(f"`{name}` is already loaded.")
            return

        try:
            await self.bot.load_extension(extension)
        except commands.ExtensionError as e:
            print(cf.yellow(f"[cog] failed to load {extension}: {e}"))
            await interaction.followup.send(f"Failed to load `{name}`: {e}")
            return

        setDisabled(name, False)
        print(cf.yellow(f"[cog] loaded {extension} (requested by {interaction.user})"))
        await self.bot.tree.sync()
        await interaction.followup.send(
            f"Loaded `{name}`. Will stay loaded across restarts."
        )

    @app_commands.command(name="unload", description="Unload a cog from commands.cogs")
    @app_commands.describe(name="Cog module name, e.g. 'stats'")
    @app_commands.autocomplete(name=unloadAutocomplete)
    @ownerOnly()
    async def unload(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.defer()

        extension = f"{cogsPackage}.{name}"
        if extension not in self.bot.extensions:
            await interaction.followup.send(f"`{name}` is not loaded.")
            return

        try:
            await self.bot.unload_extension(extension)
        except commands.ExtensionError as e:
            print(cf.yellow(f"[cog] failed to unload {extension}: {e}"))
            await interaction.followup.send(f"Failed to unload `{name}`: {e}")
            return

        setDisabled(name, True)
        print(
            cf.yellow(f"[cog] unloaded {extension} (requested by {interaction.user})")
        )
        await self.bot.tree.sync()
        await interaction.followup.send(
            f"Unloaded `{name}`. Will stay unloaded across restarts."
        )

    @app_commands.command(
        name="list",
        description="Show which cogs are loaded and whether they'll survive a restart",
    )
    @ownerOnly()
    @doughchecks.has_permissions(embed_links=True)
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
                status = (
                    "⚠️ unloaded (not disabled, but not loaded — check startup logs)"
                )
            lines.append(f"`{name}` — {status}")

        user = self.bot.user
        embed = discord.Embed(
            title="Cog status",
            description="\n".join(lines) if lines else "No cogs found.",
            color=discord.Color.fuchsia(),
        )
        embed.set_footer(
            text="Sandrone", icon_url=user.avatar.url if user and user.avatar else None
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CogManager(bot))
