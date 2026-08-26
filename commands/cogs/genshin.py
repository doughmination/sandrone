import datetime as dt

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from sandrone import doughchecks
from utils.doughmination import DoughminationError, GenshinNotFoundError, dough

genshinAccounts = {
    "main": {"label": "Main", "uid": "691386457"},
    "alt": {"label": "Alt", "uid": "640990645"},
}
defaultAccount = "main"

accountChoices = [
    app_commands.Choice(name=account["label"], value=key)
    for key, account in genshinAccounts.items()
]

accountBySubcommand = {"main-chara": "main", "alt-chara": "alt"}

elementEmojiMap = {
    "Pyro": "🔥",
    "Hydro": "💧",
    "Anemo": "🌀",
    "Electro": "⚡",
    "Cryo": "❄️",
    "Geo": "🪨",
    "Dendro": "🌿",
    "All": "✨",
}
elementOrder = ["Pyro", "Hydro", "Anemo", "Electro", "Cryo", "Geo", "Dendro", "All"]

slotLabels = {
    "flower": "Flower",
    "plume": "Plume",
    "sands": "Sands",
    "goblet": "Goblet",
    "circlet": "Circlet",
}

embedColor = discord.Color.fuchsia()
successColor = discord.Color.green()
errorColor = discord.Color.red()


def resolveAccount(key: str | None) -> dict:
    return genshinAccounts.get(key or defaultAccount, genshinAccounts[defaultAccount])


def elementEmoji(element: str) -> str:
    return elementEmojiMap.get(element, "•")


def stars(rarity: int) -> str:
    return "★" * max(0, rarity)


def formatStat(stat: dict | None) -> str | None:
    if not stat:
        return None
    value = f"{stat['value']:.1f}%" if stat["is_percent"] else str(round(stat["value"]))
    return f"{stat['name']}: {value}"


def capFieldLines(lines: list[str]) -> str:
    if not lines:
        return "—"
    limit = 1024
    kept: list[str] = []
    length = 0
    for i, line in enumerate(lines):
        tail = f"\n…and {len(lines) - i} more"
        addition = (1 if kept else 0) + len(line)
        if length + addition + len(tail) > limit:
            kept.append(f"…and {len(lines) - i} more")
            break
        kept.append(line)
        length += addition
    return "\n".join(kept)


def parseTimestamp(ms: int | None) -> dt.datetime:
    if ms:
        return dt.datetime.fromtimestamp(ms / 1000, tz=dt.UTC)
    return dt.datetime.now(dt.UTC)


def findCharacter(characters: list[dict], query: str) -> dict | None:
    q = query.lower()
    for c in characters:
        if c["name"].lower() == q:
            return c
    for c in characters:
        if q in c["name"].lower():
            return c
    return None


def buildErrorEmbed(
    error: Exception, accountLabel: str, notFoundTitle: str
) -> discord.Embed:
    notFound = isinstance(error, GenshinNotFoundError)
    message = (
        f"No Enka.Network record for the {accountLabel} account. "
        "The profile may be private, unindexed, or the UID is wrong."
        if notFound
        else str(error)
    )
    embed = discord.Embed(
        color=errorColor,
        title=notFoundTitle if notFound else "❌ Error",
        description=message,
    )
    embed.timestamp = dt.datetime.now(dt.UTC)
    return embed


