import discord
from discord import app_commands
from discord.ext import commands
from pluralkit import Client
from pluralkit.v2 import Member, NotFound, PluralKitException, System, Unauthorized

from sandrone import doughchecks

pk = Client()


class Pluralkit(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="pksystem", description="Get a pluralkit system")
    @app_commands.describe(user="The user to look up (defaults to you)")
    @doughchecks.has_permissions(embed_links=True)
    async def pkSystemSlash(
        self, interaction: discord.Interaction, user: discord.Member | None = None
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        target = user or interaction.user

        try:
            system = await pk.get_system(target.id)
        except NotFound:
            await interaction.followup.send(
                f"❌ {target.mention} doesn't have a registered PluralKit system.",
                ephemeral=True,
            )
            return
        except PluralKitException as error:
            embed = discord.Embed(
                color=discord.Color.red(),
                title="❌ Could not fetch system",
                description=str(error),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await interaction.followup.send(
            embed=self.buildSystemEmbed(system, target), ephemeral=True
        )

    @app_commands.command(
        name="pkfront", description="Get a pluralkit system's current front"
    )
    @app_commands.describe(user="The user to look up (defaults to you)")
    @doughchecks.has_permissions(embed_links=True)
    async def pkFrontSlash(
        self, interaction: discord.Interaction, user: discord.Member | None = None
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        target = user or interaction.user

        try:
            fronters = [member async for member in pk.get_fronters(target.id)]
        except NotFound:
            await interaction.followup.send(
                f"❌ {target.mention} doesn't have a registered PluralKit system.",
                ephemeral=True,
            )
            return
        except Unauthorized:
            await interaction.followup.send(
                f"❌ {target.mention}'s current front is private.",
                ephemeral=True,
            )
            return
        except PluralKitException as error:
            embed = discord.Embed(
                color=discord.Color.red(),
                title="❌ Could not fetch front",
                description=str(error),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await interaction.followup.send(
            embed=self.buildFrontEmbed(fronters, target), ephemeral=True
        )

    def buildSystemEmbed(self, system: System, user: discord.Member) -> discord.Embed:
        color = (
            discord.Color(int(str(system.color), 16))
            if system.color
            else discord.Color.fuchsia()
        )
        embed = discord.Embed(
            color=color,
            title=system.name or str(system.id),
            description=system.description,
        )
        embed.set_author(name=f"{user.display_name}'s System")

        if system.avatar_url:
            embed.set_thumbnail(url=system.avatar_url)
        if system.banner:
            embed.set_image(url=system.banner)

        embed.add_field(name="System ID", value=str(system.id), inline=True)
        if system.tag:
            embed.add_field(name="Tag", value=system.tag, inline=True)
        if system.pronouns:
            embed.add_field(name="Pronouns", value=system.pronouns, inline=True)

        embed.timestamp = system.created.datetime

        botUser = self.bot.user
        embed.set_footer(
            text="Sandrone",
            icon_url=botUser.avatar.url if botUser and botUser.avatar else None,
        )
        return embed

    def buildFrontEmbed(
        self, fronters: list[Member], user: discord.Member
    ) -> discord.Embed:
        embed = discord.Embed(color=discord.Color.fuchsia(), title="Currently fronting")
        embed.set_author(name=f"{user.display_name}'s System")

        if not fronters:
            embed.description = "No one is currently fronting."
        else:
            primary = fronters[0]
            if primary.color:
                embed.color = discord.Color(int(str(primary.color), 16))

            if primary.avatar_url:
                embed.set_thumbnail(url=primary.avatar_url)
            if primary.banner:
                embed.set_image(url=primary.banner)

            names = "\n".join(m.display_name or m.name for m in fronters)
            embed.add_field(
                name=f"Fronter{'s' if len(fronters) != 1 else ''} ({len(fronters)})",
                value=names,
                inline=False,
            )

            if primary.pronouns:
                embed.add_field(name="Pronouns", value=primary.pronouns, inline=True)

            embed.timestamp = discord.utils.utcnow()

        botUser = self.bot.user
        embed.set_footer(
            text="Sandrone",
            icon_url=botUser.avatar.url if botUser and botUser.avatar else None,
        )
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Pluralkit(bot))
