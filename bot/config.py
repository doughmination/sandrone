import os
from pathlib import Path

import toml
from dotenvx import load_dotenv

load_dotenv()

repoRoot = Path(__file__).resolve().parent.parent
commandsDir = repoRoot / "commands"
cogsDir = commandsDir / "cogs"
assetsDir = repoRoot / "assets"

version = "unknown"
# adopt path to your pyproject.toml
pyproject_toml_file = repoRoot / "pyproject.toml"
if pyproject_toml_file.exists() and pyproject_toml_file.is_file():
    data = toml.load(pyproject_toml_file)
    # check project.version
    if "project" in data and "version" in data["project"]:
        version = data["project"]["version"]

TOKEN = os.getenv("BOT_TOKEN")
prefix = os.getenv("BOT_PREFIX", "!")
devMode = os.getenv("DEV_MODE", "false").lower() == "true"
githubToken = os.getenv("GITHUB_TOKEN")

# Discord user IDs allowed to run owner-only commands (e.g. /cog).
owners: list[int] = [
    1464890289922641993,
]


def requireToken() -> str:
    """The bot cannot run without a token, so fail with a clear message."""
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is not set. Add it to your .env file before starting the bot."
        )
    return TOKEN


def requireGithubToken() -> str:
    """Only the /github command needs this, so it is checked on use."""
    if not githubToken:
        raise RuntimeError(
            "GITHUB_TOKEN is not set. Add it to your .env file to use /github."
        )
    return githubToken