def buildCharacterEmbed(detail: dict, accountLabel: str) -> discord.Embed:
    embed = discord.Embed(
        color=embedColor if detail["owned"] else discord.Color.light_gray(),
        title=f"{elementEmoji(detail['element'])} {detail['name']}",
        description=f"{stars(detail['rarity'])} • {detail['element']} • {accountLabel} account",
    )
    embed.timestamp = parseTimestamp(detail.get("updated_at"))

    if detail.get("icon_url"):
        embed.set_thumbnail(url=detail["icon_url"])

    if not detail["owned"]:
        embed.add_field(
            name="Ownership", value="❌ Not owned on this account.", inline=False
        )
        return embed

    embed.add_field(
        name="Level",
        value=str(detail["level"]) if detail.get("level") is not None else "Unknown",
        inline=True,
    )
    embed.add_field(
        name="Constellation", value=f"C{detail['constellation']}", inline=True
    )
    embed.add_field(
        name="Friendship",
        value=str(detail["friendship"])
        if detail.get("friendship") is not None
        else "—",
        inline=True,
    )

    if not detail["tracked"]:
        embed.add_field(
            name="ℹ️ Last known",
            value="This character isn't in the live showcase right now, so the build below may be missing. Level/constellation are last-known values.",
            inline=False,
        )

    weapon = detail.get("weapon")
    if weapon:
        weaponStats = " • ".join(
            s
            for s in (
                formatStat(weapon.get("base_stat")),
                formatStat(weapon.get("sub_stat")),
            )
            if s
        )
        value = f"**{weapon['name']}** {stars(weapon['rarity'])}\nLv.{weapon['level']} • R{weapon['refinement']}"
        if weaponStats:
            value += f"\n{weaponStats}"
        embed.add_field(name="⚔️ Weapon", value=value, inline=False)

    artifacts = detail.get("artifacts") or []
    if artifacts:
        lines = []
        for a in artifacts:
            main = formatStat(a.get("main_stat"))
            slot = slotLabels.get(a["slot"], a["slot"])
            line = f"**{slot}** +{a['level']} — {a['set_name']}"
            if main:
                line += f"\n  {main}"
            lines.append(line)
        embed.add_field(
            name=f"🛡️ Artifacts ({len(artifacts)})", value="\n".join(lines), inline=False
        )
    elif detail["tracked"]:
        embed.add_field(
            name="🛡️ Artifacts",
            value="No artifact data — pin this character to the in-game showcase to expose their full build.",
            inline=False,
        )

    return embed


