from types import SimpleNamespace
from typing import cast

import discord
import pytest

from commands.settings import mods
from sandrone import config

guildId = 1234567890
otherGuildId = 9876543210
ownerId = config.owners[0]


@pytest.fixture(autouse=True)
def store(tmp_path):
    mods.db.path = tmp_path / "mods.jp"
    mods.db.reload()
    return mods.db


def member(
    memberId: int,
    *,
    manageGuild: bool = False,
    admin: bool = False,
    roles: tuple[int, ...] = (),
    inGuild: int = guildId,
) -> discord.Member:
    return cast(
        discord.Member,
        SimpleNamespace(
            id=memberId,
            guild=SimpleNamespace(id=inGuild),
            guild_permissions=discord.Permissions(
                manage_guild=manageGuild, administrator=admin
            ),
            roles=[SimpleNamespace(id=roleId) for roleId in roles],
        ),
    )


def test_a_bot_owner_is_not_a_mod_in_someone_elses_server() -> None:
    assert mods.isMod(member(ownerId)) is False


def test_a_bot_owner_with_manage_server_passes_like_anyone_else() -> None:
    assert mods.isMod(member(ownerId, manageGuild=True)) is True


def test_manage_server_and_administrator_both_pass() -> None:
    assert mods.isMod(member(1, manageGuild=True)) is True
    assert mods.isMod(member(2, admin=True)) is True


def test_a_stored_user_passes_without_any_server_permissions() -> None:
    mods.db.guild(guildId).key(mods.usersKey).add(42).save()

    assert mods.isMod(member(42)) is True
    assert mods.isMod(member(43)) is False


def test_a_stored_role_passes_for_anyone_holding_it() -> None:
    mods.db.guild(guildId).key(mods.rolesKey).add(99).save()

    assert mods.isMod(member(44, roles=(99,))) is True
    assert mods.isMod(member(44, roles=(100,))) is False


def test_a_grant_in_one_server_does_not_leak_into_another() -> None:
    mods.db.guild(guildId).key(mods.usersKey).add(42).save()

    assert mods.isMod(member(42, inGuild=otherGuildId)) is False
