import discord
from discord import app_commands
from discord.ext import commands
from pluralkit import Client
from pluralkit.v2 import Member, NotFound, PluralKitException, System, Unauthorized

from utils import components

pk = Client()


class Pluralkit(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="pksystem", description="Get a pluralkit system")
    @app_commands.describe(user="The user to look up (defaults to you)")
    async def pkSystemSlash(
        self, interaction: discord.Interaction, user: discord.Member | None = None
    ) -> None:
        ephemeral = user is not None
        target = user or interaction.user

        await interaction.response.defer(ephemeral=ephemeral)

        try:
            system = await pk.get_system(target.id)
        except NotFound:
            await interaction.followup.send(
                f"❌ {target.mention} doesn't have a registered PluralKit system.",
                ephemeral=ephemeral,
            )
            return
        except PluralKitException as error:
            await interaction.followup.send(
                view=components.panel(
                    title="❌ Could not fetch system",
                    body=str(error),
                    color=components.RED,
                ),
                ephemeral=ephemeral,
            )
            return

        await interaction.followup.send(
            view=self.buildSystemPanel(system, target),
            ephemeral=ephemeral,
        )

    @app_commands.command(
        name="pkfront", description="Get a pluralkit system's current front"
    )
    @app_commands.describe(user="The user to look up (defaults to you)")
    async def pkFrontSlash(
        self, interaction: discord.Interaction, user: discord.Member | None = None
    ) -> None:
        ephemeral = user is not None
        target = user or interaction.user

        await interaction.response.defer(ephemeral=ephemeral)

        try:
            fronters = [member async for member in pk.get_fronters(target.id)]
        except NotFound:
            await interaction.followup.send(
                f"❌ {target.mention} doesn't have a registered PluralKit system.",
                ephemeral=ephemeral,
            )
            return
        except Unauthorized:
            await interaction.followup.send(
                f"❌ {target.mention}'s current front is private.",
                ephemeral=ephemeral,
            )
            return
        except PluralKitException as error:
            await interaction.followup.send(
                view=components.panel(
                    title="❌ Could not fetch front",
                    body=str(error),
                    color=components.RED,
                ),
                ephemeral=ephemeral,
            )
            return

        await interaction.followup.send(
            view=self.buildFrontPanel(fronters, target),
            ephemeral=ephemeral,
        )

    def buildSystemPanel(
        self, system: System, user: discord.Member | discord.User
    ) -> components.Panel:
        color = (
            discord.Color(int(str(system.color), 16))
            if system.color
            else components.FUCHSIA
        )
        lead = [f"-# {user.display_name}'s System", f"## {system.name or system.id}"]
        if system.description:
            lead.append(system.description)

        fields: list[components.Field] = [("System ID", str(system.id))]
        if system.tag:
            fields.append(("Tag", system.tag))
        if system.pronouns:
            fields.append(("Pronouns", system.pronouns))

        return components.panel(
            body="\n\n".join(lead),
            fields=fields,
            thumbnail=system.avatar_url or None,
            images=[system.banner] if system.banner else None,
            footer="Sandrone",
            color=color,
        )

    def buildFrontPanel(
        self, fronters: list[Member], user: discord.Member | discord.User
    ) -> components.Panel:
        lead = [f"-# {user.display_name}'s System", "## Currently fronting"]

        if not fronters:
            return components.panel(
                body="\n\n".join([*lead, "No one is currently fronting."]),
                footer="Sandrone",
            )

        primary = fronters[0]
        color = (
            discord.Color(int(str(primary.color), 16))
            if primary.color
            else components.FUCHSIA
        )
        names = "\n".join(m.display_name or m.name for m in fronters)
        fields: list[components.Field] = [
            (f"Fronter{'s' if len(fronters) != 1 else ''} ({len(fronters)})", names)
        ]
        if primary.pronouns:
            fields.append(("Pronouns", primary.pronouns))

        return components.panel(
            body="\n\n".join(lead),
            fields=fields,
            thumbnail=primary.avatar_url or None,
            images=[primary.banner] if primary.banner else None,
            footer="Sandrone",
            color=color,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Pluralkit(bot))
