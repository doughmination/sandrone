import discord
from discord import app_commands
from discord.ext import commands

from sandrone import mood


class UserId(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="uid", description="Get a user's ID", aliases=["userid", "id"]
    )
    @app_commands.describe(user="The user to get the ID of (Default to you)")
    @mood.sassy
    async def uid(
        self, ctx: commands.Context, user: discord.User | None = None
    ) -> None:
        await ctx.defer()
        target = user or ctx.author
        await ctx.send(
            f"{target.mention}'s ID is `{target.id}`",
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UserId(bot))
