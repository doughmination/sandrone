import discord
from discord import app_commands
from discord.ext import commands

from commands.settings.mods import isManager
from utils import components, jp_storage

db = jp_storage.database("incidents", version=1)

ignoredKey = "channels_ignored"

type IncidentChannel = discord.TextChannel | discord.Thread


def ignoredChannels(guildId: int) -> list[int]:
    return db.guild(guildId).key(ignoredKey).ids()


def isIgnored(guildId: int, *channelIds: int | None) -> bool:
    ignored = set(ignoredChannels(guildId))
    return any(channelId in ignored for channelId in channelIds if channelId is not None)


def setIgnored(guildId: int, channelId: int, ignored: bool) -> bool:
    field = db.guild(guildId).key(ignoredKey)
    if ignored == field.has(channelId):
        return False

    if ignored:
        field.add(channelId).save()
    else:
        field.remove(channelId).save()
    return True


def resolveChannel(
    interaction: discord.Interaction, channel: IncidentChannel | None
) -> IncidentChannel | None:
    if channel is not None:
        return channel
    if isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
        return interaction.channel
    return None


class IncidentSettings(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    incidents = app_commands.Group(
        name="incidents",
        description="Choose where puppet incidents are allowed to happen",
        guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @incidents.command(
        name="ignore",
        description="Stop incidents from happening in a channel",
    )
    @app_commands.describe(channel="Channel to ignore. Defaults to this one.")
    @app_commands.guild_only()
    @isManager()
    async def ignore(
        self, interaction: discord.Interaction, channel: IncidentChannel | None = None
    ) -> None:
        target = resolveChannel(interaction, channel)
        if target is None:
            await interaction.response.send_message(
                view=components.error("Pick a text channel or thread."), ephemeral=True
            )
            return

        changed = setIgnored(interaction.guild.id, target.id, True)
        body = (
            f"Incidents will skip {target.mention}."
            if changed
            else f"{target.mention} was already ignored."
        )
        await interaction.response.send_message(view=components.panel(body=body), ephemeral=True)

    @incidents.command(
        name="unignore",
        description="Allow incidents in a channel again",
    )
    @app_commands.describe(channel="Channel to allow. Defaults to this one.")
    @app_commands.guild_only()
    @isManager()
    async def unignore(
        self, interaction: discord.Interaction, channel: IncidentChannel | None = None
    ) -> None:
        target = resolveChannel(interaction, channel)
        if target is None:
            await interaction.response.send_message(
                view=components.error("Pick a text channel or thread."), ephemeral=True
            )
            return

        changed = setIgnored(interaction.guild.id, target.id, False)
        body = (
            f"Incidents can happen in {target.mention} again."
            if changed
            else f"{target.mention} was not ignored."
        )
        await interaction.response.send_message(view=components.panel(body=body), ephemeral=True)

    @incidents.command(
        name="list",
        description="Show which channels incidents will skip",
    )
    @app_commands.guild_only()
    @isManager()
    async def listIgnored(self, interaction: discord.Interaction) -> None:
        channelIds = ignoredChannels(interaction.guild.id)
        if not channelIds:
            await interaction.response.send_message(
                view=components.panel(
                    title="Incident settings",
                    body="Nothing is ignored — incidents can happen anywhere I can speak.",
                    footer="Use `incidents ignore` to exclude a channel.",
                ),
                ephemeral=True,
            )
            return

        lines = []
        for channelId in channelIds:
            channel = interaction.guild.get_channel_or_thread(channelId)
            lines.append(channel.mention if channel else f"`{channelId}` (gone)")

        await interaction.response.send_message(
            view=components.panel(
                title="Incident settings",
                body="Incidents will skip:\n" + "\n".join(f"- {line}" for line in lines),
                footer=f"{len(channelIds)} ignored · `incidents unignore` to undo",
            ),
            ephemeral=True,
        )

    @incidents.command(
        name="reset",
        description="Clear the ignore list for this server",
    )
    @app_commands.guild_only()
    @isManager()
    async def reset(self, interaction: discord.Interaction) -> None:
        if not ignoredChannels(interaction.guild.id):
            await interaction.response.send_message(
                view=components.panel(body="Nothing to clear."), ephemeral=True
            )
            return

        db.guild(interaction.guild.id).key(ignoredKey).delete().save()
        await interaction.response.send_message(
            view=components.panel(body="Ignore list cleared."), ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(IncidentSettings(bot))
