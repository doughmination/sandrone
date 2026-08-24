import discord
from discord import app_commands


class MissingPermissions(app_commands.MissingPermissions):
    """Raised by `has_permissions` when the invoker lacks a required permission.

    Subclasses discord.py's own MissingPermissions, so it keeps
    `.missing_permissions` and is still caught by anything handling
    `app_commands.CheckFailure`."""


def has_permissions(*, guildOnly: bool = True, **perms: bool):
    """Check that the invoker has every listed permission.

    Permission names must match the properties on `discord.Permissions`;
    invalid ones raise TypeError when the cog is imported rather than when
    the command is run.

    With `guildOnly` (the default), running the command outside a server
    raises NoPrivateMessage instead of reporting every permission as missing,
    since the tree allows DM and user-install contexts."""

    invalid = perms.keys() - discord.Permissions.VALID_FLAGS.keys()
    if invalid:
        raise TypeError(f"Invalid permission(s): {', '.join(sorted(invalid))}")

    async def predicate(interaction: discord.Interaction) -> bool:
        if guildOnly and interaction.guild is None:
            raise app_commands.NoPrivateMessage(
                "This command can only be used in a server."
            )

        permissions = interaction.permissions
        missing = [
            perm for perm, value in perms.items() if getattr(permissions, perm) != value
        ]
        if missing:
            raise MissingPermissions(missing)
        return True

    return app_commands.check(predicate)
