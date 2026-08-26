import asyncio

import discord
from discord import app_commands
from discord.ext import commands
from github import Auth, Github, GithubException

from bot import config, doughchecks
from bot.config import githubToken as GITHUB_TOKEN
from utils.colors import cf

ownerGithub = "doughmination"

ownerOrgs = [
    "Clove-Web",
    "Clove-Archives",
    "Girls-Network",
    "Is-A-Stupid-Cat",
]

ownerOrgLookup = {org.lower() for org in ownerOrgs}


def normalizeRepo(repository: str) -> str | None:
    text = repository.strip().removeprefix("@")
    text = text.removeprefix("https://").removeprefix("http://")
    text = text.removeprefix("www.").removeprefix("github.com/")
    text = text.removesuffix("/").removesuffix(".git")

    parts = [part.strip() for part in text.split("/")]
    if len(parts) != 2 or not all(parts):
        return None
    return "/".join(parts)


class GitHub(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="github", description="Look up a GitHub user")
    @app_commands.describe(username="The GitHub username to fetch information on")
    @doughchecks.has_permissions(embed_links=True)
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
        embed = discord.Embed(color=discord.Color.fuchsia(), title=username)
        gh = Github(auth=Auth.Token(config.requireGithubToken()))
        try:
            try:
                user = gh.get_user(username)
                _ = user.id
            except GithubException:
                embed.title = None
                embed.color = discord.Color.red()
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
            privateRepos = self._fetchPrivateRepos(gh, username)
            if privateRepos is not None:
                parts.append(f"\n> **Private Repositories**: {privateRepos}")
            if user.user_view_type != "public":
                parts.append("\n\nThis user has set their profile as private.")
            if user.site_admin:
                parts.append("\n\n**This user is a GitHub site administrator.**")

            embed.description = "".join(parts)
            return embed
        finally:
            gh.close()

    def _fetchPrivateRepos(self, gh: Github, username: str) -> int | None:
        lookup = username.lower()
        try:
            if lookup == ownerGithub:
                me = gh.get_user()
                if me.login.lower() != lookup:
                    return None
                return me.total_private_repos
            if lookup in ownerOrgLookup:
                return gh.get_organization(username).total_private_repos
        except GithubException:
            return None
        return None

    @app_commands.command(name="repo", description="Look up a GitHub repository")
    @app_commands.describe(repository="The repository to fetch, as username/repo")
    @doughchecks.has_permissions(embed_links=True)
    async def repoSlash(
        self, interaction: discord.Interaction, repository: str
    ) -> None:
        await interaction.response.defer()
        embed = await self.fetchRepoEmbed(repository)
        await interaction.followup.send(embed=embed)

    async def fetchRepoEmbed(self, repository: str) -> discord.Embed:
        return await asyncio.to_thread(self._buildRepoEmbed, repository)

    def _buildRepoEmbed(self, repository: str) -> discord.Embed:
        embed = discord.Embed(color=discord.Color.fuchsia())

        fullName = normalizeRepo(repository)
        if fullName is None:
            embed.color = discord.Color.red()
            embed.description = ":x: Give the repository as `username/repo`."
            return embed

        gh = Github(auth=Auth.Token(config.requireGithubToken()))
        try:
            try:
                repo = gh.get_repo(fullName)
                _ = repo.id
            except GithubException:
                embed.color = discord.Color.red()
                embed.description = ":x: That repository does not exist."
                return embed

            embed.title = repo.full_name
            embed.url = repo.html_url
            embed.set_thumbnail(url=repo.owner.avatar_url)
            if repo.description:
                embed.description = repo.description

            embed.add_field(
                name="Stars",
                value=f"[{repo.stargazers_count}]({repo.html_url}/stargazers)",
            )
            embed.add_field(
                name="Forks",
                value=f"[{repo.forks_count}]({repo.html_url}/forks)",
            )
            embed.add_field(
                name="Open issues",
                value=f"[{repo.open_issues_count}]({repo.html_url}/issues)",
            )
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
