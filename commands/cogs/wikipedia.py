import discord
import wikipediaapi
from discord import app_commands
from discord.ext import commands

from sandrone import config, doughchecks


def format_text(text: str) -> str:
    return text[:500].strip() + "..." if len(text) > 500 else text


class Wikipedia(commands.Cog):
    def __init__(self, bot):
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
            user_agent=f"UV-Bot-{config.version} (https://github.com/doughmination/UV-Bot)",
            language="en",
        )
        wiki_page = wiki.page(query)
        if not await wiki_page.exists():
            embed = discord.Embed(color=discord.Color.red())
            embed.title = None
            embed.description = ":x: That Wikipedia page does not exist. Try adjusting your capitalisation, as results are occasionally case-sensitive!"
            return embed
        elif "Category:All disambiguation pages" in (await wiki_page.categories):
            page_summary = f'Disambiguations for "{query}":'
            page_links = await wiki_page.links
            for name in page_links:
                page_summary += f"\n- {name}"

            page_images = {}
            page_summary = format_text(page_summary)
        else:
            page_images = await wiki_page.images
            page_summary = format_text(await wiki_page.summary)

        embed = discord.Embed(
            title=wiki_page.title,
            description=page_summary,
            url=(await wiki_page.fullurl),
            color=discord.Color.fuchsia(),
        )
        embed.set_footer(
            text="Powered by Wikipedia",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/2/2e/Wikipedia_W_favicon_on_white_background.png",
        )
        if page_images:
            img = next(iter(page_images.values()))
            embed.set_thumbnail(url=await img.url)
        else:
            embed.set_thumbnail(url="https://m.doughmination.gay/img/search.png")
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Wikipedia(bot))
