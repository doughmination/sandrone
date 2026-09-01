import discord
from discord import app_commands
from discord.ext import commands

from sandrone import doughchecks

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
    @doughchecks.has_permissions(embed_links=True)
    async def pfpSlash(
        self,
        interaction: discord.Interaction,
        user: discord.Member | discord.User | None = None,
        server: app_commands.Choice[str] | None = None,
    ) -> None:
        await interaction.response.defer()
        target = user or interaction.user
        scope = server.value if server else "global"
        embed = await self.getPfpEmbed(target, scope)
        await interaction.followup.send(embed=embed)

    async def getPfpEmbed(
        self, user: discord.Member | discord.User, scope: str
    ) -> discord.Embed:
        if scope == "guild":
            avatar = getattr(user, "guild_avatar", None) or self.globalAvatar(user)
            title = f"{user.name}'s Server pfp"
        else:
            avatar = self.globalAvatar(user)
            title = f"{user.name}'s Global pfp"

        embed = discord.Embed(color=discord.Color.fuchsia(), title=title)
        embed.set_image(url=avatar.url)

        botUser = self.bot.user
        embed.set_footer(
            text="Sandrone",
            icon_url=botUser.avatar.url if botUser and botUser.avatar else None,
        )
        return embed

    def globalAvatar(self, user: discord.Member | discord.User) -> discord.Asset:
        return user.avatar or user.default_avatar


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Pfp(bot))
