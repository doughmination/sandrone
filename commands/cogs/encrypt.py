import base64
import codecs

import discord
from discord import app_commands
from discord.ext import commands

# 1. Expanded the options dictionary
encoderSystem = {
    "Base64": "b64",
    "Base32": "b32",
    "Rot13": "rot13",
    "Caesar Cipher": "caesar"
}

class Encrypt(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
    
    @app_commands.command(
        name="encrypt",
        description="Encode some text using a chosen method"
    )
    @app_commands.describe(input="What do you want to encrypt?")
    @app_commands.describe(method="The encoding/encryption algorithm")
    @app_commands.choices(method=[
        app_commands.Choice(name=name, value=value) for name, value in encoderSystem.items()
    ])
    async def encryptSlash(self, interaction: discord.Interaction, input: str, method: app_commands.Choice[str] = None) -> None:
        await interaction.response.defer(ephemeral=True)
        
        chosen_value = method.value if method else "b64"
        
        reply = await self.encodeMessage(input, chosen_value)
        await interaction.followup.send(reply, ephemeral=True)

    async def encodeMessage(self, input: str, method: str) -> str:
        if method == "b64":
            input_bytes = input.encode("utf-8")
            encoded_bytes = base64.b64encode(input_bytes)
            return encoded_bytes.decode("utf-8")
            
        elif method == "b32":
            input_bytes = input.encode("utf-8")
            encoded_bytes = base64.b32encode(input_bytes)
            return encoded_bytes.decode("utf-8")
            
        elif method == "rot13":
            return codecs.encode(input, 'rot_13')
            
        elif method == "caesar":
            shifted = []
            for char in input:
                if char.isalpha():
                    stay_in_alphabet = ord('a') if char.islower() else ord('A')
                    shifted.append(chr((ord(char) - stay_in_alphabet + 3) % 26 + stay_in_alphabet))
                else:
                    shifted.append(char)
            return "".join(shifted)
            
        else:
            return "Unknown method requested."

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Encrypt(bot))
