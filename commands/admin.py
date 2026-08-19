from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

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

    async def nameAutocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=name, value=name)
            for name in discoverCogNames()
            if current.lower() in name.lower()
        ][:25]

    @app_commands.command(name="load", description="Load a cog from commands.cogs")
    @app_commands.describe(name="Cog module name, e.g. 'stats'")
    @app_commands.autocomplete(name=nameAutocomplete)
    @ownerOnly()
    async def load(self, interaction: discord.Interaction, name: str) -> None:
        if name not in discoverCogNames():
            await interaction.response.send_message(
                f"No cog named `{name}` in `{cogsPackage}`.", ephemeral=True
            )
            return

        extension = f"{cogsPackage}.{name}"
        if extension in self.bot.extensions:
            await interaction.response.send_message(f"`{name}` is already loaded.", ephemeral=True)
            return

        try:
            await self.bot.load_extension(extension)
        except commands.ExtensionError as e:
            print(f"[cog] failed to load {extension}: {e}")
            await interaction.response.send_message(f"Failed to load `{name}`: {e}", ephemeral=True)
            return

        print(f"[cog] loaded {extension} (requested by {interaction.user})")
        await self.bot.tree.sync()
        await interaction.response.send_message(f"Loaded `{name}`.", ephemeral=True)

    @app_commands.command(name="unload", description="Unload a cog from commands.cogs")
    @app_commands.describe(name="Cog module name, e.g. 'stats'")
    @app_commands.autocomplete(name=nameAutocomplete)
    @ownerOnly()
    async def unload(self, interaction: discord.Interaction, name: str) -> None:
        extension = f"{cogsPackage}.{name}"
        if extension not in self.bot.extensions:
            await interaction.response.send_message(f"`{name}` is not loaded.", ephemeral=True)
            return

        try:
            await self.bot.unload_extension(extension)
        except commands.ExtensionError as e:
            print(f"[cog] failed to unload {extension}: {e}")
            await interaction.response.send_message(f"Failed to unload `{name}`: {e}", ephemeral=True)
            return

        print(f"[cog] unloaded {extension} (requested by {interaction.user})")
        await self.bot.tree.sync()
        await interaction.response.send_message(f"Unloaded `{name}`.", ephemeral=True)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "You do not have permission to execute this command", ephemeral=True
            )
            return
        raise error


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CogManager(bot))
