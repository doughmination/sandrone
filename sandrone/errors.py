import discord
from discord import app_commands
from discord.ext import commands

from sandrone import mood
from utils.colors import cf


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
    """Fallback for app commands that never reach ``on_command_error``.

    Hybrid commands funnel their errors — slash and prefix alike — through
    :func:`handleCommandError`, so this now only catches the leftovers
    (signature mismatches, context menus, anything not wrapped as a hybrid).
    """
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
        return  # We don't do anything as the mood.py file handles the output from this error!

    if isinstance(error, app_commands.CheckFailure):
        await respond(interaction, "You do not have permission to execute this command")
        return

    print(cf.red(f"[error] unhandled error in {interaction.command}: {error}"))
    await respond(
        interaction, f"Something went wrong running `{interaction.command}`: {error}"
    )


async def handleCommandError(ctx: commands.Context, error: commands.CommandError) -> None:
    """Primary handler — every hybrid invocation lands here, slash or prefix."""
    # Prefix typos shouldn't produce noise; there is no slash equivalent of
    # someone mistyping a word after her name.
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, mood.SassyDenial):
        return  # mood.py already sent the refusal.

    # HybridCommandError wraps an app-command-side failure; unwrap for a
    # readable message.
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

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"You need to give me `{error.param.name}`. "
            f"Try `{ctx.clean_prefix}{ctx.invoked_with} <{error.param.name}>`.",
            ephemeral=True,
        )
        return

    if isinstance(error, (commands.BadArgument, commands.BadLiteralArgument)):
        await ctx.send(f"That argument didn't work: {error}", ephemeral=True)
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
