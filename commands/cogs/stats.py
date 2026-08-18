import datetime

import discord
from discord import app_commands
from discord.ext import commands


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.launch_time = datetime.datetime.now(datetime.UTC)

    @app_commands.command(name="stats", description="Show the bot's ping and uptime")
    @app_commands.guild_only()
    async def stats(self, interaction: discord.Interaction) -> None:
        delta_uptime = datetime.datetime.now(datetime.UTC) - self.launch_time
        hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        latency = round(self.bot.latency * 1000)

        if not interaction.user.guild_permissions.administrator:  # this just makes sure the user is an admin
            await interaction.response.send_message(
                "You do not have permission to execute this command", ephemeral=True
            )
            return

        embed = discord.Embed(title=f"{self.bot.user.name}'s stats", color=discord.Color.blurple())
        embed.add_field(name="Ping:", value=f"{latency}ms")
        embed.add_field(name="Uptime:", value=f"{days}d, {hours}h, {minutes}m, {seconds}s")
        embed.add_field(name="Region", value="Manchester, UK")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Stats(bot))
