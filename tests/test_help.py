from discord import app_commands, ui

from commands.help import (
    HelpMenu,
    commandList,
    groupedCommands,
    helpPanel,
    listedCommands,
    sectionKey,
)


def textOf(panel) -> str:
    return "\n".join(
        child.content
        for child in panel.children[0].children
        if isinstance(child, ui.TextDisplay)
    )


def selectOf(panel) -> ui.Select:
    row = next(
        child for child in panel.children[0].children if isinstance(child, ui.ActionRow)
    )
    return row.children[0]


async def callback(interaction):
    pass


def test_help_lists_commands_and_nested_group_commands() -> None:
    direct = app_commands.Command(
        name="alpha", description="First command", callback=callback
    )
    group = app_commands.Group(name="tools", description="Tool commands")
    nested = app_commands.Command(
        name="beta", description="Second command", callback=callback
    )
    group.add_command(nested)

    commands = listedCommands([group, direct])

    assert [command.qualified_name for command in commands] == ["alpha", "tools beta"]
    assert commandList([group, direct]) == (
        "`/alpha` — First command\n`/tools beta` — Second command"
    )


def moduleCommand(name: str, module: str) -> app_commands.Command:
    command = app_commands.Command(
        name=name, description=f"{name} command", callback=callback
    )
    command.module = module
    return command


def test_section_key_follows_the_folder_a_command_was_loaded_from() -> None:
    assert sectionKey(moduleCommand("animal", "commands.cogs.fun.animals")) == "fun"
    assert sectionKey(moduleCommand("qr", "commands.cogs.tools.qr")) == "tools"
    assert sectionKey(moduleCommand("genshin", "commands.cogs.genshin")) == "other"
    assert sectionKey(moduleCommand("links", "commands.links")) == "core"
    assert sectionKey(moduleCommand("stray", "")) == "other"


def test_grouped_commands_bucket_by_section_in_display_order() -> None:
    items = [
        moduleCommand("links", "commands.links"),
        moduleCommand("qr", "commands.cogs.tools.qr"),
        moduleCommand("animal", "commands.cogs.fun.animals"),
        moduleCommand("8ball", "commands.cogs.fun.eightball"),
        moduleCommand("weird", "commands.cogs.zzz.thing"),
    ]

    buckets = groupedCommands(items)

    assert list(buckets) == ["fun", "tools", "zzz", "core"]
    assert [command.name for command in buckets["fun"]] == ["8ball", "animal"]


def test_help_panel_offers_a_section_per_bucket_plus_overview() -> None:
    items = [
        moduleCommand("animal", "commands.cogs.fun.animals"),
        moduleCommand("qr", "commands.cogs.tools.qr"),
    ]

    select = selectOf(helpPanel(items))

    assert select.custom_id == "help:overview"
    assert [option.value for option in select.options] == ["overview", "fun", "tools"]
    assert [option.default for option in select.options] == [True, False, False]


def test_help_panel_for_a_section_lists_only_that_section() -> None:
    items = [
        moduleCommand("animal", "commands.cogs.fun.animals"),
        moduleCommand("qr", "commands.cogs.tools.qr"),
    ]

    panel = helpPanel(items, "fun")
    body = textOf(panel)

    assert "`/animal`" in body
    assert "`/qr`" not in body
    assert "Fun" in body
    assert selectOf(panel).custom_id == "help:fun"


def test_help_panel_falls_back_to_the_overview_for_an_unloaded_section() -> None:
    items = [moduleCommand("animal", "commands.cogs.fun.animals")]

    panel = helpPanel(items, "media")

    assert "Sandrone's command catalogue" in textOf(panel)
    assert [option.value for option in selectOf(panel).options] == ["overview", "fun"]


def test_help_panel_drops_the_menu_when_nothing_is_loaded() -> None:
    panel = helpPanel([])

    assert "Nothing is loaded" in textOf(panel)
    assert not any(
        isinstance(child, ui.ActionRow) for child in panel.children[0].children
    )


def test_help_menu_routes_every_section_custom_id() -> None:
    template = HelpMenu.__discord_ui_compiled_template__

    for section in ["overview", "fun", "nsfw", "zzz", "other", "core"]:
        assert template.fullmatch(f"help:{section}")
