import discord
from discord import app_commands
import math
from sandrone import config, mood
from utils import cf, errors

permsAttr = "__sandrone_bot_perms__"
cooldownAttr = "__sandrone_cooldown__"

# Every command gets this unless it's decorated with its own `cooldown`.
defaultRate = 3
defaultPer = 10.0


def perUserCooldown(rate: int, per: float):
    """A per-user cooldown check that owners are never held back by."""

    def factory(
        interaction: discord.Interaction,
    ) -> app_commands.Cooldown | None:
        if interaction.user.id in config.owners:
            return None
        return app_commands.Cooldown(rate, per)

    return app_commands.checks.dynamic_cooldown(factory)


def cooldown(rate: int, per: float):
    """Let each user run the command *rate* times every *per* seconds.

    The limit is stashed on the callback so the default cooldown knows to
    leave the command alone.
    """
    check = perUserCooldown(rate, per)

    def decorator(func):
        target = getattr(func, "callback", func)
        setattr(target, cooldownAttr, (rate, per))
        return check(func)

    return decorator


def applyDefaultCooldown(
    command: app_commands.Command | app_commands.ContextMenu,
) -> None:
    """Give *command* the default cooldown if it has none of its own.

    Cogs copy their commands but share callbacks, so the default is
    marked on the command itself, not the callback.
    """
    if hasattr(command.callback, cooldownAttr) or hasattr(
        command, cooldownAttr
    ):
        return
    perUserCooldown(defaultRate, defaultPer)(command)
    setattr(command, cooldownAttr, (defaultRate, defaultPer))


def commandCooldown(
    command: app_commands.Command | app_commands.ContextMenu,
) -> tuple[int, float] | None:
    """The (rate, per) limit *command* runs under, if any."""
    return getattr(
        command.callback,
        cooldownAttr,
        getattr(command, cooldownAttr, None),
    )


def hasPermissions(*, guildOnly: bool = False, **perms: bool):
    """Require the bot to hold *perms* where the command was run.

    The permissions are also stashed on the callback so `debug perms` can
    list what the loaded commands actually need.
    """
    invalid = perms.keys() - discord.Permissions.VALID_FLAGS.keys()
    if invalid:
        raise TypeError(
            f"Invalid permission(s): {', '.join(sorted(invalid))}"
        )

    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            if guildOnly:
                raise app_commands.NoPrivateMessage(
                    "This command can only be used in a server."
                )
            return True

        permissions = interaction.app_permissions
        missing = [
            perm
            for perm, value in perms.items()
            if getattr(permissions, perm) != value
        ]
        if missing:
            raise app_commands.BotMissingPermissions(missing)
        return True

    check = app_commands.check(predicate)

    def decorator(func):
        target = getattr(func, "callback", func)
        setattr(
            target, permsAttr, {**getattr(target, permsAttr, {}), **perms}
        )
        return check(func)

    return decorator


def requiredPermissions(command: app_commands.Command) -> dict[str, bool]:
    """The bot permissions *command* was decorated with.

    Used by `debug perms`.
    """
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
            f"I am missing {formatPermissions(error.missing_permissions)} "
            "to run"
            f" this command.{errors.note(logged)}",
        )
        return

    if isinstance(error, app_commands.MissingPermissions):
        await respond(
            interaction,
            (
                "You are missing "
                f"{formatPermissions(error.missing_permissions)} to run "
                "this command."
            ),
        )
        return

    if isinstance(error, app_commands.NoPrivateMessage):
        await respond(
            interaction, "This command can only be used in a server."
        )
        return

    if isinstance(error, app_commands.CommandOnCooldown):
        await respond(
            interaction,
            f"Slow down. Try again in {math.ceil(error.retry_after)}s.",
        )
        return

    if isinstance(error, mood.SassyDenial):
        return

    if isinstance(error, app_commands.CheckFailure):
        await respond(
            interaction,
            "You do not have permission to execute this command",
        )
        return

    cause: Exception = error
    if isinstance(error, app_commands.CommandInvokeError):
        cause = error.original

    logged = errors.fromInteraction(interaction, cause)
    print(
        cf.red(
            f"[error] unhandled error in {interaction.command}: {cause!r}"
        )
    )
    await respond(
        interaction,
        f"Something went wrong running `{interaction.command}`:"
        f" {cause}{errors.note(logged)}",
    )
