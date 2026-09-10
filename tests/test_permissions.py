import asyncio
from types import SimpleNamespace

import discord
import pytest
from discord.ext import commands

from sandrone.doughchecks import has_permissions


def permissionPredicate(**permissions: bool):
    checked = has_permissions(**permissions)(lambda: None)
    return checked.__commands_checks__[0]


def fakeContext(**kwargs) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def test_checks_application_permissions() -> None:
    predicate = permissionPredicate(embed_links=True)
    ctx = fakeContext(
        guild=object(),
        permissions=discord.Permissions(embed_links=True),
        bot_permissions=discord.Permissions(embed_links=False),
    )

    with pytest.raises(commands.BotMissingPermissions):
        asyncio.run(predicate(ctx))


def test_user_permissions_do_not_block_bot_capabilities() -> None:
    predicate = permissionPredicate(attach_files=True)
    ctx = fakeContext(
        guild=object(),
        permissions=discord.Permissions(attach_files=False),
        bot_permissions=discord.Permissions(attach_files=True),
    )

    assert asyncio.run(predicate(ctx)) is True


def test_guild_only_check_still_rejects_dms() -> None:
    predicate = permissionPredicate(guildOnly=True, embed_links=True)
    ctx = fakeContext(guild=None)

    with pytest.raises(commands.NoPrivateMessage):
        asyncio.run(predicate(ctx))


def test_dms_are_allowed_when_not_guild_only() -> None:
    predicate = permissionPredicate(embed_links=True)
    ctx = fakeContext(guild=None)

    assert asyncio.run(predicate(ctx)) is True
