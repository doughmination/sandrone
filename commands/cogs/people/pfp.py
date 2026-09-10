import discord
from discord import app_commands
from discord.ext import commands

from sandrone import mood
from utils import components


class Pfp(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="pfp",
        description="Get a user's Profile Image",
        aliases=["avatar", "av"],
        ignore_extra=False,
    )
    @app_commands.describe(user="The user you want to check (defaults to you)")
    @mood.sassy
    async def pfp(
        self,
        ctx: commands.Context,
        user: discord.Member | discord.User | None = None,
    ) -> None:
        await ctx.defer()
        target = user or ctx.author
        await ctx.send(view=self.getPfpPanel(target))

    def getPfpPanel(self, user: discord.Member | discord.User) -> components.Panel:
        globalAvatar = user.avatar or user.default_avatar
        guildAvatar = getattr(user, "guild_avatar", None)

        images = [components.image(globalAvatar.url, alt="Global avatar")]
        if guildAvatar is not None:
            images.insert(0, components.image(guildAvatar.url, alt="Server avatar"))

        title = f"{user.name}'s avatar" + ("s" if guildAvatar is not None else "")
        return components.panel(title=title, images=images, footer="Sandrone")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Pfp(bot))
