from collections.abc import Iterable
from typing import cast

import discord
from discord import app_commands
from discord.ext import commands

from sandrone import mood
from utils import components


class TreeClient:
    tree: app_commands.CommandTree


def listedCommands(
    commandItems: Iterable[object],
) -> list[app_commands.Command]:
    """Return every runnable slash command from the currently loaded tree."""
    result: list[app_commands.Command] = []
    for command in commandItems:
        if isinstance(command, app_commands.Group):
            result.extend(listedCommands(command.commands))
        elif isinstance(command, app_commands.Command):
            result.append(command)
    return sorted(result, key=lambda command: command.qualified_name)


def commandList(
    commandItems: Iterable[object],
) -> str:
    entries = [
        f"`/{command.qualified_name}` — {command.description}"
        for command in listedCommands(commandItems)
    ]
    return "\n".join(entries) or "Nothing is loaded. How embarrassing."


def helpPanel(
    commandItems: Iterable[object],
) -> components.Panel:
    return components.panel(
        title="Sandrone's command catalogue",
        body=(
            "These are the functions currently installed and operational. "
            "Try not to break anything.\n\n"
            f"{commandList(commandItems)}"
        ),
        footer="Commands update themselves when modules are loaded or unloaded.",
    )


@app_commands.command(name="help", description="Show Sandrone's available commands")
@mood.sassy
async def helpSlash(interaction: discord.Interaction) -> None:
    client = cast(TreeClient, interaction.client)
    await interaction.response.send_message(view=helpPanel(client.tree.get_commands()))


async def setup(bot: commands.Bot) -> None:
    bot.tree.add_command(helpSlash)


async def teardown(bot: commands.Bot) -> None:
    bot.tree.remove_command(helpSlash.name)
