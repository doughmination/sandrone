import re
from collections.abc import Iterable
from typing import Any, NamedTuple, cast

import discord
from discord import app_commands
from discord.ext import commands

from sandrone import config, mood
from utils import components

MENU_TEMPLATE = r"help:(?P<section>[a-z0-9_]+)"

OVERVIEW = "overview"
CORE = "core"
OTHER = "other"


class TreeClient:
    tree: app_commands.CommandTree


class Section(NamedTuple):
    """How one commands/cogs folder is presented in the help menu."""

    label: str
    emoji: str
    blurb: str
    rank: int


SECTIONS: dict[str, Section] = {
    "fun": Section("Fun", "🎲", "Nonsense, on demand.", 10),
    "lookups": Section("Lookups", "🔍", "Fetch things from elsewhere.", 20),
    "media": Section("Media", "🎬", "Links, downloads, and embeds.", 30),
    "people": Section("People", "👤", "Users, profiles, and systems.", 40),
    "tools": Section("Tools", "🛠️", "Small utilities that do one job.", 50),
    "nsfw": Section("NSFW", "🔞", "Age-restricted channels only.", 60),
    "nerd": Section("Nerd", "🤓", "Nerd stuff like Maths", 70),
    OTHER: Section("Other", "📦", "Cogs that never picked a folder.", 800),
    CORE: Section("Core", "⚙️", "The bot's own plumbing.", 900),
}

UNKNOWN_RANK = 500


def sectionOf(key: str) -> Section:
    """Presentation for a section key, inventing one for unmapped folders."""
    if key in SECTIONS:
        return SECTIONS[key]
    return Section(key.replace("_", " ").title(), "📁", "", UNKNOWN_RANK)


def sectionKey(command: app_commands.Command) -> str:
    """Which folder under ``commands/`` a command was loaded from."""
    module = command.module or ""
    if module.startswith("commands.cogs."):
        parts = module.removeprefix("commands.cogs.").split(".")
        return parts[0] if len(parts) > 1 else OTHER
    if module.startswith("commands."):
        return CORE
    return OTHER


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


def groupedCommands(
    commandItems: Iterable[object],
) -> dict[str, list[app_commands.Command]]:
    """Commands bucketed by section key, sections in display order."""
    buckets: dict[str, list[app_commands.Command]] = {}
    for command in listedCommands(commandItems):
        buckets.setdefault(sectionKey(command), []).append(command)
    return dict(
        sorted(
            buckets.items(),
            key=lambda item: (sectionOf(item[0]).rank, sectionOf(item[0]).label),
        )
    )


def commandList(
    commandItems: Iterable[object],
) -> str:
    entries = [
        f"`/{command.qualified_name}` — {command.description}"
        for command in listedCommands(commandItems)
    ]
    return "\n".join(entries) or "Nothing is loaded. How embarrassing."


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def overviewBody(buckets: dict[str, list[app_commands.Command]]) -> str:
    lines = []
    for key, found in buckets.items():
        section = sectionOf(key)
        lines.append(
            f"{section.emoji} **{section.label}** — {plural(len(found), 'command')}"
        )
    return "\n".join(lines)


def menuRow(
    buckets: dict[str, list[app_commands.Command]], current: str
) -> discord.ui.ActionRow:
    options = [
        discord.SelectOption(
            label="Overview",
            value=OVERVIEW,
            emoji="📖",
            description="Every section at a glance.",
            default=current == OVERVIEW,
        )
    ]
    for key, found in list(buckets.items())[:24]:
        section = sectionOf(key)
        options.append(
            discord.SelectOption(
                label=section.label[:100],
                value=key,
                emoji=section.emoji,
                description=" · ".join(
                    part
                    for part in (plural(len(found), "command"), section.blurb)
                    if part
                )[:100],
                default=key == current,
            )
        )

    row = discord.ui.ActionRow()
    row.add_item(
        discord.ui.Select(
            custom_id=f"help:{current}",
            placeholder="Pick a section…",
            options=options,
        )
    )
    return row


def helpContainer(
    commandItems: Iterable[object], current: str = OVERVIEW
) -> discord.ui.Container:
    buckets = groupedCommands(commandItems)

    if current == OVERVIEW or current not in buckets:
        title = "Sandrone's command catalogue"
        body = (
            "These are the functions currently installed and operational. "
            "Try not to break anything.\n\n"
            f"Every command works as a slash command or by name — "
            f"`{config.prefixNames[0]} help`, or just @mention her.\n\n"
        )
        body += overviewBody(buckets) or "Nothing is loaded. How embarrassing."
        footer = (
            f"{plural(sum(len(f) for f in buckets.values()), 'command')} across "
            f"{plural(len(buckets), 'section')}. Pick one from the menu."
        )
    else:
        section = sectionOf(current)
        title = f"{section.emoji} {section.label}"
        body = f"{section.blurb}\n\n" if section.blurb else ""
        body += commandList(buckets[current])
        footer = "Commands update themselves when modules are loaded or unloaded."

    box = discord.ui.Container(accent_colour=components.FUCHSIA)
    box.add_item(discord.ui.TextDisplay(f"{components.heading(title)}\n\n{body}"))
    if buckets:
        box.add_item(menuRow(buckets, current))
    box.add_item(discord.ui.Separator(visible=False))
    box.add_item(discord.ui.TextDisplay(f"-# {footer}"))
    return box


def helpPanel(
    commandItems: Iterable[object], current: str = OVERVIEW
) -> components.Panel:
    return components.Panel(helpContainer(commandItems, current))


class HelpMenu(discord.ui.DynamicItem[discord.ui.Select], template=MENU_TEMPLATE):
    """The section dropdown — rebuilt from the live tree on every pick."""

    def __init__(self, customId: str) -> None:
        super().__init__(
            discord.ui.Select(
                custom_id=customId,
                options=[discord.SelectOption(label="_", value=OVERVIEW)],
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "HelpMenu":
        return cls(match.string)

    async def callback(self, interaction: discord.Interaction) -> None:
        client = cast(TreeClient, interaction.client)
        await interaction.response.edit_message(
            view=helpPanel(client.tree.get_commands(), self.item.values[0])
        )


@commands.hybrid_command(
    name="help",
    description="Show Sandrone's available commands",
    aliases=["commands", "h"],
)
@mood.sassy
async def helpCommand(ctx: commands.Context) -> None:
    client = cast(TreeClient, ctx.bot)
    await ctx.send(view=helpPanel(client.tree.get_commands()))


async def setup(bot: commands.Bot) -> None:
    bot.add_dynamic_items(HelpMenu)
    bot.add_command(helpCommand)  # registers the app command alongside it


async def teardown(bot: commands.Bot) -> None:
    bot.remove_command(helpCommand.name)
