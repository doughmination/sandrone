import discord
from discord import app_commands
from discord.ext import commands

from sandrone import mood
from utils import components


class Judge(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="judge", description="Get Sandrone's Judgement on a user"
    )
    @app_commands.describe(user="The user to judge")
    @mood.sassy
    async def judgeSlash(
        self, interaction: discord.Interaction, user: discord.User | None = None
    ) -> None:
        target = user or interaction.user
        verdict = mood.judge(interaction, target)
        view = components.panel(
            title="Sandrone's Assessment",
            body=f'Subject: {target.mention}\n\n"{verdict}"',
            thumbnail=target.display_avatar.url,
            footer="Sandrone",
        )
        await interaction.response.send_message(
            view=view, allowed_mentions=discord.AllowedMentions.none()
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Judge(bot))
