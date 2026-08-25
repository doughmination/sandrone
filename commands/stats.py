import datetime
from pathlib import Path
import toml

import discord
from discord import app_commands
from discord.ext import commands

from bot import doughchecks

version = "unknown"
# adopt path to your pyproject.toml
pyproject_toml_file = Path(__file__).parent / ".." / "pyproject.toml"
if pyproject_toml_file.exists() and pyproject_toml_file.is_file():
    data = toml.load(pyproject_toml_file)
    # check project.version
    if "project" in data and "version" in data["project"]:
        version = data["project"]["version"]


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.launch_time = datetime.datetime.now(datetime.UTC)

    @app_commands.command(name="stats", description="Show the bot's ping and uptime")
    @doughchecks.has_permissions(embed_links=True)
    async def stats(self, interaction: discord.Interaction) -> None:
        delta_uptime = datetime.datetime.now(datetime.UTC) - self.launch_time
        hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        latency = round(self.bot.latency * 1000)

        embed = discord.Embed(title=f"{self.bot.user.name}'s stats", color=discord.Color.fuchsia())
        embed.add_field(name="Ping:", value=f"{latency}ms")
        embed.add_field(name="Uptime:", value=f"{days}d, {hours}h, {minutes}m, {seconds}s")
        embed.add_field(name="Region:", value="London, UK")
        embed.add_field(name="Version:", value=version)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Stats(bot))
