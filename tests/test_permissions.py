import asyncio
from types import SimpleNamespace

import discord
import pytest
from discord import app_commands

from sandrone.doughchecks import has_permissions


def permissionPredicate(**permissions: bool):
    checked = has_permissions(**permissions)(lambda: None)
    return checked.__discord_app_commands_checks__[0]


def test_checks_application_permissions() -> None:
    predicate = permissionPredicate(embed_links=True)
    interaction = SimpleNamespace(
        guild=object(),
        permissions=discord.Permissions(embed_links=True),
        app_permissions=discord.Permissions(embed_links=False),
    )

    with pytest.raises(app_commands.BotMissingPermissions):
        asyncio.run(predicate(interaction))


def test_user_permissions_do_not_block_bot_capabilities() -> None:
    predicate = permissionPredicate(attach_files=True)
    interaction = SimpleNamespace(
        guild=object(),
        permissions=discord.Permissions(attach_files=False),
        app_permissions=discord.Permissions(attach_files=True),
    )

    assert asyncio.run(predicate(interaction)) is True


def test_guild_only_check_still_rejects_dms() -> None:
    predicate = permissionPredicate(guildOnly=True, embed_links=True)
    interaction = SimpleNamespace(guild=None)

    with pytest.raises(app_commands.NoPrivateMessage):
        asyncio.run(predicate(interaction))
