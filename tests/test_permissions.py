import unittest
from types import SimpleNamespace

import discord
from discord import app_commands

from sandrone.doughchecks import has_permissions


def permissionPredicate(**permissions: bool):
    checked = has_permissions(**permissions)(lambda: None)
    return checked.__discord_app_commands_checks__[0]


class PermissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_checks_application_permissions(self) -> None:
        predicate = permissionPredicate(embed_links=True)
        interaction = SimpleNamespace(
            guild=object(),
            permissions=discord.Permissions(embed_links=True),
            app_permissions=discord.Permissions(embed_links=False),
        )

        with self.assertRaises(app_commands.BotMissingPermissions):
            await predicate(interaction)

    async def test_user_permissions_do_not_block_bot_capabilities(self) -> None:
        predicate = permissionPredicate(attach_files=True)
        interaction = SimpleNamespace(
            guild=object(),
            permissions=discord.Permissions(attach_files=False),
            app_permissions=discord.Permissions(attach_files=True),
        )

        self.assertTrue(await predicate(interaction))

    async def test_guild_only_check_still_rejects_dms(self) -> None:
        predicate = permissionPredicate(guildOnly=True, embed_links=True)
        interaction = SimpleNamespace(guild=None)

        with self.assertRaises(app_commands.NoPrivateMessage):
            await predicate(interaction)


if __name__ == "__main__":
    unittest.main()
