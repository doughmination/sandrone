import discord
from discord import app_commands
from discord.ext import commands


class userId(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="uid", description="Get a user's ID")
    @app_commands.describe(user="The user to get the ID of (Default to you)")
    async def idSlash(
        self, interaction: discord.Interaction, user: discord.Member | None = None
    ) -> None:
        await interaction.response.defer()
        target = user or interaction.user
        await interaction.followup.send(f"{target.mention}'s ID is `{target.id}`")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(userId(bot))
