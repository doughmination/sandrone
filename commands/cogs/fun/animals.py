import uuid

from discord.ext import commands

from sandrone import mood
from utils import components


class Animals(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="kitty", description="KITTY!", aliases=["cat", "cats"]
    )
    @mood.sassy
    async def kitty(self, ctx: commands.Context) -> None:
        await ctx.defer()
        await ctx.send(view=await self.getCatPanel())

    async def getCatPanel(self) -> components.Panel:
        catUrl = f"https://cataas.com/cat?v={uuid.uuid4()}"
        return components.panel(images=[catUrl], footer="Sandrone")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Animals(bot))
