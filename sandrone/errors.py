import discord
from discord import app_commands

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
    if isinstance(error, app_commands.MissingPermissions):
        await respond(
            interaction,
            f"You are missing {formatPermissions(error.missing_permissions)} to run this command.",
        )
        return

    if isinstance(error, app_commands.NoPrivateMessage):
        await respond(interaction, "This command can only be used in a server.")
        return

    if isinstance(error, app_commands.CheckFailure):
        await respond(interaction, "You do not have permission to execute this command")
        return

    print(cf.red(f"[error] unhandled error in {interaction.command}: {error}"))
    await respond(
        interaction, f"Something went wrong running `{interaction.command}`: {error}"
    )
