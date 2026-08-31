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
pyproject_toml_file = repoRoot / "pyproject.toml"
if pyproject_toml_file.exists() and pyproject_toml_file.is_file():
    data = toml.load(pyproject_toml_file)
    if "project" in data and "version" in data["project"]:
        version = data["project"]["version"]

TOKEN = os.getenv("BOT_TOKEN")
prefix = os.getenv("BOT_PREFIX", "!")
devMode = os.getenv("DEV_MODE", "false").lower() == "true"
githubToken = os.getenv("GITHUB_TOKEN")

downloadsDir = Path(os.getenv("DOWNLOADS_DIR", str(repoRoot / "downloads")))
downloadsHost = os.getenv("DOWNLOADS_HOST", "0.0.0.0")
downloadsPort = int(os.getenv("DOWNLOADS_PORT", "2020"))
downloadsUrl = os.getenv("DOWNLOADS_URL", f"http://localhost:{downloadsPort}").rstrip(
    "/"
)
downloadsRetention = int(os.getenv("DOWNLOADS_RETENTION_HOURS", "24"))
downloadsMaxSize = int(os.getenv("DOWNLOADS_MAX_SIZE_MIB", "2048")) * 1024 * 1024

owners: list[int] = [
    1464890289922641993,
    1025770042245251122,
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
