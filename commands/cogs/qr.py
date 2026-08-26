import io

import discord
import qrcode
from discord import app_commands
from discord.ext import commands

from bot import doughchecks


class Qr(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="qr", description="Generate a QR Code")
    @app_commands.describe(text="The text or URI to generate")
    @doughchecks.has_permissions(attach_files=True)
    async def qrSlash(self, interaction: discord.Interaction, text: str) -> None:
        await interaction.response.defer()
        reply = await self.getQr(text)
        await interaction.followup.send(file=reply)

    async def getQr(self, text: str) -> discord.File:
        qr = qrcode.make(text)
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        buffer.seek(0)
        qrFile = discord.File(buffer, filename="qr.png")
        return qrFile


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Qr(bot))
