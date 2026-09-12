import json
import os
from pathlib import Path

import toml
from dotenvx import load_dotenv

load_dotenv()

repoRoot = Path(__file__).resolve().parent.parent
commandsDir = repoRoot / "commands"
cogsDir = commandsDir / "cogs"
settingsDir = commandsDir / "settings"
webDir = repoRoot / "web"
assetsDir = webDir / "assets"
dataDir = repoRoot / "data"

version = "unknown"
pyproject_toml_file = repoRoot / "pyproject.toml"
if pyproject_toml_file.exists() and pyproject_toml_file.is_file():
    data = toml.load(pyproject_toml_file)
    if "project" in data and "version" in data["project"]:
        version = data["project"]["version"]

TOKEN = os.getenv("BOT_TOKEN")
clientIdValue = os.getenv("CLIENT_ID")
clientId = int(clientIdValue) if clientIdValue and clientIdValue.strip() else None
devMode = os.getenv("DEV_MODE", "false").lower() == "true"
githubToken = os.getenv("GITHUB_TOKEN")

downloadsDirValue = os.getenv("DOWNLOADS_DIR")
downloadsDir = (
    Path(downloadsDirValue)
    if downloadsDirValue and downloadsDirValue.strip()
    else repoRoot / "downloads"
)
downloadsHost = os.getenv("DOWNLOADS_HOST", "0.0.0.0")
downloadsPort = int(os.getenv("DOWNLOADS_PORT", "2020"))
downloadsUrlValue = os.getenv("DOWNLOADS_URL")
downloadsUrl = (
    downloadsUrlValue.strip()
    if downloadsUrlValue and downloadsUrlValue.strip()
    else f"http://localhost:{downloadsPort}"
).rstrip("/")

siteUrlValue = os.getenv("SITE_URL")
siteUrl = (
    siteUrlValue.strip()
    if siteUrlValue and siteUrlValue.strip()
    else downloadsUrl
).rstrip("/")

downloadsRetention = int(os.getenv("DOWNLOADS_RETENTION_HOURS", "24"))
downloadsMaxSize = int(os.getenv("DOWNLOADS_MAX_SIZE_MIB", "2048")) * 1024 * 1024

prefixNames: list[str] = sorted(
    ("marrionette", "marionette", "sandrone"), key=len, reverse=True
)

owners: list[int] = [
    1464890289922641993,
    1025770042245251122,
]


def requireToken() -> str:
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is not set. Add it to your .env file before starting the bot."
        )
    return TOKEN

def requireClientID() -> int:
    if clientId is None:
        raise RuntimeError(
            "CLIENT_ID is not set. Add it to your .env before starting the bot."
        )
    return clientId

def requireGithubToken() -> str:
    if not githubToken:
        raise RuntimeError(
            "GITHUB_TOKEN is not set. Add it to your .env file to use /github."
        )
    return githubToken


cogStatePath = repoRoot / "cog_state.json"


def discoverCogHandles(directory: Path | None = None) -> list[str]:
    directory = directory if directory is not None else cogsDir
    handles = []
    for path in directory.rglob("*.py"):
        if path.stem == "__init__":
            continue
        relative = path.relative_to(directory).with_suffix("")
        handles.append(".".join(relative.parts))
    return sorted(handles)


def loadDisabled() -> set[str]:
    if not cogStatePath.exists():
        return set()
    try:
        data = json.loads(cogStatePath.read_text())
    except (json.JSONDecodeError, OSError):
        return set()
    return set(data.get("disabled", []))


def saveDisabled(disabled: set[str]) -> None:
    cogStatePath.write_text(json.dumps({"disabled": sorted(disabled)}, indent=2) + "\n")


def setDisabled(name: str, disabled: bool) -> None:
    current = loadDisabled()
    if disabled:
        current.add(name)
    else:
        current.discard(name)
    saveDisabled(current)
