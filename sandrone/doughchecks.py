import discord
from discord import app_commands


class MissingPermissions(app_commands.MissingPermissions):
    """Raised by `has_permissions` when the invoker lacks a required permission.

    Subclasses discord.py's own MissingPermissions, so it keeps
    `.missing_permissions` and is still caught by anything handling
    `app_commands.CheckFailure`."""


def has_permissions(*, guildOnly: bool = False, **perms: bool):
    """Check that the invoker has every listed permission.

    Permission names must match the properties on `discord.Permissions`;
    invalid ones raise TypeError when the cog is imported rather than when
    the command is run.

    Outside a server there are no channel permissions to read, so the
    permission check is skipped and the command runs, keeping the DM and
    user-install contexts the tree allows. Pass `guildOnly=True` on commands
    that genuinely need a server; those raise NoPrivateMessage instead."""

    invalid = perms.keys() - discord.Permissions.VALID_FLAGS.keys()
    if invalid:
        raise TypeError(f"Invalid permission(s): {', '.join(sorted(invalid))}")

    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            if guildOnly:
                raise app_commands.NoPrivateMessage(
                    "This command can only be used in a server."
                )
            return True

        permissions = interaction.permissions
        missing = [
            perm for perm, value in perms.items() if getattr(permissions, perm) != value
        ]
        if missing:
            raise MissingPermissions(missing)
        return True

    return app_commands.check(predicate)
