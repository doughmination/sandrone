import base64
import codecs

from discord import app_commands
from discord.ext import commands

from sandrone import mood
from utils.choices import ChoiceSet

encoderSystem = {
    "Base64": "b64",
    "Base32": "b32",
    "Rot13": "rot13",
    "Caesar Cipher": "caesar",
}

# A converter (rather than app_commands.Choice) so the prefix parser can try
# the first word against it and fall back to the default when it doesn't match.
# It takes the menu labels as well as the values, and @app_commands.choices
# below keeps the slash menu itself label-and-value only.
encoders = ChoiceSet(encoderSystem)
EncoderMethod = encoders.converter


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
    @app_commands.choices(method=encoders.options)
    @mood.sassy
    async def encrypt(
        self,
        ctx: commands.Context,
        method: EncoderMethod | None = None,
        *,
        input: str,
    ) -> None:
        await ctx.defer(ephemeral=True)

        reply = await self.encodeMessage(input, encoders.resolve(method, "b64"))
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
