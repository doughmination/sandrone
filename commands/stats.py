import datetime

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from sandrone import config
from utils import components


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.launch_time = datetime.datetime.now(datetime.UTC)
        self.session = aiohttp.ClientSession()
        self.region: str | None = None

    async def cog_unload(self) -> None:
        await self.session.close()

    async def getRegion(self) -> str:
        if self.region is not None:
            return self.region

        params = {"fields": "status,city,regionName,country"}
        try:
            async with self.session.get(
                "http://ip-api.com/json",
                params=params,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                data = await resp.json()
        except (aiohttp.ClientError, TimeoutError):
            return "Unknown"

        if data.get("status") != "success":
            return "Unknown"

        parts = [data.get("city"), data.get("regionName"), data.get("country")]
        self.region = ", ".join(part for part in parts if part) or "Unknown"
        return self.region

    @app_commands.command(name="stats", description="Show the bot's ping and uptime")
    async def stats(self, interaction: discord.Interaction) -> None:
        user = self.bot.user
        await interaction.response.defer()

        delta_uptime = datetime.datetime.now(datetime.UTC) - self.launch_time
        hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        latency = round(self.bot.latency * 1000)
        botName = user.name if user else "Bot"

        view = components.panel(
            title=f"{botName}'s stats",
            fields=[
                ("Ping", f"{latency}ms"),
                ("Uptime", f"{days}d, {hours}h, {minutes}m, {seconds}s"),
                ("Version", config.version),
                ("Region", await self.getRegion()),
            ],
            footer="Sandrone",
        )
        await interaction.followup.send(view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Stats(bot))
