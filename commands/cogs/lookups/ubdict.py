import re
import urllib.parse

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from sandrone import checks, mood
from utils import components


def formatText(text: str) -> str:
    text = re.sub(
        r"\[(.*?)\]",
        lambda match: (
            f"[{match.group(1)}](https://www.urbandictionary.com/define.php?term={urllib.parse.quote(match.group(1))})"
        ),
        text,
    )
    return text[:300].strip() + "..." if len(text) > 300 else text


class UrbanDictionary(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        await self.session.close()

    @app_commands.command(
        name="urban-dictionary",
        description="Lookup a definition on UrbDictionary",
    )
    @app_commands.describe(query="The query")
    @checks.hasPermissions(embed_links=True)
    @mood.sassy
    async def urbanDictionary(
        self, interaction: discord.Interaction, query: str
    ) -> None:
        await interaction.response.defer()
        await interaction.followup.send(view=await self.getUrbDefPanel(query))

    async def getUrbDefPanel(self, query: str) -> components.Panel:
        params = {"term": query}
        try:
            async with self.session.get(
                "https://api.urbandictionary.com/v0/define", params=params
            ) as resp:
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return components.error(
                "Couldn't reach Urban Dictionary — try again in a moment."
            )

        definitions = data.get("list") if isinstance(data, dict) else None
        if not definitions:
            return components.error(
                "Could not find that definition in Urban Dictionary, try /wiki instead"
            )

        reply = definitions[0]

        parts: list[str] = []
        parts.append(f"**Definition:**\n{formatText(reply.get('definition') or '')}")
        if reply.get("example"):
            parts.append(f"\n\n**Example:**\n{formatText(reply.get('example'))}")
        parts.append(
            f"\n\n-# <:likes:1540415874794528768>: {reply.get('thumbs_up')} | <:dislikes:1540415873678844035>: {reply.get('thumbs_down')}"
        )

        return components.panel(
            title=f"Searched '{query}' and found:",
            url=reply.get("permalink"),
            body="".join(parts),
            thumbnail="https://m.doughmination.gay/img/search.png",
            footer=f"by {reply.get('author')}, Urban Dictionary",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UrbanDictionary(bot))
