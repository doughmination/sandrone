import uuid

import discord
from discord import app_commands
from discord.ext import commands

class Animals(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="kitty", description="KITTY!")
    async def kittySlash(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        embed = await self.getCatEmbed()
        await interaction.followup.send(embed=embed)

    async def getCatEmbed(self) -> discord.Embed:
        catEmbed = discord.Embed(color=discord.Color.fuchsia())
        catUrl = f"https://cataas.com/cat?v={uuid.uuid4()}"
        catEmbed.set_image(url=catUrl)
        return catEmbed

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Animals(bot))