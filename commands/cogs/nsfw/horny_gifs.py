import discord
from discord import app_commands
from discord.ext import commands

from sandrone import doughchecks, mood
from utils import components

nsfwGifUrls = {
    "Catgirl Sucking": "catgirl-suck",
    "Cum Filled": "cum-filled",
    "Cum Thirsty": "cum-thirsty",
    "Deep Kiss": "deep-kiss",
    "Double Blowjob": "double-suck",
    "Held Up Anal": "held-up-anal",
    "Pregnant Pillow": "pregnant-pillow",
    "Shuddup": "shuddup",
    "Shut the fuck up": "stfu",
    "Stop Yapping": "stop-yapping",
    "Tied Up": "tied-up",
    "Yeah Yeah Whatever": "whatever",
}


class NsfwGifs(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def nsfwGifAuto(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=name, value=name)
            for name in nsfwGifUrls
            if current.lower() in name.lower()
        ][:25]

    @commands.hybrid_command(name="nsfwgif", description="Moans!")
    @app_commands.describe(gif="The gif to grab")
    @app_commands.autocomplete(gif=nsfwGifAuto)
    @doughchecks.nsfw_only()
    @mood.sassy
    async def nsfwGif(self, ctx: commands.Context, gif: str) -> None:
        await ctx.defer()
        await ctx.send(view=await self.getNsfwGifUrl(gif))

    async def getNsfwGifUrl(self, gif: str) -> components.Panel:
        slug = nsfwGifUrls.get(gif)
        if slug is None:
            return components.error(f"There's no gif called `{gif}`.")

        return components.panel(
            images=[f"https://m.doughmination.gay/gif/nsfw/{slug}.gif"],
            footer="Sandrone",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NsfwGifs(bot))
