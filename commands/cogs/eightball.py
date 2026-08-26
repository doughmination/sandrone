import random

import discord
from discord import app_commands
from discord.ext import commands

from bot import doughchecks

responses = [
    "Hmph. Fine, yes. Not that I did the math for your sake or anything.",
    "Obviously yes. Did you really need to ask?",
    "I-it's a yes, okay?! Don't look at me like that.",
    "Yes. And before you get any ideas, I only answered because I felt like it.",
    "Ugh, fine — yes. Happy now?",
    "It's a yes. Not that I care what happens either way.",
    "No. And don't ask again, it's embarrassing for both of us.",
    "Hmph, no. Obviously. Were you even thinking?",
    "No way. I-it's not like I'd tell you even if it were a maybe.",
    "That's a no. Don't cry about it.",
    "No. Absolutely not. ...Was that too harsh? Whatever, it's still no.",
    "Ooo, what's inside that question... not that I care. Ask again later.",
    "I-I don't know, okay?! It's not like I have every answer memorized!",
    "Unclear. Stop making me think so hard about your problems.",
    "Ask me later. I'm busy. ...Doing nothing in particular. Shut up.",
    "That's for me to know and you to figure out yourself, dummy.",
    "Hah?! How should I know that? Figure it out on your own for once.",
]


class EightBall(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="8ball", description="Ask Sandrone a question. Don't expect her to be nice about it."
    )
    @app_commands.describe(question="The question you want answered")
    @doughchecks.has_permissions(embed_links=True)
    async def eightballSlash(
        self, interaction: discord.Interaction, question: str
    ) -> None:
        embed = discord.Embed(color=discord.Color.fuchsia())
        embed.add_field(name="You asked", value=question, inline=False)
        embed.add_field(name="Sandrone says", value=random.choice(responses), inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EightBall(bot))
