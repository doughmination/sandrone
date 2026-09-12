import asyncio
from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest
from discord import app_commands

from sandrone import checks


def permissionPredicate(**permissions: bool):
    async def callback(interaction: discord.Interaction) -> None:
        pass

    checked = checks.hasPermissions(**permissions)(callback)
    return checked.__discord_app_commands_checks__[0]


def fakeInteraction(**kwargs) -> discord.Interaction:
    return cast(Any, SimpleNamespace(**kwargs))


def test_checks_application_permissions() -> None:
    predicate = permissionPredicate(embed_links=True)
    interaction = fakeInteraction(
        guild=object(),
        app_permissions=discord.Permissions(embed_links=False),
    )

    with pytest.raises(app_commands.BotMissingPermissions):
        asyncio.run(predicate(interaction))


def test_the_bot_holding_the_permission_passes() -> None:
    predicate = permissionPredicate(attach_files=True)
    interaction = fakeInteraction(
        guild=object(),
        app_permissions=discord.Permissions(attach_files=True),
    )

    assert asyncio.run(predicate(interaction)) is True


def test_guild_only_check_still_rejects_dms() -> None:
    predicate = permissionPredicate(guildOnly=True, embed_links=True)
    interaction = fakeInteraction(guild=None)

    with pytest.raises(app_commands.NoPrivateMessage):
        asyncio.run(predicate(interaction))


def test_dms_are_allowed_when_not_guild_only() -> None:
    predicate = permissionPredicate(embed_links=True)
    interaction = fakeInteraction(guild=None)

    assert asyncio.run(predicate(interaction)) is True


def test_an_unknown_permission_is_refused_at_import_time() -> None:
    with pytest.raises(TypeError):
        checks.hasPermissions(bend_spoons=True)


def test_what_a_command_needs_is_readable_back_off_it() -> None:
    async def callback(interaction: discord.Interaction) -> None:
        pass

    decorated = checks.hasPermissions(embed_links=True)(callback)
    command = app_commands.Command(
        name="sample", description="sample", callback=decorated
    )

    assert checks.requiredPermissions(command) == {"embed_links": True}
