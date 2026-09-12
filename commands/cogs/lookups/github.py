import asyncio

import discord
from discord import app_commands
from discord.ext import commands
from github import Auth, Github, GithubException

from sandrone import checks, config, mood
from sandrone.config import githubToken as GITHUB_TOKEN
from utils import cf, components

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

    @app_commands.command(
        name="github", description="Look up a GitHub user"
    )
    @app_commands.describe(username="The GitHub username to fetch information on")
    @checks.hasPermissions(embed_links=True)
    @mood.sassy
    async def github(
        self, interaction: discord.Interaction, username: str
    ) -> None:
        await interaction.response.defer()
        await interaction.followup.send(view=await self.fetchUserPanel(username))

    async def fetchUserPanel(self, username: str) -> components.Panel:
        username = username.removeprefix("@")
        return await asyncio.to_thread(self._buildPanel, username)

    def _buildPanel(self, username: str) -> components.Panel:
        gh = Github(auth=Auth.Token(config.requireGithubToken()))
        try:
            try:
                user = gh.get_user(username)
                _ = user.id
            except GithubException:
                return components.error("That GitHub account does not exist.")

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

            return components.panel(
                title=username,
                url=user.html_url,
                body="".join(parts),
                thumbnail=user.avatar_url,
                footer=f"User ID: {user.id} · GitHub",
            )
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

    @app_commands.command(
        name="repo", description="Look up a GitHub repository"
    )
    @app_commands.describe(repository="The repository to fetch, as username/repo")
    @checks.hasPermissions(embed_links=True)
    @mood.sassy
    async def repo(
        self, interaction: discord.Interaction, repository: str
    ) -> None:
        await interaction.response.defer()
        await interaction.followup.send(view=await self.fetchRepoPanel(repository))

    async def fetchRepoPanel(self, repository: str) -> components.Panel:
        return await asyncio.to_thread(self._buildRepoPanel, repository)

    def _buildRepoPanel(self, repository: str) -> components.Panel:
        fullName = normalizeRepo(repository)
        if fullName is None:
            return components.error("Give the repository as `username/repo`.")

        gh = Github(auth=Auth.Token(config.requireGithubToken()))
        try:
            try:
                repo = gh.get_repo(fullName)
                _ = repo.id
            except GithubException:
                return components.error("That repository does not exist.")

            return components.panel(
                title=repo.full_name,
                url=repo.html_url,
                body=repo.description or None,
                fields=[
                    ("Stars", f"[{repo.stargazers_count}]({repo.html_url}/stargazers)"),
                    ("Forks", f"[{repo.forks_count}]({repo.html_url}/forks)"),
                    (
                        "Open issues",
                        f"[{repo.open_issues_count}]({repo.html_url}/issues)",
                    ),
                ],
                thumbnail=repo.owner.avatar_url,
                footer="GitHub",
            )
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
