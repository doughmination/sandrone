import datetime as dt

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

EMBED_COLOR = discord.Color.blurple()
ERROR_COLOR = discord.Color.red()


class Codeberg(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        await self.session.close()

    @app_commands.command(name="codeberg", description="Look up a Codeberg user")
    @app_commands.describe(username="The Codeberg username to fetch information on")
    async def codeberg_slash(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        embed = await self.fetch_user_embed(username)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="cb", description="Look up a Codeberg user (alias for /codeberg)")
    @app_commands.describe(username="The Codeberg username to fetch information on")
    async def cb_slash(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        embed = await self.fetch_user_embed(username)
        await interaction.followup.send(embed=embed)

    async def fetch_user_embed(self, username: str) -> discord.Embed:
        embed = discord.Embed(color=EMBED_COLOR, title=username, description="")

        async with self.session.get(f"https://codeberg.org/api/v1/users/{username}") as resp:
            if resp.status != 200:
                embed.title = None
                embed.color = ERROR_COLOR
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
        if data.get("description"):
            embed.description += f"{data.get('description')}\n"
        if website:
            embed.description += f"\n> **Website**: [{website_label}]({website})"
        if data.get("email"):
            embed.description += f"\n> **Email**: [{data.get('email')}](mailto:{data.get('email')})"
        if data.get("location"):
            embed.description += f"\n> **Location**: {data.get('location')}"
        if data.get("followers_count"):
            embed.description += f"\n> **Followers**: {data.get('followers_count')}"
        if data.get("following_count"):
            embed.description += f"\n> **Following**: {data.get('following_count')}"
        if repo_count:
            embed.description += f"\n> **Public Repositories**: {repo_count}"
        if data.get("created"):
            joined = dt.datetime.fromisoformat(data.get("created"))
            embed.description += f"\n> **Joined Codeberg**: <t:{int(joined.timestamp())}:D>"
        if data.get("is_admin"):
            embed.description += "\n\n**This user is a Codeberg site administrator.**"

        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Codeberg(bot))
