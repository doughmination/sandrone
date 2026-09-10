import discord
from discord.ext import commands


def has_permissions(*, guildOnly: bool = False, **perms: bool):
    """Require the bot to hold ``perms`` in the invoking channel.

    A ``commands.check`` rather than an ``app_commands.check`` so it runs for
    both slash and prefix invocations of a hybrid command. ``ctx.bot_permissions``
    resolves to ``interaction.app_permissions`` on the slash path and to the
    channel's computed permissions on the prefix path.
    """
    invalid = perms.keys() - discord.Permissions.VALID_FLAGS.keys()
    if invalid:
        raise TypeError(f"Invalid permission(s): {', '.join(sorted(invalid))}")

    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            if guildOnly:
                raise commands.NoPrivateMessage(
                    "This command can only be used in a server."
                )
            return True

        permissions = ctx.bot_permissions
        missing = [
            perm for perm, value in perms.items() if getattr(permissions, perm) != value
        ]
        if missing:
            raise commands.BotMissingPermissions(missing)
        return True

    return commands.check(predicate)


def nsfw_only():
    """Restrict a hybrid command to age-restricted channels, on both paths.

    ``commands.is_nsfw`` covers the prefix side; the marker attribute is what
    ``hybrid_command`` reads to set ``nsfw=True`` on the generated app command.
    """

    def decorator(func):
        func.__discord_app_commands_is_nsfw__ = True
        return commands.is_nsfw()(func)

    return decorator
