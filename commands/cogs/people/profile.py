import datetime as dt

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from sandrone import mood
from utils import components
from utils.doughmination import DoughminationError, ProfileNotFoundError, dough

statusEmoji = {
    "online": "🟢",
    "idle": "🌙",
    "dnd": "⛔",
    "offline": "⚪",
}

embedColor = discord.Color.fuchsia()


def parseTimestamp(ms: int | None) -> dt.datetime:
    if ms:
        return dt.datetime.fromtimestamp(ms / 1000, tz=dt.UTC)
    return dt.datetime.now(dt.UTC)


class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="profile",
        description="Get a user's Discord profile",
    )
    @app_commands.describe(user="The user to look up (defaults to you)")
    @mood.sassy
    async def profile(
        self, interaction: discord.Interaction, user: discord.Member | None = None
    ) -> None:
        await interaction.response.defer()
        target = user or interaction.user

        try:
            profile = await dough.getProfile(target.id)
        except ProfileNotFoundError:
            await interaction.followup.send(
                f"❌ No Discord profile found for {target.mention}."
            )
            return
        except (
            DoughminationError,
            RuntimeError,
            aiohttp.ClientError,
            TimeoutError,
        ) as error:
            await interaction.followup.send(
                view=components.panel(
                    title="❌ Could not fetch profile",
                    body=str(error),
                    footer="Sandrone",
                    color=components.RED,
                )
            )
            return

        await interaction.followup.send(view=self.buildProfilePanel(profile))

    def buildProfilePanel(self, profile: dict) -> components.Panel:
        user = profile["user"]
        presence = profile.get("presence")
        badges = profile.get("badges") or []
        connectedAccounts = profile.get("connected_accounts") or []
        timezone = profile.get("timezone")

        displayName = (
            user.get("display_name") or user.get("global_name") or user["username"]
        )
        emoji = statusEmoji.get(presence["status"], "⚪") if presence else "⚪"

        color = (
            discord.Color(user["accent_color"])
            if user.get("accent_color") is not None
            else embedColor
        )

        fields: list[components.Field] = [
            ("User ID", str(user["id"])),
            ("Status", f"{emoji} {presence['status'] if presence else 'unknown'}"),
        ]
        if user.get("pronouns"):
            fields.append(("Pronouns", user["pronouns"]))
        if user.get("bio"):
            fields.append(("Bio", user["bio"][:1024]))
        if user.get("premium"):
            fields.append(("Nitro", user["premium"]["type"]))
        if user.get("clan"):
            fields.append(("Clan Tag", user["clan"]["tag"]))
        if timezone:
            fields.append(("Timezone", timezone["timezone"]))
        if badges:
            badgeList = ", ".join(b["description"] for b in badges[:10])
            fields.append((f"Badges [{len(badges)}]", badgeList))

        socials = [
            f"{a['type']}: {a['name']}"
            for a in connectedAccounts
            if a.get("type") != "domain"
        ][:10]
        if socials:
            fields.append(("Connected Accounts", "\n".join(socials)))

        return components.panel(
            title=f"{displayName} (@{user['username']})",
            body=f"-# updated {parseTimestamp(profile.get('updated_at')):%Y-%m-%d}",
            fields=fields,
            thumbnail=user.get("avatar_url"),
            images=[user["banner_url"]] if user.get("banner_url") else None,
            footer="Sandrone",
            color=color,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Profile(bot))
