import discord
from discord import app_commands
from discord.ext import commands

from utils import components

scopes = {
    "Global": "global",
    "Server": "guild",
}


class Pfp(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="pfp", description="Get a user's Profile Image")
    @app_commands.describe(
        user="The user you want to check (defaults to you)",
        server="Global or server pfp (defaults to Global)",
    )
    @app_commands.choices(
        server=[
            app_commands.Choice(name=name, value=value)
            for name, value in scopes.items()
        ]
    )
    async def pfpSlash(
        self,
        interaction: discord.Interaction,
        user: discord.Member | discord.User | None = None,
        server: app_commands.Choice[str] | None = None,
    ) -> None:
        await interaction.response.defer()
        target = user or interaction.user
        scope = server.value if server else "global"
        await interaction.followup.send(view=await self.getPfpPanel(target, scope))

    async def getPfpPanel(
        self, user: discord.Member | discord.User, scope: str
    ) -> components.Panel:
        if scope == "guild":
            avatar = getattr(user, "guild_avatar", None) or self.globalAvatar(user)
            title = f"{user.name}'s Server pfp"
        else:
            avatar = self.globalAvatar(user)
            title = f"{user.name}'s Global pfp"

        return components.panel(title=title, images=[avatar.url], footer="Sandrone")

    def globalAvatar(self, user: discord.Member | discord.User) -> discord.Asset:
        return user.avatar or user.default_avatar


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Pfp(bot))
