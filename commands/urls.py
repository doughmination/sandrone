import discord
from discord import app_commands
from discord.ext import commands

siteUrls = {
"personal": "https://doughmination.gay",
"cdn": "https://m.doughmination.gay",
"git": "https://git.doughmination.gay",
}

class Urls(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def urlAutocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        result = []
        for name in siteUrls:
            if current.lower() in name.lower():
                result.append(app_commands.Choice(name=name, value=name))
        return result[:25]



    @app_commands.command(name="urls", description="Get a Doughmination URL")
    @app_commands.describe(site="The website to get")
    @app_commands.autocomplete(site=urlAutocomplete)
    async def urlsSlash(self, interaction: discord.Interaction, site: str) -> None:
        await interaction.response.defer()
        embed = await self.getUrlEmbed(site)
        await interaction.followup.send(embed=embed)

    async def getUrlEmbed(self, site: str) -> discord.Embed:
        embed = discord.Embed(color=discord.Color.pink())
        embed.set_thumbnail(url="https://m.doughmination.gay/img/avatars/favicon.png")
        urlString = await self.getUrlFromMap(site)
        embed.add_field(name="URL:", value=f"[{site}]({urlString})")
        return embed

    async def getUrlFromMap(self, site: str):
        url = siteUrls.get(site)
        return url


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Urls(bot))
