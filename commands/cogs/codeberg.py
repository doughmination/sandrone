import datetime as dt

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from sandrone import doughchecks


class Codeberg(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        await self.session.close()

    @app_commands.command(name="codeberg", description="Look up a Codeberg user")
    @app_commands.describe(username="The Codeberg username to fetch information on")
    @doughchecks.has_permissions(embed_links=True)
    async def codebergSlash(
        self, interaction: discord.Interaction, username: str
    ) -> None:
        await interaction.response.defer()
        embed = await self.fetchUserEmbed(username)
        await interaction.followup.send(embed=embed)

    async def fetchUserEmbed(self, username: str) -> discord.Embed:
        embed = discord.Embed(color=discord.Color.fuchsia(), title=username)

        try:
            async with self.session.get(
                f"https://codeberg.org/api/v1/users/{username}"
            ) as resp:
                if resp.status != 200:
                    embed.title = None
                    embed.color = discord.Color.red()
                    embed.description = ":x: That Codeberg account does not exist."
                    return embed
                data = await resp.json()

            login = data.get("username") or username
            async with self.session.get(
                f"https://codeberg.org/api/v1/users/{login}/repos",
                params={"limit": "1"},
            ) as resp:
                repoCount = (
                    resp.headers.get("X-Total-Count") if resp.status == 200 else None
                )
        except (aiohttp.ClientError, TimeoutError):
            embed.title = None
            embed.color = discord.Color.red()
            embed.description = ":x: Couldn't reach Codeberg — try again in a moment."
            return embed

        embed.set_thumbnail(url=data.get("avatar_url"))
        embed.set_footer(text=f"User ID: {data.get('id')}")
        embed.url = data.get("html_url")

        website = data.get("website")

        parts: list[str] = []
        if data.get("description"):
            parts.append(f"{data.get('description')}\n")
        if website:
            label = website.removeprefix("https://").removeprefix("http://")
            parts.append(f"\n> **Website**: [{label}]({website})")
        if data.get("email"):
            parts.append(
                f"\n> **Email**: [{data.get('email')}](mailto:{data.get('email')})"
            )
        if data.get("location"):
            parts.append(f"\n> **Location**: {data.get('location')}")
        if data.get("followers_count"):
            parts.append(f"\n> **Followers**: {data.get('followers_count')}")
        if data.get("following_count"):
            parts.append(f"\n> **Following**: {data.get('following_count')}")
        if repoCount:
            parts.append(f"\n> **Public Repositories**: {repoCount}")
        if data.get("created"):
            joined = dt.datetime.fromisoformat(data.get("created"))
            parts.append(f"\n> **Joined Codeberg**: <t:{int(joined.timestamp())}:D>")
        if data.get("is_admin"):
            parts.append("\n\n**This user is a Codeberg site administrator.**")

        embed.description = "".join(parts)
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Codeberg(bot))
