import datetime as dt

import discord
from discord import app_commands
from discord.ext import commands

from utils.doughmination import ProfileNotFoundError, dough

statusEmoji = {
    "online": "🟢",
    "idle": "🌙",
    "dnd": "⛔",
    "offline": "⚪",
}

embedColor = discord.Color.blurple()
errorColor = discord.Color.red()


def parseTimestamp(ms: int | None) -> dt.datetime:
    if ms:
        return dt.datetime.fromtimestamp(ms / 1000, tz=dt.UTC)
    return dt.datetime.now(dt.UTC)


class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="profile", description="Get a user's Discord profile")
    @app_commands.describe(user="The user to look up (defaults to you)")
    async def profileSlash(self, interaction: discord.Interaction, user: discord.Member | None = None) -> None:
        await interaction.response.defer()
        target = user or interaction.user

        try:
            profile = await dough.getProfile(target.id)
        except ProfileNotFoundError:
            await interaction.followup.send(f"❌ No Discord profile found for {target.mention}.")
            return
        except Exception as error:
            embed = discord.Embed(color=errorColor, title="❌ Could not fetch profile", description=str(error))
            embed.timestamp = dt.datetime.now(dt.UTC)
            await interaction.followup.send(embed=embed)
            return

        await interaction.followup.send(embed=self.buildProfileEmbed(profile))

    def buildProfileEmbed(self, profile: dict) -> discord.Embed:
        user = profile["user"]
        presence = profile.get("presence")
        badges = profile.get("badges") or []
        connectedAccounts = profile.get("connected_accounts") or []
        timezone = profile.get("timezone")

        displayName = user.get("display_name") or user.get("global_name") or user["username"]
        emoji = statusEmoji.get(presence["status"], "⚪") if presence else "⚪"

        color = discord.Color(user["accent_color"]) if user.get("accent_color") is not None else embedColor
        embed = discord.Embed(color=color)
        embed.set_author(name=f"{displayName} (@{user['username']})", icon_url=user.get("avatar_url"))
        embed.set_thumbnail(url=user.get("avatar_url"))
        embed.add_field(name="User ID", value=user["id"], inline=True)
        embed.add_field(name="Status", value=f"{emoji} {presence['status'] if presence else 'unknown'}", inline=True)
        embed.timestamp = parseTimestamp(profile.get("updated_at"))

        if user.get("banner_url"):
            embed.set_image(url=user["banner_url"])

        if user.get("pronouns"):
            embed.add_field(name="Pronouns", value=user["pronouns"], inline=True)

        if user.get("bio"):
            embed.add_field(name="Bio", value=user["bio"][:1024], inline=False)

        if user.get("premium"):
            embed.add_field(name="Nitro", value=user["premium"]["type"], inline=True)

        if user.get("clan"):
            embed.add_field(name="Clan Tag", value=user["clan"]["tag"], inline=True)

        if timezone:
            embed.add_field(name="Timezone", value=timezone["timezone"], inline=True)

        if badges:
            badgeList = ", ".join(b["description"] for b in badges[:10])
            embed.add_field(name=f"Badges [{len(badges)}]", value=badgeList, inline=False)

        socials = [f"{a['type']}: {a['name']}" for a in connectedAccounts if a.get("type") != "domain"][:10]
        if socials:
            embed.add_field(name="Connected Accounts", value="\n".join(socials), inline=False)

        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Profile(bot))
