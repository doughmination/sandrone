import os
from pathlib import Path

from dotenvx import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
prefix = os.getenv("BOT_PREFIX", "!")
devMode = os.getenv("DEV_MODE", "false").lower() == "true"
githubToken = os.getenv("GITHUB_TOKEN")

repoRoot = Path(__file__).resolve().parent.parent
commandsDir = repoRoot / "commands"
cogsDir = commandsDir / "cogs"
assetsDir = repoRoot / "assets"
