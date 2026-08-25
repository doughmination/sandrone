import discord
from discord import app_commands
from discord.ext import commands

from bot import doughchecks


class Invite(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="invite", description="All invite links")
    @doughchecks.has_permissions(embed_links=True)
    async def inviteSlash(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        invite = await self.buildInviteEmbed()
        await interaction.followup.send(embed=invite)

    async def buildInviteEmbed(self) -> discord.Embed:
        user = self.bot.user
        if user is None:  # only possible before login
            raise RuntimeError("Bot is not logged in yet")

        embed = discord.Embed(color=discord.Color.fuchsia(), title="Invite Links:")
        if user.avatar is not None:
            embed.set_thumbnail(url=user.avatar.url)
        embed.add_field(
            name=" ",
            value=f"[Invite Link](https://discord.com/oauth2/authorize?client_id={user.id})",
        )
        embed.add_field(
            name=" ", value="[Discord Server](https://discord.gg/N8gCjS294R)"
        )
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Invite(bot))
