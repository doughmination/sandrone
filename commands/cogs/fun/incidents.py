import random
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
from discord.utils import utcnow

from commands.admin import ownerOnly
from commands.settings.incidents import isIgnored
from sandrone import mood
from utils import cf, components

INCIDENT_COLOR = discord.Color.dark_teal()

CHECK_INTERVAL_MINUTES = 20
INCIDENT_CHANCE = 4
STALE_AFTER = timedelta(minutes=12)

type ActiveChannel = discord.TextChannel | discord.Thread


class Incidents(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.lastChannel: ActiveChannel | None = None
        self.lastActivity: datetime | None = None

    async def cog_load(self) -> None:
        self.incidentLoop.start()

    async def cog_unload(self) -> None:
        self.incidentLoop.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        if not isinstance(message.channel, (discord.TextChannel, discord.Thread)):
            return

        me = message.guild.me
        if me is None or not message.channel.permissions_for(me).send_messages:
            return

        channel = message.channel
        parentId = channel.parent_id if isinstance(channel, discord.Thread) else None
        if isIgnored(message.guild.id, channel.id, parentId):
            return

        self.lastChannel = message.channel
        self.lastActivity = utcnow()

    @tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
    async def incidentLoop(self) -> None:
        if random.randint(1, INCIDENT_CHANCE) == 1:
            await self.fireIncident()

    @incidentLoop.before_loop
    async def beforeIncidentLoop(self) -> None:
        await self.bot.wait_until_ready()

    @incidentLoop.error
    async def incidentLoopError(self, error: BaseException) -> None:
        print(cf.red(f"[incident] loop stopped on error: {error!r}"))

    async def fireIncident(self) -> bool:
        channel = self.lastChannel
        if channel is None or self.lastActivity is None:
            return False
        if utcnow() - self.lastActivity > STALE_AFTER:
            return False

        me = channel.guild.me
        if me is None or not channel.permissions_for(me).send_messages:
            return False

        parentId = channel.parent_id if isinstance(channel, discord.Thread) else None
        if isIgnored(channel.guild.id, channel.id, parentId):
            self.lastChannel = None
            self.lastActivity = None
            return False

        try:
            await channel.send(
                view=components.panel(
                    body=mood.randomIncident(),
                    color=INCIDENT_COLOR,
                )
            )
        except discord.HTTPException as e:
            print(cf.red(f"[incident] failed to send in {channel.id}: {e}"))
            return False

        print(cf.magenta(f"[incident] posted in #{channel} ({channel.guild})"))
        self.lastChannel = None
        self.lastActivity = None
        return True

    @commands.hybrid_command(
        name="incident",
        description="(owner) Force a puppet incident in the last active channel",
    )
    @ownerOnly()
    async def incident(self, ctx: commands.Context) -> None:
        fired = await self.fireIncident()
        message = (
            "Incident dispatched." if fired else "No suitable active channel right now."
        )
        await ctx.send(message, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Incidents(bot))
