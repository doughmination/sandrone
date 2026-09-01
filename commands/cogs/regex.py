import re

import discord
from discord import app_commands
from discord.ext import commands

from sandrone import doughchecks
from utils.markdown import caretAt, codeBlock

maxInput = 500
fieldLimit = 1024

# (a+)+ and friends — a quantified group whose body is itself quantified.
nestedQuantifier = re.compile(r"\((?:[^()]*[+*][^()]*)\)\s*[+*]")
emptyBranch = re.compile(r"\|\||\(\||\|\)")

flagNames = {
    re.IGNORECASE: "IGNORECASE",
    re.MULTILINE: "MULTILINE",
    re.DOTALL: "DOTALL",
    re.VERBOSE: "VERBOSE",
    re.ASCII: "ASCII",
}


def describeFlags(compiled: re.Pattern[str]) -> str:
    names = [name for flag, name in flagNames.items() if compiled.flags & flag]
    return ", ".join(f"`{name}`" for name in names) if names else "None"


def describeGroups(compiled: re.Pattern[str]) -> str:
    if not compiled.groups:
        return "No capturing groups"

    named = compiled.groupindex
    plural = "s" if compiled.groups != 1 else ""
    summary = f"{compiled.groups} capturing group{plural}"
    if not named:
        return summary

    listed = ", ".join(f"`{name}` (#{index})" for name, index in named.items())
    return f"{summary}\nNamed: {listed}"


def findIssues(pattern: str, compiled: re.Pattern[str]) -> tuple[list[str], list[str]]:
    """Real problems first, then advisory notes that shouldn't raise an alarm."""
    warnings: list[str] = []
    notes: list[str] = []

    if pattern != pattern.strip():
        warnings.append(
            "⚠️ There's whitespace at the start or end of the pattern — "
            "it has to match literally, which is usually a paste mistake."
        )

    if nestedQuantifier.search(pattern):
        warnings.append(
            "⚠️ A quantified group contains another quantifier (like `(a+)+`). "
            "On a near-miss this can backtrack forever — that's how ReDoS hangs happen."
        )

    if emptyBranch.search(pattern):
        warnings.append(
            "⚠️ One alternation branch is empty, so it matches nothing at all. "
            "`(a|)` is almost always meant to be `(a)?`."
        )

    if compiled.fullmatch("") is not None:
        warnings.append(
            "⚠️ The whole pattern matches the empty string, so it will accept "
            "empty input. Check your `*` quantifiers if that wasn't deliberate."
        )

    anchoredStart = pattern.startswith(("^", r"\A"))
    anchoredEnd = pattern.endswith(("$", r"\Z")) and not pattern.endswith(r"\$")
    if not anchoredStart and not anchoredEnd:
        notes.append(
            "ℹ️ Unanchored, so it matches anywhere inside a string. Add `^` and `$` "
            "if you meant to validate a whole value."
        )

    return warnings, notes


class Regex(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="regex", description="Check a regular expression and flag its problems"
    )
    @app_commands.describe(pattern="The regular expression to check")
    @doughchecks.has_permissions(embed_links=True)
    async def regexSlash(
        self,
        interaction: discord.Interaction,
        pattern: app_commands.Range[str, 1, maxInput],
    ) -> None:
        await interaction.response.send_message(embed=self.getRegexEmbed(pattern))

    def getRegexEmbed(self, pattern: str) -> discord.Embed:
        user = self.bot.user
        try:
            compiled = re.compile(pattern)
        except re.error as error:
            embed = self.buildErrorEmbed(pattern, error)
        else:
            embed = self.buildValidEmbed(pattern, compiled)

        embed.set_footer(
            text="Sandrone", icon_url=user.avatar.url if user and user.avatar else None
        )
        return embed

    def buildErrorEmbed(self, pattern: str, error: re.error) -> discord.Embed:
        embed = discord.Embed(
            color=discord.Color.red(),
            title="❌ Invalid pattern",
            description=f"**{error.msg}**",
        )

        position = error.pos if error.pos is not None else 0
        embed.add_field(
            name=f"Column {position + 1}",
            value=codeBlock(caretAt(pattern, position)),
            inline=False,
        )
        return embed

    def buildValidEmbed(self, pattern: str, compiled: re.Pattern[str]) -> discord.Embed:
        warnings, notes = findIssues(pattern, compiled)
        embed = discord.Embed(
            color=discord.Color.orange() if warnings else discord.Color.green(),
            title="⚠️ Valid, with caveats" if warnings else "✅ Valid pattern",
            description=codeBlock(pattern),
        )

        embed.add_field(name="Groups", value=describeGroups(compiled), inline=True)
        embed.add_field(name="Flags", value=describeFlags(compiled), inline=True)

        if warnings:
            embed.add_field(
                name="Issues", value="\n\n".join(warnings)[:fieldLimit], inline=False
            )
        if notes:
            embed.add_field(
                name="Worth knowing",
                value="\n\n".join(notes)[:fieldLimit],
                inline=False,
            )
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Regex(bot))
