import discord
from discord import app_commands
from discord.ext import commands

from utils import components, jp_storage

db = jp_storage.database("mods", version=1)

usersKey = "users"
rolesKey = "roles"

type ModTarget = discord.Member | discord.Role


def modUsers(guildId: int) -> list[int]:
    return db.guild(guildId).key(usersKey).ids()


def modRoles(guildId: int) -> list[int]:
    return db.guild(guildId).key(rolesKey).ids()


def keyFor(target: ModTarget) -> str:
    return rolesKey if isinstance(target, discord.Role) else usersKey


def setMod(guildId: int, target: ModTarget, allowed: bool) -> bool:
    field = db.guild(guildId).key(keyFor(target))
    if allowed == field.has(target.id):
        return False

    if allowed:
        field.add(target.id).save()
    else:
        field.remove(target.id).save()
    return True


def hasServerPermissions(member: discord.Member) -> bool:
    permissions = member.guild_permissions
    return permissions.administrator or permissions.manage_guild


def isMod(member: discord.Member) -> bool:
    """Whether *member* may change this bot's settings in their guild.

    Manage Server and Administrator always pass, whatever the stored list says.
    Bot owners get nothing here: owner powers live in `ownerOnly()` and stop at
    the bot's own plumbing, so they cannot quietly override a server's choices.
    """
    if hasServerPermissions(member):
        return True

    guildId = member.guild.id
    if member.id in modUsers(guildId):
        return True

    roleIds = set(modRoles(guildId))
    return any(role.id in roleIds for role in member.roles)


def isManager():
    """Check for settings commands: a mod, or someone with Manage Server."""

    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.NoPrivateMessage(
                "This command can only be used in a server."
            )
        user = interaction.user
        if not isinstance(user, discord.Member) or not isMod(user):
            raise app_commands.MissingPermissions(["manage_guild"])
        return True

    return app_commands.check(predicate)


class Mods(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    mod = app_commands.Group(
        name="mod",
        description="Choose who may change my settings here",
        guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @mod.command(name="add", description="Let a user or role change my settings")
    @app_commands.describe(target="The user or role to allow.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add(self, interaction: discord.Interaction, target: ModTarget) -> None:
        if isinstance(target, discord.Member) and target.bot:
            await interaction.response.send_message(
                view=components.error("Bots cannot be moderators."), ephemeral=True
            )
            return

        changed = setMod(interaction.guild.id, target, True)
        body = (
            f"{target.mention} can now change my settings."
            if changed
            else f"{target.mention} already could."
        )
        await interaction.response.send_message(view=components.panel(body=body), ephemeral=True)

    @mod.command(name="remove", description="Revoke a user or role")
    @app_commands.describe(target="The user or role to revoke.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove(self, interaction: discord.Interaction, target: ModTarget) -> None:
        changed = setMod(interaction.guild.id, target, False)
        if changed:
            body = f"{target.mention} can no longer change my settings."
        elif isinstance(target, discord.Member) and hasServerPermissions(target):
            body = f"{target.mention} was not on the list — they have Manage Server."
        else:
            body = f"{target.mention} was not on the list."
        await interaction.response.send_message(view=components.panel(body=body), ephemeral=True)

    @mod.command(name="list", description="Show who may change my settings")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def listMods(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        users = modUsers(guild.id)
        roles = modRoles(guild.id)

        if not users and not roles:
            await interaction.response.send_message(
                view=components.panel(
                    title="Moderators",
                    body="Nobody extra — only Manage Server and Administrator.",
                    footer="Use `mod add` to allow a user or role.",
                ),
                ephemeral=True,
            )
            return

        fields = []
        if roles:
            fields.append(("Roles", "\n".join(mentions(guild.get_role, roles))))
        if users:
            fields.append(("Users", "\n".join(mentions(guild.get_member, users))))

        await interaction.response.send_message(
            view=components.panel(
                title="Moderators",
                body="These can change my settings, alongside Manage Server:",
                fields=fields,
                footer=f"{len(roles)} roles · {len(users)} users",
            ),
            ephemeral=True,
        )

    @mod.command(name="reset", description="Revoke every stored user and role")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reset(self, interaction: discord.Interaction) -> None:
        if not modUsers(interaction.guild.id) and not modRoles(interaction.guild.id):
            await interaction.response.send_message(
                view=components.panel(body="Nothing to clear."), ephemeral=True
            )
            return

        db.guild(interaction.guild.id).clear().save()
        await interaction.response.send_message(
            view=components.panel(body="Moderator list cleared."), ephemeral=True
        )


def mentions(lookup, ids: list[int]) -> list[str]:
    found = []
    for entryId in ids:
        entry = lookup(entryId)
        found.append(f"- {entry.mention}" if entry else f"- `{entryId}` (gone)")
    return found


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Mods(bot))
