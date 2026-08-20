import io

import discord
from discord import app_commands
from discord.ext import commands
import qrcode

class Qr(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="qr", description="Generate a QR Code")
    @app_commands.describe(text="The text or URI to generate")
    async def qrSlash(self, interaction: discord.Interaction, text: str) -> None:
        await interaction.response.defer()
        reply = await self.getQr(text)
        await interaction.followup.send(file=reply)

    async def getQr(self, text: str) -> None:
        qr = qrcode.make(text)
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        buffer.seek(0)
        qrFile = discord.File(buffer, filename="qr.png")
        return qrFile


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Qr(bot))