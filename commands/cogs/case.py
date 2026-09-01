import re

import discord
from discord import app_commands
from discord.ext import commands

from sandrone import doughchecks
from utils.markdown import codeBlock

maxInput = 500

caseStyles = {
    "lowercase": "lower",
    "UPPERCASE": "upper",
    "Title Case": "title",
    "camelCase": "camel",
    "PascalCase": "pascal",
    "snake_case": "snake",
    "kebab-case": "kebab",
    "SCREAMING_SNAKE_CASE": "screaming",
}

styleLabels = {value: name for name, value in caseStyles.items()}

# Runs of capitals stay together unless a lowercase letter follows, so
# "parseXMLHttpRequest" splits as parse / XML / Http / Request.
wordPattern = re.compile(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+")

detectors = (
    ("SCREAMING_SNAKE_CASE", re.compile(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$")),
    ("snake_case", re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)+$")),
    ("kebab-case", re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)+$")),
    ("camelCase", re.compile(r"^[a-z][a-z0-9]*([A-Z][a-z0-9]*)+$")),
    ("PascalCase", re.compile(r"^([A-Z][a-z0-9]*){2,}$")),
    ("Title Case", re.compile(r"^[A-Z][a-z0-9]*( [A-Z][a-z0-9]*)*$")),
    ("UPPERCASE", re.compile(r"^[A-Z0-9]+( [A-Z0-9]+)*$")),
    ("lowercase", re.compile(r"^[a-z0-9]+( [a-z0-9]+)*$")),
)


def splitWords(text: str) -> list[str]:
    return wordPattern.findall(text)


def detectCase(text: str) -> str:
    stripped = text.strip()
    for name, pattern in detectors:
        if pattern.fullmatch(stripped):
            return name
    return "Mixed"


def applyCase(words: list[str], style: str) -> str:
    lowered = [word.lower() for word in words]

    if style == "lower":
        return " ".join(lowered)
    if style == "upper":
        return " ".join(word.upper() for word in lowered)
    if style == "title":
        return " ".join(word.capitalize() for word in lowered)
    if style == "camel":
        return lowered[0] + "".join(word.capitalize() for word in lowered[1:])
    if style == "pascal":
        return "".join(word.capitalize() for word in lowered)
    if style == "snake":
        return "_".join(lowered)
    if style == "kebab":
        return "-".join(lowered)
    return "_".join(word.upper() for word in lowered)


class Case(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="case", description="Convert text between cases")
    @app_commands.describe(
        text="The text to convert",
        to="The case to convert into",
    )
    @app_commands.choices(
        to=[
            app_commands.Choice(name=name, value=value)
            for name, value in caseStyles.items()
        ]
    )
    @doughchecks.has_permissions(embed_links=True)
    async def caseSlash(
        self,
        interaction: discord.Interaction,
        text: app_commands.Range[str, 1, maxInput],
        to: app_commands.Choice[str],
    ) -> None:
        await interaction.response.send_message(embed=self.getCaseEmbed(text, to.value))

    def getCaseEmbed(self, text: str, style: str) -> discord.Embed:
        words = splitWords(text)
        if not words:
            return discord.Embed(
                color=discord.Color.red(),
                description=":x: There are no letters or digits in that to re-case.",
            )

        user = self.bot.user
        embed = discord.Embed(color=discord.Color.fuchsia())
        embed.add_field(name=detectCase(text), value=codeBlock(text), inline=False)
        embed.add_field(
            name=styleLabels[style],
            value=codeBlock(applyCase(words, style)),
            inline=False,
        )
        embed.set_footer(
            text="Sandrone", icon_url=user.avatar.url if user and user.avatar else None
        )
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Case(bot))
