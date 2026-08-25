import asyncio

import discord
from discord import app_commands
from discord.ext import commands
from github import Auth, Github, GithubException

from bot.config import githubToken as GITHUB_TOKEN
from bot.config import requireGithubToken
from utils.colors import cf

embedColor = discord.Color.fuchsia()
errorColor = discord.Color.red()


class GitHub(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="github", description="Look up a GitHub user")
    @app_commands.describe(username="The GitHub username to fetch information on")
    async def githubSlash(
        self, interaction: discord.Interaction, username: str
    ) -> None:
        await interaction.response.defer()
        embed = await self.fetchUserEmbed(username)
        await interaction.followup.send(embed=embed)

    async def fetchUserEmbed(self, username: str) -> discord.Embed:
        username = username.removeprefix("@")
        return await asyncio.to_thread(self._buildEmbed, username)

    def _buildEmbed(self, username: str) -> discord.Embed:
        embed = discord.Embed(color=embedColor, title=username)
        gh = Github(auth=Auth.Token(requireGithubToken()))
        try:
            try:
                user = gh.get_user(username)
                _ = user.id  # forces the request now, so a missing user raises here
            except GithubException:
                embed.title = None
                embed.color = errorColor
                embed.description = ":x: That GitHub account does not exist."
                return embed

            embed.url = user.html_url
            embed.set_thumbnail(url=user.avatar_url)
            embed.set_footer(text=f"User ID: {user.id}")

            parts: list[str] = []
            if user.bio:
                parts.append(f"{user.bio}\n")
            if user.blog:
                website = user.blog.removeprefix("https://").removeprefix("http://")
                parts.append(f"\n> **Website**: [{website}]({user.blog})")
            if user.email:
                parts.append(f"\n> **Email**: [{user.email}](mailto:{user.email})")
            if user.location:
                parts.append(f"\n> **Location**: {user.location}")
            if user.hireable:
                parts.append("\n> **Hireable**: This user is available for hire.")
            if user.company:
                parts.append(f"\n> **Company**: {user.company}")
            if user.followers:
                parts.append(f"\n> **Followers**: {user.followers}")
            if user.following:
                parts.append(f"\n> **Following**: {user.following}")
            if user.created_at:
                parts.append(
                    f"\n> **Joined GitHub**: <t:{int(user.created_at.timestamp())}:D>"
                )
            if user.public_repos:
                parts.append(f"\n> **Public Repositories**: {user.public_repos}")
            if user.public_gists:
                parts.append(f"\n> **Public Gists**: {user.public_gists}")
            if user.user_view_type != "public":
                parts.append("\n\nThis user has set their profile as private.")
            if user.site_admin:
                parts.append("\n\n**This user is a GitHub site administrator.**")

            embed.description = "".join(parts)
            return embed
        finally:
            gh.close()


async def setup(bot: commands.Bot) -> None:
    if not GITHUB_TOKEN:
        print(
            cf.yellow(
                "[github] GITHUB_TOKEN is not set, skipping cog. "
                "To get a token, visit https://github.com/settings/tokens/new"
            )
        )
        return
    await bot.add_cog(GitHub(bot))
