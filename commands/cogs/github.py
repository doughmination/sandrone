import asyncio
import os

import discord
from discord import app_commands
from discord.ext import commands
from github import Auth, Github, GithubException
import colorful as cf

cf.use_true_colors()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

embedColor = discord.Color.fuchsia()
errorColor = discord.Color.red()


class GitHub(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="github", description="Look up a GitHub user")
    @app_commands.describe(username="The GitHub username to fetch information on")
    async def githubSlash(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        embed = await self.fetchUserEmbed(username)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="gh", description="Look up a GitHub user (alias for /github)")
    @app_commands.describe(username="The GitHub username to fetch information on")
    async def ghSlash(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        embed = await self.fetchUserEmbed(username)
        await interaction.followup.send(embed=embed)

    async def fetchUserEmbed(self, username: str) -> discord.Embed:
        username = username.removeprefix("@")
        return await asyncio.to_thread(self._buildEmbed, username)

    def _buildEmbed(self, username: str) -> discord.Embed:
        embed = discord.Embed(color=embedColor, title=username, description="")
        gh = Github(auth=Auth.Token(GITHUB_TOKEN))
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

            if user.bio:
                embed.description += f"{user.bio}\n"
            if user.blog:
                website = user.blog.removeprefix("https://").removeprefix("http://")
                embed.description += f"\n> **Website**: [{website}]({user.blog})"
            if user.email:
                embed.description += f"\n> **Email**: [{user.email}](mailto:{user.email})"
            if user.location:
                embed.description += f"\n> **Location**: {user.location}"
            if user.hireable:
                embed.description += "\n> **Hireable**: This user is available for hire."
            if user.company:
                embed.description += f"\n> **Company**: {user.company}"
            if user.followers:
                embed.description += f"\n> **Followers**: {user.followers}"
            if user.following:
                embed.description += f"\n> **Following**: {user.following}"
            if user.created_at:
                embed.description += f"\n> **Joined GitHub**: <t:{int(user.created_at.timestamp())}:D>"
            if user.public_repos:
                embed.description += f"\n> **Public Repositories**: {user.public_repos}"
            if user.public_gists:
                embed.description += f"\n> **Public Gists**: {user.public_gists}"
            if user.user_view_type != "public":
                embed.description += "\n\nThis user has set their profile as private."
            if user.site_admin:
                embed.description += "\n\n**This user is a GitHub site administrator.**"

            return embed
        finally:
            gh.close()


async def setup(bot: commands.Bot) -> None:
    if not GITHUB_TOKEN:
        print(cf.yellow(
            "[github] GITHUB_TOKEN is not set, skipping cog. "
            "To get a token, visit https://github.com/settings/tokens/new"
        ))
        return
    await bot.add_cog(GitHub(bot))
