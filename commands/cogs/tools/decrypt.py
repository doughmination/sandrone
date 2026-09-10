import base64
import codecs
from typing import Literal

from discord import app_commands
from discord.ext import commands

from sandrone import mood

decoderSystem = {
    "Base64": "b64",
    "Base32": "b32",
    "Rot13": "rot13",
    "Caesar Cipher": "caesar",
}

# See encrypt.py — Literal so the prefix parser can backtrack past a missing method.
DecoderMethod = Literal[*tuple(decoderSystem.values())]


class Decrypt(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="decrypt",
        description="Decode or decrypt some text using a chosen method",
        aliases=["decode", "dec"],
    )
    @app_commands.describe(input="What do you want to decrypt?")
    @app_commands.describe(method="The decoding/decryption algorithm")
    @app_commands.choices(
        method=[
            app_commands.Choice(name=name, value=value)
            for name, value in decoderSystem.items()
        ]
    )
    @mood.sassy
    async def decrypt(
        self,
        ctx: commands.Context,
        method: DecoderMethod | None = None,
        *,
        input: str,
    ) -> None:
        await ctx.defer(ephemeral=True)
        reply = await self.decodeMessage(input, method or "b64")
        await ctx.send(reply, ephemeral=True)

    async def decodeMessage(self, input: str, method: str) -> str:
        try:
            if method == "b64":
                input_bytes = input.encode("utf-8")
                decoded_bytes = base64.b64decode(input_bytes)
                return decoded_bytes.decode("utf-8")

            elif method == "b32":
                input_bytes = input.encode("utf-8")
                decoded_bytes = base64.b32decode(input_bytes)
                return decoded_bytes.decode("utf-8")

            elif method == "rot13":
                return codecs.encode(input, "rot_13")

            elif method == "caesar":
                shifted = []
                for char in input:
                    if char.isalpha():
                        stay_in_alphabet = ord("a") if char.islower() else ord("A")
                        shifted.append(
                            chr(
                                (ord(char) - stay_in_alphabet - 3) % 26
                                + stay_in_alphabet
                            )
                        )
                    else:
                        shifted.append(char)
                return "".join(shifted)

            else:
                return "❌ Unknown decryption method requested."

        except ValueError:
            return "❌ **Error:** Could not decode that text. Make sure you selected the right method for that specific scrambled text!"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Decrypt(bot))
