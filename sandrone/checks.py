import discord
from discord import app_commands
from discord.ext import commands

from sandrone import mood
from utils import cf, usage


def has_permissions(*, guildOnly: bool = False, **perms: bool):
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
    def decorator(func):
        func.__discord_app_commands_is_nsfw__ = True
        return commands.is_nsfw()(func)

    return decorator


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
        await respond(
            interaction,
            f"I am missing {formatPermissions(error.missing_permissions)} to run this command.",
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

    if isinstance(error, mood.SassyDenial):
        return

    if isinstance(error, app_commands.CheckFailure):
        await respond(interaction, "You do not have permission to execute this command")
        return

    print(cf.red(f"[error] unhandled error in {interaction.command}: {error}"))
    await respond(
        interaction, f"Something went wrong running `{interaction.command}`: {error}"
    )


async def handleCommandError(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, mood.SassyDenial):
        return

    if isinstance(error, commands.HybridCommandError):
        error = error.original  # type: ignore[assignment]

    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(
            f"Slow down. Try again in {error.retry_after:.0f}s.", ephemeral=True
        )
        return

    if isinstance(error, commands.BotMissingPermissions):
        await ctx.send(
            f"I am missing {formatPermissions(error.missing_permissions)} to run this command.",
            ephemeral=True,
        )
        return

    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            f"You are missing {formatPermissions(error.missing_permissions)} to run this command.",
            ephemeral=True,
        )
        return

    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command can only be used in a server.", ephemeral=True)
        return

    if isinstance(error, commands.NSFWChannelRequired):
        await ctx.send(
            "That one only works in an age-restricted channel.", ephemeral=True
        )
        return

    if (
        isinstance(error, (commands.UserInputError, app_commands.TransformerError))
        and ctx.command is not None
    ):
        await ctx.send(view=usage.usagePanel(ctx, error), ephemeral=True)
        return

    if isinstance(error, commands.CheckFailure):
        await ctx.send(
            "You do not have permission to execute this command", ephemeral=True
        )
        return

    if isinstance(error, commands.CommandInvokeError):
        error = error.original  # type: ignore[assignment]

    print(cf.red(f"[error] unhandled error in {ctx.command}: {error!r}"))
    await ctx.send(f"Something went wrong running `{ctx.command}`: {error}")
