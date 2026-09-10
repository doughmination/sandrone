from discord.ext import commands

from sandrone import config, mood
from utils import components


class Invite(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="links",
        description="All related links",
        aliases=["invite", "support"],
    )
    @mood.sassy
    async def links(self, ctx: commands.Context) -> None:
        await ctx.defer()
        await ctx.send(view=await self.buildInvitePanel())

    async def buildInvitePanel(self) -> components.Panel:
        return components.panel(
            title="Sandrone links",
            body="Add the bot, join the support server, or dig into the source.",
            buttons=[
                components.linkButton(
                    "Invite", "https://sandrone.doughmination.gay/invite", emoji="➕"
                ),
                components.linkButton(
                    "Support server", "https://sandrone.doughmination.gay/support", emoji="💬"
                ),
                components.linkButton(
                    "Website", "https://sandrone.doughmination.gay", emoji="🌐"
                ),
                components.linkButton(
                    "Source", "https://github.com/doughmination/sandrone", emoji="🧑‍💻"
                ),
            ],
            footer=f"Sandrone v{config.version}",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Invite(bot))
