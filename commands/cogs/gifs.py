import discord
from discord import app_commands
from discord.ext import commands

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
        result = []
        for name in gifUrls:
            if current.lower() in name.lower():
                result.append(app_commands.Choice(name=name, value=name))
        return result[:25]

    @app_commands.command(name="fungif", description="Angry MRAAAOW!")
    @app_commands.describe(gif="The gif to grab")
    @app_commands.autocomplete(gif=gifAuto)
    async def gifSlash(self, interaction: discord.Interaction, gif: str) -> None:
        await interaction.response.defer()
        reply = await self.getGifUrl(gif)
        await interaction.followup.send(embed=reply)
    
    async def getGifUrl(self, gif: str) -> discord.Embed:
        embed = discord.Embed(color=discord.Color.fuchsia())
        slug = gifUrls.get(gif)
        embed.set_image(url=f"https://m.doughmination.gay/gif/{slug}.gif")
        return embed
    
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Gifs(bot))