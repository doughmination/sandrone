import base64
import codecs
from typing import Literal

from discord import app_commands
from discord.ext import commands

from sandrone import mood

encoderSystem = {
    "Base64": "b64",
    "Base32": "b32",
    "Rot13": "rot13",
    "Caesar Cipher": "caesar",
}

# A Literal (rather than app_commands.Choice) so the prefix parser can try the
# first word against it and fall back to the default when it doesn't match —
# @app_commands.choices below still supplies the pretty slash-menu labels.
EncoderMethod = Literal[*tuple(encoderSystem.values())]


class Encrypt(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="encrypt",
        description="Encode some text using a chosen method",
        aliases=["encode", "enc"],
    )
    @app_commands.describe(input="What do you want to encrypt?")
    @app_commands.describe(method="The encoding/encryption algorithm")
    @app_commands.choices(
        method=[
            app_commands.Choice(name=name, value=value)
            for name, value in encoderSystem.items()
        ]
    )
    @mood.sassy
    async def encrypt(
        self,
        ctx: commands.Context,
        method: EncoderMethod | None = None,
        *,
        input: str,
    ) -> None:
        await ctx.defer(ephemeral=True)

        reply = await self.encodeMessage(input, method or "b64")
        await ctx.send(reply, ephemeral=True)

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
            return codecs.encode(input, "rot_13")

        elif method == "caesar":
            shifted = []
            for char in input:
                if char.isalpha():
                    stay_in_alphabet = ord("a") if char.islower() else ord("A")
                    shifted.append(
                        chr((ord(char) - stay_in_alphabet + 3) % 26 + stay_in_alphabet)
                    )
                else:
                    shifted.append(char)
            return "".join(shifted)

        else:
            return "❌ Unknown encryption method requested."


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Encrypt(bot))
