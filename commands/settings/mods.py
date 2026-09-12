import discord
from discord import app_commands
from discord.ext import commands

from sandrone import config
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

    Manage Server, Administrator and the bot owners always pass, whatever the
    stored list says.
    """
    if member.id in config.owners or hasServerPermissions(member):
        return True

    guildId = member.guild.id
    if member.id in modUsers(guildId):
        return True

    roleIds = set(modRoles(guildId))
    return any(role.id in roleIds for role in member.roles)


def isManager():
    """Check for settings commands: a mod, or someone with Manage Server."""

    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage("This command can only be used in a server.")
        if not isinstance(ctx.author, discord.Member) or not isMod(ctx.author):
            raise commands.MissingPermissions(["manage_guild"])
        return True

    return commands.check(predicate)


class Mods(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_group(
        name="mod",
        description="Choose who may change my settings here",
        invoke_without_command=True,
    )
    @commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def mod(self, ctx: commands.Context) -> None:
        await self.listMods(ctx)

    @mod.command(name="add", description="Let a user or role change my settings")
    @app_commands.describe(target="The user or role to allow.")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def add(self, ctx: commands.Context, target: ModTarget) -> None:
        if isinstance(target, discord.Member) and target.bot:
            await ctx.send(
                view=components.error("Bots cannot be moderators."), ephemeral=True
            )
            return

        changed = setMod(ctx.guild.id, target, True)
        body = (
            f"{target.mention} can now change my settings."
            if changed
            else f"{target.mention} already could."
        )
        await ctx.send(view=components.panel(body=body), ephemeral=True)

    @mod.command(name="remove", description="Revoke a user or role")
    @app_commands.describe(target="The user or role to revoke.")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def remove(self, ctx: commands.Context, target: ModTarget) -> None:
        changed = setMod(ctx.guild.id, target, False)
        if changed:
            body = f"{target.mention} can no longer change my settings."
        elif isinstance(target, discord.Member) and hasServerPermissions(target):
            body = f"{target.mention} was not on the list — they have Manage Server."
        else:
            body = f"{target.mention} was not on the list."
        await ctx.send(view=components.panel(body=body), ephemeral=True)

    @mod.command(name="list", description="Show who may change my settings")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def listMods(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        users = modUsers(guild.id)
        roles = modRoles(guild.id)

        if not users and not roles:
            await ctx.send(
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

        await ctx.send(
            view=components.panel(
                title="Moderators",
                body="These can change my settings, alongside Manage Server:",
                fields=fields,
                footer=f"{len(roles)} roles · {len(users)} users",
            ),
            ephemeral=True,
        )

    @mod.command(name="reset", description="Revoke every stored user and role")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def reset(self, ctx: commands.Context) -> None:
        if not modUsers(ctx.guild.id) and not modRoles(ctx.guild.id):
            await ctx.send(
                view=components.panel(body="Nothing to clear."), ephemeral=True
            )
            return

        db.guild(ctx.guild.id).clear().save()
        await ctx.send(
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
