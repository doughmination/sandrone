import io
import json

import discord
from discord import app_commands
from discord.ext import commands

from sandrone import doughchecks
from utils import components
from utils.markdown import caretAt, codeBlock

maxInput = 4000
# A V2 message caps at 4000 chars of text; leave room for the fence and fields.
embedLimit = 3500

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
    @doughchecks.has_permissions(attach_files=True)
    async def jsonSlash(
        self,
        interaction: discord.Interaction,
        data: app_commands.Range[str, 1, maxInput],
        indent: app_commands.Choice[str] | None = None,
    ) -> None:
        await interaction.response.defer()

        view, file = self.getJsonReply(data, indent.value if indent else "2")
        await interaction.followup.send(view=view, file=file or discord.utils.MISSING)

    def getJsonReply(
        self, data: str, indent: str
    ) -> tuple[components.Panel, discord.File | None]:
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as error:
            return self.buildErrorPanel(data, error), None

        pretty = json.dumps(parsed, indent=indentValues[indent], ensure_ascii=False)
        fields = [
            ("Contains", describeData(parsed)),
            ("Size", f"{len(data):,} → {len(pretty):,} chars"),
        ]

        if len(pretty) <= embedLimit:
            return (
                components.panel(
                    title="✅ Formatted JSON",
                    body=codeBlock(pretty, "json"),
                    fields=fields,
                    footer="Sandrone",
                ),
                None,
            )

        attachment = discord.File(
            io.BytesIO(pretty.encode("utf-8")), filename="formatted.json"
        )
        return (
            components.panel(
                title="✅ Formatted JSON",
                body="That's too long to show inline, so here it is as a file.",
                fields=fields,
                files=["attachment://formatted.json"],
                footer="Sandrone",
            ),
            attachment,
        )

    def buildErrorPanel(
        self, data: str, error: json.JSONDecodeError
    ) -> components.Panel:
        return components.panel(
            title="❌ That isn't valid JSON",
            body=f"**{error.msg}**",
            fields=[
                (
                    f"Line {error.lineno}, column {error.colno}",
                    codeBlock(caretAt(data, error.pos)),
                ),
            ],
            footer="Sandrone",
            color=components.RED,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JsonFormat(bot))
