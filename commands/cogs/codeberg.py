import datetime as dt

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from bot import doughchecks


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

        async with self.session.get(
            f"https://codeberg.org/api/v1/users/{username}"
        ) as resp:
            if resp.status != 200:
                embed.title = None
                embed.color = discord.Color.red()
                embed.description = ":x: That Codeberg account does not exist."
                return embed
            data = await resp.json()

        username = data.get("username")
        async with self.session.get(
            f"https://codeberg.org/api/v1/users/{username}/repos", params={"limit": "1"}
        ) as resp:
            repo_count = resp.headers.get("X-Total-Count")

        embed.set_thumbnail(url=data.get("avatar_url"))
        embed.set_footer(text=f"User ID: {data.get('id')}")

        website = data.get("website")
        if website:
            website_label = website.removeprefix("https://").removeprefix("http://")

        embed.url = data.get("html_url")

        parts: list[str] = []
        if data.get("description"):
            parts.append(f"{data.get('description')}\n")
        if website:
            parts.append(f"\n> **Website**: [{website_label}]({website})")
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
        if repo_count:
            parts.append(f"\n> **Public Repositories**: {repo_count}")
        if data.get("created"):
            joined = dt.datetime.fromisoformat(data.get("created"))
            parts.append(f"\n> **Joined Codeberg**: <t:{int(joined.timestamp())}:D>")
        if data.get("is_admin"):
            parts.append("\n\n**This user is a Codeberg site administrator.**")

        embed.description = "".join(parts)
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Codeberg(bot))
