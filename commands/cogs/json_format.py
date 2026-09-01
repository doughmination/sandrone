import io
import json

import discord
from discord import app_commands
from discord.ext import commands

from sandrone import doughchecks
from utils.markdown import caretAt, codeBlock

maxInput = 4000
# Embed descriptions cap at 4096; leave room for the code fence.
embedLimit = 3900

indentStyles = {
    "2 spaces": "2",
    "4 spaces": "4",
    "Tab": "tab",
}

indentValues: dict[str, int | str] = {"2": 2, "4": 4, "tab": "\t"}

typeNames = {
    str: "String",
    bool: "Boolean",
    int: "Number",
    float: "Number",
}


def describeData(data: object) -> str:
    if isinstance(data, dict):
        return f"Object · {len(data)} key{'s' if len(data) != 1 else ''}"
    if isinstance(data, list):
        return f"Array · {len(data)} item{'s' if len(data) != 1 else ''}"
    if data is None:
        return "null"
    return typeNames.get(type(data), "Value")


class JsonFormat(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="json", description="Pretty-print compact JSON")
    @app_commands.describe(
        data="The JSON to format",
        indent="How far to indent each level (defaults to 2 spaces)",
    )
    @app_commands.choices(
        indent=[
            app_commands.Choice(name=name, value=value)
            for name, value in indentStyles.items()
        ]
    )
    @doughchecks.has_permissions(embed_links=True, attach_files=True)
    async def jsonSlash(
        self,
        interaction: discord.Interaction,
        data: app_commands.Range[str, 1, maxInput],
        indent: app_commands.Choice[str] | None = None,
    ) -> None:
        await interaction.response.defer()

        embed, file = self.getJsonReply(data, indent.value if indent else "2")
        await interaction.followup.send(embed=embed, file=file or discord.utils.MISSING)

    def getJsonReply(
        self, data: str, indent: str
    ) -> tuple[discord.Embed, discord.File | None]:
        user = self.bot.user
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as error:
            embed = self.buildErrorEmbed(data, error)
            embed.set_footer(
                text="Sandrone",
                icon_url=user.avatar.url if user and user.avatar else None,
            )
            return embed, None

        pretty = json.dumps(parsed, indent=indentValues[indent], ensure_ascii=False)

        embed = discord.Embed(color=discord.Color.fuchsia(), title="✅ Formatted JSON")
        embed.add_field(name="Contains", value=describeData(parsed), inline=True)
        embed.add_field(
            name="Size",
            value=f"{len(data):,} → {len(pretty):,} chars",
            inline=True,
        )

        attachment: discord.File | None = None
        if len(pretty) <= embedLimit:
            embed.description = codeBlock(pretty, "json")
        else:
            embed.description = (
                "That's too long to show inline, so here it is as a file."
            )
            attachment = discord.File(
                io.BytesIO(pretty.encode("utf-8")), filename="formatted.json"
            )

        embed.set_footer(
            text="Sandrone", icon_url=user.avatar.url if user and user.avatar else None
        )
        return embed, attachment

    def buildErrorEmbed(self, data: str, error: json.JSONDecodeError) -> discord.Embed:
        embed = discord.Embed(
            color=discord.Color.red(),
            title="❌ That isn't valid JSON",
            description=f"**{error.msg}**",
        )
        embed.add_field(
            name=f"Line {error.lineno}, column {error.colno}",
            value=codeBlock(caretAt(data, error.pos)),
            inline=False,
        )
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JsonFormat(bot))
