from discord import app_commands

from commands.help import commandList, listedCommands


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
