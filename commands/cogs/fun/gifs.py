import discord
from discord import app_commands
from discord.ext import commands

from sandrone import mood
from utils import components

gifUrls = {
    "angry-cat": "angy-car",
    "bitey-cat": "nom-car",
    "meow-cat": "mrrow-car",
    "sus-cat": "sus",
    "want-pats": "want-pats",
}


class Gifs(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def gifAuto(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=name, value=name)
            for name in gifUrls
            if current.lower() in name.lower()
        ][:25]

    @commands.hybrid_command(
        name="fungif", description="Send some fun gifs!", aliases=["gif"]
    )
    @app_commands.describe(gif="The gif to grab")
    @app_commands.autocomplete(gif=gifAuto)
    @mood.sassy
    async def fungif(self, ctx: commands.Context, gif: str) -> None:
        await ctx.defer()
        await ctx.send(view=await self.getGifUrl(gif))

    async def getGifUrl(self, gif: str) -> components.Panel:
        slug = gifUrls.get(gif)
        if slug is None:
            return components.error(f"There's no gif called `{gif}`.")

        return components.panel(
            images=[f"https://m.doughmination.gay/gif/{slug}.gif"], footer="Sandrone"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Gifs(bot))