class Genshin(
    commands.GroupCog, name="genshin", description="Genshin Impact character lookups"
):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    async def charaAutocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        accountKey = accountBySubcommand.get(
            interaction.command.name if interaction.command else ""
        )
        if not accountKey:
            return []

        account = genshinAccounts[accountKey]
        try:
            roster = await dough.getGenshinRoster(account["uid"])
        except DoughminationError, RuntimeError, aiohttp.ClientError, TimeoutError:
            return []

        q = current.lower()
        owned = [
            c for c in roster["characters"] if c["owned"] and q in c["name"].lower()
        ]
        owned.sort(key=lambda c: (-(c.get("level") or 0), c["name"]))

        return [
            app_commands.Choice(
                name=f"{c['name']} (Lv.{c['level']})"
                if c.get("level") is not None
                else c["name"],
                value=c["name"],
            )
            for c in owned[:25]
        ]

    @app_commands.command(
        name="stats",
        description="Quick overview of an account (level, owned count, etc.)",
    )
    @app_commands.describe(account="Which account (defaults to Main)")
    @app_commands.choices(account=accountChoices)
    @doughchecks.has_permissions(embed_links=True)
    async def statsSlash(
        self, interaction: discord.Interaction, account: str | None = None
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        acc = resolveAccount(account)

        try:
            roster = await dough.getGenshinRoster(acc["uid"])
        except (
            DoughminationError,
            RuntimeError,
            aiohttp.ClientError,
            TimeoutError,
        ) as error:
            await interaction.followup.send(
                embed=buildErrorEmbed(error, acc["label"], "❓ Account Not Found")
            )
            return

        untracked = roster["owned_count"] - roster["tracked_count"]
        embed = discord.Embed(
            color=successColor,
            title=f"📊 Genshin Stats — {roster.get('nickname') or acc['label']}",
        )
        embed.timestamp = parseTimestamp(roster.get("updated_at"))
        embed.add_field(name="UID", value=roster["uid"], inline=True)
        embed.add_field(
            name="Adventure Rank",
            value=str(roster["player_level"])
            if roster.get("player_level")
            else "Unknown",
            inline=True,
        )
        embed.add_field(name="Account", value=acc["label"], inline=True)
        embed.add_field(
            name="Owned",
            value=f"{roster['owned_count']} / {roster['total_count']}",
            inline=True,
        )
        embed.add_field(
            name="Tracked live", value=str(roster["tracked_count"]), inline=True
        )
        embed.add_field(name="Last known only", value=str(untracked), inline=True)

        notes = []
        if roster.get("partial"):
            notes.append(
                '⚠️ Only pinned showcase characters visible — enable "Display all your characters" in-game.'
            )
        if roster.get("stale"):
            notes.append(
                "ℹ️ Served from the ownership ledger (Enka unavailable) — figures are last-known."
            )
        if notes:
            embed.description = "\n".join(notes)

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="roster", description="List the characters you own, grouped by element"
    )
    @app_commands.describe(account="Which account (defaults to Main)")
    @app_commands.choices(account=accountChoices)
    @doughchecks.has_permissions(embed_links=True)
    async def rosterSlash(
        self, interaction: discord.Interaction, account: str | None = None
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        acc = resolveAccount(account)

        try:
            roster = await dough.getGenshinRoster(acc["uid"])
        except (
            DoughminationError,
            RuntimeError,
            aiohttp.ClientError,
            TimeoutError,
        ) as error:
            await interaction.followup.send(
                embed=buildErrorEmbed(error, acc["label"], "❓ Roster Not Found")
            )
            return

        owned = [c for c in roster["characters"] if c["owned"]]

        embed = discord.Embed(
            color=embedColor,
            title=f"🎮 Genshin Roster — {roster.get('nickname') or acc['label']}",
            description=(
                f"**UID:** {roster['uid']}"
                + (
                    f" • **AR {roster['player_level']}**"
                    if roster.get("player_level")
                    else ""
                )
                + f"\n**Owned:** {roster['owned_count']}/{roster['total_count']} characters"
                + f" • **Tracked live:** {roster['tracked_count']}"
            ),
        )
        embed.timestamp = parseTimestamp(roster.get("updated_at"))

        for element in elementOrder:
            inElement = sorted(
                (c for c in owned if c["element"] == element),
                key=lambda c: (-(c.get("level") or 0), c["name"]),
            )
            if not inElement:
                continue

            lines = []
            for c in inElement:
                level = f"Lv.{c['level']}" if c.get("level") is not None else "Lv.?"
                flag = "" if c["tracked"] else " *(last known)*"
                lines.append(f"{c['name']} — {level}{flag}")

            label = "Traveler" if element == "All" else element
            embed.add_field(
                name=f"{elementEmoji(element)} {label} ({len(inElement)})",
                value=capFieldLines(lines),
                inline=True,
            )

        if roster.get("partial"):
            embed.add_field(
                name="⚠️ Partial data",
                value=(
                    "Only your pinned showcase characters are visible. Enable "
                    '**"Display all your characters"** in-game (Character Showcase) '
                    "for the full roster."
                ),
                inline=False,
            )

        if roster.get("stale"):
            embed.set_footer(
                text="Served from the ownership ledger — Enka was unavailable, levels are last-known."
            )

        await interaction.followup.send(embed=embed)

    async def characterSlash(
        self,
        interaction: discord.Interaction,
        accountKey: str,
        name: str,
        ephemeral: bool,
    ) -> None:
        await interaction.response.defer(ephemeral=ephemeral)
        account = genshinAccounts[accountKey]

        try:
            roster = await dough.getGenshinRoster(account["uid"])
            match = findCharacter(roster["characters"], name)
            if not match:
                await interaction.followup.send(
                    content=f'❌ No character matching "{name}" was found in the catalog.'
                )
                return
            detail = await dough.getGenshinCharacter(account["uid"], match["id"])
            await interaction.followup.send(
                embed=buildCharacterEmbed(detail, account["label"])
            )
        except (
            DoughminationError,
            RuntimeError,
            aiohttp.ClientError,
            TimeoutError,
        ) as error:
            await interaction.followup.send(
                embed=buildErrorEmbed(error, account["label"], "❓ Not Found")
            )

    @app_commands.command(
        name="main-chara", description="Character detail on the Main account"
    )
    @app_commands.describe(
        name="Character name", ephemeral="Only show the reply to you (default: true)"
    )
    @app_commands.autocomplete(name=charaAutocomplete)
    @doughchecks.has_permissions(embed_links=True)
    async def mainCharaSlash(
        self, interaction: discord.Interaction, name: str, ephemeral: bool = True
    ) -> None:
        await self.characterSlash(interaction, "main", name, ephemeral)

    @app_commands.command(
        name="alt-chara", description="Character detail on the Alt account"
    )
    @app_commands.describe(
        name="Character name", ephemeral="Only show the reply to you (default: true)"
    )
    @app_commands.autocomplete(name=charaAutocomplete)
    @doughchecks.has_permissions(embed_links=True)
    async def altCharaSlash(
        self, interaction: discord.Interaction, name: str, ephemeral: bool = True
    ) -> None:
        await self.characterSlash(interaction, "alt", name, ephemeral)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Genshin(bot))
