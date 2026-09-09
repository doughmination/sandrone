import discord
import wikipediaapi
from discord import app_commands
from discord.ext import commands

from sandrone import config, doughchecks, mood
from utils import components


def formatText(text: str) -> str:
    return text[:500].strip() + "..." if len(text) > 500 else text


class Wikipedia(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="wikipedia", description="Look a term on Wikipedia")
    @app_commands.describe(query="The query")
    @doughchecks.has_permissions(embed_links=True)
    @mood.sassy
    async def wikiSlash(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        await interaction.followup.send(view=await self.wikiDefPanel(query))

    async def wikiDefPanel(self, query: str) -> components.Panel:
        wiki = wikipediaapi.AsyncWikipedia(
            user_agent=f"Sandrone-{config.version} (https://github.com/doughmination/sandrone)",
            language="en",
        )
        wikiPage = wiki.page(query)
        if not await wikiPage.exists():
            return components.error(
                "That Wikipedia page does not exist. Try adjusting your "
                "capitalisation, as results are occasionally case-sensitive!"
            )
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

        if pageImages:
            img = next(iter(pageImages.values()))
            thumbnail = await img.url
        else:
            thumbnail = "https://m.doughmination.gay/img/search.png"

        return components.panel(
            title=wikiPage.title,
            url=(await wikiPage.fullurl),
            body=pageSummary,
            thumbnail=thumbnail,
            footer="Powered by Wikipedia",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Wikipedia(bot))
