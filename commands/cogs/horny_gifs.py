import discord
from discord import app_commands
from discord.ext import commands

from sandrone import doughchecks

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
        result = []
        for name in nsfwGifUrls:
            if current.lower() in name.lower():
                result.append(app_commands.Choice(name=name, value=name))
        return result[:25]

    @app_commands.command(name="nsfwgif", description="Moans!", nsfw=True)
    @app_commands.describe(gif="The gif to grab")
    @app_commands.autocomplete(gif=nsfwGifAuto)
    @doughchecks.has_permissions(embed_links=True)
    async def nsfwGifSlash(self, interaction: discord.Interaction, gif: str) -> None:
        await interaction.response.defer()
        reply = await self.getNsfwGifUrl(gif)
        await interaction.followup.send(embed=reply)

    async def getNsfwGifUrl(self, gif: str) -> discord.Embed:
        user = self.bot.user
        embed = discord.Embed(color=discord.Color.fuchsia())
        slug = nsfwGifUrls.get(gif)
        embed.set_image(url=f"https://m.doughmination.gay/gif/nsfw/{slug}.gif")
        embed.set_footer(
            text="Sandrone", icon_url=user.avatar.url if user and user.avatar else None
        )
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NsfwGifs(bot))
