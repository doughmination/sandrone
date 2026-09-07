import uuid

import discord
from discord import app_commands
from discord.ext import commands

from utils import components


class Animals(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="kitty", description="KITTY!")
    async def kittySlash(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await interaction.followup.send(view=await self.getCatPanel())

    async def getCatPanel(self) -> components.Panel:
        catUrl = f"https://cataas.com/cat?v={uuid.uuid4()}"
        return components.panel(images=[catUrl], footer="Sandrone")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Animals(bot))
