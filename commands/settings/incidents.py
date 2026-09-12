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
    ctx: commands.Context, channel: IncidentChannel | None
) -> IncidentChannel | None:
    if channel is not None:
        return channel
    if isinstance(ctx.channel, (discord.TextChannel, discord.Thread)):
        return ctx.channel
    return None


class IncidentSettings(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_group(
        name="incidents",
        description="Choose where puppet incidents are allowed to happen",
        invoke_without_command=True,
    )
    @commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @isManager()
    async def incidents(self, ctx: commands.Context) -> None:
        await self.listIgnored(ctx)

    @incidents.command(
        name="ignore",
        description="Stop incidents from happening in a channel",
    )
    @app_commands.describe(channel="Channel to ignore. Defaults to this one.")
    @commands.guild_only()
    @isManager()
    async def ignore(
        self, ctx: commands.Context, channel: IncidentChannel | None = None
    ) -> None:
        target = resolveChannel(ctx, channel)
        if target is None:
            await ctx.send(
                view=components.error("Pick a text channel or thread."), ephemeral=True
            )
            return

        changed = setIgnored(ctx.guild.id, target.id, True)
        body = (
            f"Incidents will skip {target.mention}."
            if changed
            else f"{target.mention} was already ignored."
        )
        await ctx.send(view=components.panel(body=body), ephemeral=True)

    @incidents.command(
        name="unignore",
        description="Allow incidents in a channel again",
    )
    @app_commands.describe(channel="Channel to allow. Defaults to this one.")
    @commands.guild_only()
    @isManager()
    async def unignore(
        self, ctx: commands.Context, channel: IncidentChannel | None = None
    ) -> None:
        target = resolveChannel(ctx, channel)
        if target is None:
            await ctx.send(
                view=components.error("Pick a text channel or thread."), ephemeral=True
            )
            return

        changed = setIgnored(ctx.guild.id, target.id, False)
        body = (
            f"Incidents can happen in {target.mention} again."
            if changed
            else f"{target.mention} was not ignored."
        )
        await ctx.send(view=components.panel(body=body), ephemeral=True)

    @incidents.command(
        name="list",
        description="Show which channels incidents will skip",
    )
    @commands.guild_only()
    @isManager()
    async def listIgnored(self, ctx: commands.Context) -> None:
        channelIds = ignoredChannels(ctx.guild.id)
        if not channelIds:
            await ctx.send(
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
            channel = ctx.guild.get_channel_or_thread(channelId)
            lines.append(channel.mention if channel else f"`{channelId}` (gone)")

        await ctx.send(
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
    @commands.guild_only()
    @isManager()
    async def reset(self, ctx: commands.Context) -> None:
        if not ignoredChannels(ctx.guild.id):
            await ctx.send(
                view=components.panel(body="Nothing to clear."), ephemeral=True
            )
            return

        db.guild(ctx.guild.id).key(ignoredKey).delete().save()
        await ctx.send(
            view=components.panel(body="Ignore list cleared."), ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(IncidentSettings(bot))
