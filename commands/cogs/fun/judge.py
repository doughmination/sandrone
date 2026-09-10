import discord
from discord import app_commands
from discord.ext import commands

from sandrone import mood
from utils import components


class Judge(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="judge",
        description="Get Sandrone's Judgement on a user",
        ignore_extra=False,
    )
    @app_commands.describe(user="The user to judge")
    @mood.sassy
    async def judge(
        self, ctx: commands.Context, user: discord.User | None = None
    ) -> None:
        target = user or ctx.author
        verdict = mood.judge(target)
        view = components.panel(
            title="Sandrone's Assessment",
            body=f'Subject: {target.mention}\n\n"{verdict}"',
            thumbnail=target.display_avatar.url,
            footer="Sandrone",
        )
        await ctx.send(view=view, allowed_mentions=discord.AllowedMentions.none())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Judge(bot))
