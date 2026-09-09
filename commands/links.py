import discord
from discord import app_commands
from discord.ext import commands

from sandrone import config, mood
from utils import components


class Invite(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="links", description="All related links")
    @mood.sassy
    async def inviteSlash(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await interaction.followup.send(view=await self.buildInvitePanel())

    async def buildInvitePanel(self) -> components.Panel:
        return components.panel(
            title="Sandrone links",
            body="Add the bot, join the support server, or dig into the source.",
            buttons=[
                components.linkButton(
                    "Invite", "https://invite.sandrone.is-a.bot", emoji="➕"
                ),
                components.linkButton(
                    "Support server", "https://support.sandrone.is-a.bot", emoji="💬"
                ),
                components.linkButton(
                    "Website", "https://sandrone.is-a.bot", emoji="🌐"
                ),
                components.linkButton(
                    "Source", "https://github.com/doughmination/sandrone", emoji="🧑‍💻"
                ),
            ],
            footer=f"Sandrone v{config.version}",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Invite(bot))
