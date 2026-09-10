from discord.ext import commands

from sandrone import mood
from utils import components


class Pi(commands.Cog):
    def __ini__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="pi", description="Get the first 100 digits of pi")
    @mood.sassy
    async def pi(self, ctx: commands.Context) -> None:
        await ctx.defer()
        embed = components.panel(body="3.1415926535 8979323846 2643383279 5028841971 6939937510 5820974944 5923078164 0628620899 8628034825 3421170679")
        await ctx.send(view=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog((Pi(bot)))