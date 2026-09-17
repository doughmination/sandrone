import discord
from discord import app_commands
from discord.ext import commands
import psutil
from utils import components

class System(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="server", description="(owner-only) Get server status"
    )
    async def serverCommand(
        self, interaction: discord.Interaction
    ) -> None:
        await interaction.response.defer()
        panel = await self.getInfo()
        await interaction.followup.send(view=panel)

    async def getInfo(self) -> components.Panel:
        memory = psutil.virtual_memory()
        # CPU HERE
        psutil.disk_usage("/")

        info = components.panel(
            fields=[
                (
                    "Memory",
                    f"{memory.used}/{memory.available} ({memory.percent}%)"
                )
            ]
        )
        return info
