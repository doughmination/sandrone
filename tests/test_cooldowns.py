import asyncio
import datetime
import discord
from discord import app_commands
import pytest
from sandrone import checks, config
from sandrone.client import Tree
from types import SimpleNamespace
from typing import Any, cast

strangerId = 1


def fakeInteraction(userId: int = strangerId) -> discord.Interaction:
    return cast(
        Any,
        SimpleNamespace(
            user=SimpleNamespace(id=userId),
            created_at=datetime.datetime.now(datetime.UTC),
        ),
    )


def makeCommand(*decorators) -> app_commands.Command:
    async def callback(interaction: discord.Interaction) -> None:
        pass

    for decorator in reversed(decorators):
        callback = decorator(callback)
    return app_commands.Command(
        name="thing", description="A thing", callback=callback
    )


def runChecks(
    command: app_commands.Command, interaction: discord.Interaction
) -> None:
    for predicate in command.checks:
        asyncio.run(discord.utils.maybe_coroutine(predicate, interaction))


def test_a_command_with_no_cooldown_gets_the_default() -> None:
    command = makeCommand()
    checks.applyDefaultCooldown(command)

    assert len(command.checks) == 1
    assert checks.commandCooldown(command) == (
        checks.defaultRate,
        checks.defaultPer,
    )


def test_the_default_is_only_applied_once() -> None:
    command = makeCommand()
    checks.applyDefaultCooldown(command)
    checks.applyDefaultCooldown(command)

    assert len(command.checks) == 1


def test_an_explicit_cooldown_is_left_alone() -> None:
    command = makeCommand(checks.cooldown(1, 60))
    checks.applyDefaultCooldown(command)

    assert len(command.checks) == 1
    assert checks.commandCooldown(command) == (1, 60)


def test_a_user_is_stopped_once_they_run_out() -> None:
    command = makeCommand(checks.cooldown(2, 60))
    interaction = fakeInteraction()

    runChecks(command, interaction)
    runChecks(command, interaction)
    with pytest.raises(app_commands.CommandOnCooldown):
        runChecks(command, interaction)


def test_users_have_their_own_buckets() -> None:
    command = makeCommand(checks.cooldown(1, 60))

    runChecks(command, fakeInteraction(strangerId))
    runChecks(command, fakeInteraction(strangerId + 1))


def test_owners_are_never_held_back() -> None:
    command = makeCommand(checks.cooldown(1, 60))
    owner = fakeInteraction(config.owners[0])

    for _ in range(5):
        runChecks(command, owner)


def test_the_tree_gives_group_children_the_default() -> None:
    group = app_commands.Group(name="things", description="Things")

    @group.command(name="plain", description="No cooldown of its own")
    async def plain(interaction: discord.Interaction) -> None:
        pass

    @group.command(name="slow", description="Has its own cooldown")
    @checks.cooldown(1, 60)
    async def slow(interaction: discord.Interaction) -> None:
        pass

    tree = Tree(discord.Client(intents=discord.Intents.none()))
    tree.add_command(group)

    assert checks.commandCooldown(plain) == (
        checks.defaultRate,
        checks.defaultPer,
    )
    assert checks.commandCooldown(slow) == (1, 60)
    assert len(slow.checks) == 1
