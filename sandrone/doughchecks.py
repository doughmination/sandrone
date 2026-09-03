import discord
from discord import app_commands


def has_permissions(*, guildOnly: bool = False, **perms: bool):
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

        permissions = interaction.app_permissions
        missing = [
            perm for perm, value in perms.items() if getattr(permissions, perm) != value
        ]
        if missing:
            raise app_commands.BotMissingPermissions(missing)
        return True

    return app_commands.check(predicate)
