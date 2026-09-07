import discord
from discord import app_commands
from discord.ext import commands

from sandrone import config, doughchecks
from utils import components


class Invite(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="links", description="All related links")
    @doughchecks.has_permissions(embed_links=True)
    async def inviteSlash(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await interaction.followup.send(view=await self.buildInvitePanel())

    async def buildInvitePanel(self) -> components.Panel:
        links = (
            "[Invite Link](https://invite.sandrone.is-a.bot)\n"
            "[Discord Server](https://support.sandrone.is-a.bot)\n"
            "[Website](https://sandrone.is-a.bot)\n"
            "[Source Code](https://github.com/doughmination/sandrone)"
        )
        return components.panel(
            title="Invite Links",
            body=links,
            footer=f"Sandrone v{config.version}",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Invite(bot))
