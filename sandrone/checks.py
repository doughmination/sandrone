import discord
from discord import app_commands

from sandrone import mood
from utils import cf, errors

permsAttr = "__sandrone_bot_perms__"


def hasPermissions(*, guildOnly: bool = False, **perms: bool):
    """Require the bot to hold *perms* where the command was run.

    The permissions are also stashed on the callback so `debug perms` can list
    what the loaded commands actually need.
    """
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

    check = app_commands.check(predicate)

    def decorator(func):
        target = getattr(func, "callback", func)
        setattr(target, permsAttr, {**getattr(target, permsAttr, {}), **perms})
        return check(func)

    return decorator


def requiredPermissions(command: app_commands.Command) -> dict[str, bool]:
    """The bot permissions *command* was decorated with, for `debug perms`."""
    return dict(getattr(command.callback, permsAttr, {}))


def formatPermissions(permissions: list[str]) -> str:
    return ", ".join(
        f"`{perm.replace('_', ' ').replace('guild', 'server').title()}`"
        for perm in permissions
    )


async def respond(interaction: discord.Interaction, message: str) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


async def handleAppCommandError(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    if isinstance(error, app_commands.BotMissingPermissions):
        logged = errors.fromInteraction(interaction, error)
        await respond(
            interaction,
            f"I am missing {formatPermissions(error.missing_permissions)} to run"
            f" this command.{errors.note(logged)}",
        )
        return

    if isinstance(error, app_commands.MissingPermissions):
        await respond(
            interaction,
            f"You are missing {formatPermissions(error.missing_permissions)} to run this command.",
        )
        return

    if isinstance(error, app_commands.NoPrivateMessage):
        await respond(interaction, "This command can only be used in a server.")
        return

    if isinstance(error, app_commands.CommandOnCooldown):
        await respond(
            interaction, f"Slow down. Try again in {error.retry_after:.0f}s."
        )
        return

    if isinstance(error, mood.SassyDenial):
        return

    if isinstance(error, app_commands.CheckFailure):
        await respond(interaction, "You do not have permission to execute this command")
        return

    if isinstance(error, app_commands.CommandInvokeError):
        error = error.original  # type: ignore[assignment]

    logged = errors.fromInteraction(interaction, error)
    print(cf.red(f"[error] unhandled error in {interaction.command}: {error!r}"))
    await respond(
        interaction,
        f"Something went wrong running `{interaction.command}`:"
        f" {error}{errors.note(logged)}",
    )
