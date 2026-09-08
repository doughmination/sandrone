import random

import discord
from discord import app_commands

from utils import components

DENIED = discord.Color.gold()

sassy_replies = [
    "Sandrone has determined that this command is beneath her.",
    "Sandrone is tired of your command usage. Ask again nicely and she might do it.",
    "No.",
    "Absolutely not.",
    "Sandrone has decided that you have used enough commands today.",
    "The puppet has reviewed your request. It has declined.",
    "Your command has been rejected on the grounds that Sandrone doesn't feel like it.",
]


class SassyDenial(app_commands.CheckFailure):
    """Raised when Sandrone sassily denies a command.

    Distinguishing this from a generic CheckFailure lets the global
    error handler know Sandrone has already sent her own rejection
    message, so it doesn't need to send a second "no permission"
    message on top of it.
    """
    pass


async def sassy(interaction: discord.Interaction) -> bool:
    if random.randint(1, 10) != 1:
        return True

    await interaction.response.send_message(
        view=components.panel(
            body=(
                "<:sandrone_refuses:1546669792595939468> "
                f"{random.choice(sassy_replies)}"
            ),
            color=DENIED,
        )
    )

    raise SassyDenial()


sassy = app_commands.check(sassy)