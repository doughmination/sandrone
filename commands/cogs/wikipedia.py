import discord
import wikipediaapi
from discord import app_commands
from discord.ext import commands

from sandrone import config, doughchecks


def formatText(text: str) -> str:
    return text[:500].strip() + "..." if len(text) > 500 else text


class Wikipedia(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="wikipedia", description="Look a term on Wikipedia")
    @app_commands.describe(query="The query")
    @doughchecks.has_permissions(embed_links=True)
    async def wikiSlash(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        defin = await self.wikiDefEmbed(query)
        await interaction.followup.send(embed=defin)

    async def wikiDefEmbed(self, query: str) -> discord.Embed:
        wiki = wikipediaapi.AsyncWikipedia(
            user_agent=f"Sandrone-{config.version} (https://github.com/doughmination/sandrone)",
            language="en",
        )
        wikiPage = wiki.page(query)
        if not await wikiPage.exists():
            embed = discord.Embed(color=discord.Color.red())
            embed.description = ":x: That Wikipedia page does not exist. Try adjusting your capitalisation, as results are occasionally case-sensitive!"
            return embed
        elif "Category:All disambiguation pages" in (await wikiPage.categories):
            pageSummary = f'Disambiguations for "{query}":'
            pageLinks = await wikiPage.links
            for name in pageLinks:
                pageSummary += f"\n- {name}"

            pageImages = {}
            pageSummary = formatText(pageSummary)
        else:
            pageImages = await wikiPage.images
            pageSummary = formatText(await wikiPage.summary)

        embed = discord.Embed(
            title=wikiPage.title,
            description=pageSummary,
            url=(await wikiPage.fullurl),
            color=discord.Color.fuchsia(),
        )
        embed.set_footer(
            text="Powered by Wikipedia",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/2/2e/Wikipedia_W_favicon_on_white_background.png",
        )
        if pageImages:
            img = next(iter(pageImages.values()))
            embed.set_thumbnail(url=await img.url)
        else:
            embed.set_thumbnail(url="https://m.doughmination.gay/img/search.png")
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Wikipedia(bot))
