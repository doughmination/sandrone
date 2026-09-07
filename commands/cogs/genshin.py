import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils import components
from utils.doughmination import DoughminationError, GenshinNotFoundError, dough

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

slotLabels = {
    "flower": "Flower",
    "plume": "Plume",
    "sands": "Sands",
    "goblet": "Goblet",
    "circlet": "Circlet",
}

embedColor = components.FUCHSIA
successColor = discord.Color.green()

jumpPageSize = 25
apiErrors = (DoughminationError, RuntimeError, aiohttp.ClientError, TimeoutError)


def elementEmoji(element: str) -> str:
    return elementEmojiMap.get(element, "•")


def stars(rarity: int) -> str:
    return "★" * max(0, rarity)


def formatStat(stat: dict | None) -> str | None:
    if not stat:
        return None
    value = f"{stat['value']:.1f}%" if stat["is_percent"] else str(round(stat["value"]))
    return f"{stat['name']}: {value}"


def validUid(raw: str) -> str | None:
    uid = raw.strip()
    return uid if uid.isdigit() and 9 <= len(uid) <= 10 else None


def sectionText(
    title: str | None = None,
    body: str | None = None,
    fields: list[components.Field] | None = None,
) -> str:
    parts = [components.heading(title)] if title else []
    if body:
        parts.append(body)
    if fields:
        parts.append(components.renderFields(fields))
    return "\n\n".join(parts)


def buildErrorPanel(error: Exception, uid: str) -> components.Panel:
    notFound = isinstance(error, GenshinNotFoundError)
    message = (
        f"No Enka.Network record for UID `{uid}`. The profile may be private, "
        "unindexed, or the UID is wrong."
        if notFound
        else str(error)
    )
    return components.panel(
        title="❓ Not found" if notFound else "❌ Error",
        body=message,
        color=components.RED,
    )


def overviewSummary(roster: dict) -> tuple[str | None, list[components.Field]]:
    untracked = roster["owned_count"] - roster["tracked_count"]

    notes = []
    if roster.get("partial"):
        notes.append(
            '⚠️ Only pinned showcase characters are visible — enable "Display all '
            'your characters" in-game.'
        )
    if roster.get("stale"):
        notes.append(
            "ℹ️ Served from the ownership ledger (Enka unavailable) — figures are "
            "last-known."
        )

    fields: list[components.Field] = [
        ("UID", str(roster["uid"])),
        (
            "Adventure Rank",
            str(roster["player_level"]) if roster.get("player_level") else "Unknown",
        ),
        ("Owned", f"{roster['owned_count']} / {roster['total_count']}"),
        ("Tracked live", str(roster["tracked_count"])),
        ("Last known only", str(untracked)),
    ]
    return "\n".join(notes) or None, fields


def characterFields(detail: dict) -> list[components.Field]:
    if not detail.get("owned"):
        return [("Ownership", "❌ Not owned on this account.")]

    fields: list[components.Field] = [
        ("Constellation", f"C{detail.get('constellation', 0)}"),
        (
            "Friendship",
            str(detail["friendship"]) if detail.get("friendship") is not None else "—",
        ),
    ]

    if not detail.get("tracked"):
        fields.append(
            (
                "ℹ️ Last known",
                (
                    "This character isn't in the live showcase right now, so the "
                    "build below may be incomplete."
                ),
            )
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
        value = (
            f"**{weapon['name']}** {stars(weapon['rarity'])}\n"
            f"Lv.{weapon['level']} • R{weapon['refinement']}"
        )
        if weaponStats:
            value += f"\n{weaponStats}"
        fields.append(("⚔️ Weapon", value))

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
        fields.append((f"🛡️ Artifacts ({len(artifacts)})", "\n".join(lines)))
    elif detail.get("tracked"):
        fields.append(
            (
                "🛡️ Artifacts",
                (
                    "No artifact data — pin this character to the in-game showcase "
                    "to expose their full build."
                ),
            )
        )

    return fields


class OverviewRow(discord.ui.ActionRow["GenshinView"]):
    @discord.ui.button(
        label="Browse characters", emoji="🎴", style=discord.ButtonStyle.primary
    )
    async def browse(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        view = self.view
        if view is None:
            return
        view.mode = "browser"
        view.showBuild = False
        view.goTo(0)
        await view.refresh(interaction)


class NavRow(discord.ui.ActionRow["GenshinView"]):
    @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
    async def prev(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        view = self.view
        if view is None:
            return
        view.goTo(max(0, view.index - 1))
        await view.refresh(interaction)

    @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
    async def next(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        view = self.view
        if view is None:
            return
        view.goTo(min(len(view.owned) - 1, view.index + 1))
        await view.refresh(interaction)

    @discord.ui.button(label="Full build", style=discord.ButtonStyle.secondary)
    async def build(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        view = self.view
        if view is None:
            return
        view.showBuild = not view.showBuild
        view.buildError = None
        if view.showBuild:
            await view.loadBuild(interaction)
        else:
            await view.refresh(interaction)

    @discord.ui.button(label="Overview", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def back(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        view = self.view
        if view is None:
            return
        view.mode = "overview"
        await view.refresh(interaction)


class JumpRow(discord.ui.ActionRow["GenshinView"]):
    @discord.ui.select(placeholder="Jump to a character…")
    async def jump(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ) -> None:
        view = self.view
        if view is None:
            return
        view.goTo(int(select.values[0]))
        view.showBuild = False
        await view.refresh(interaction)


class MenuPagerRow(discord.ui.ActionRow["GenshinView"]):
    @discord.ui.button(label="◀ names", style=discord.ButtonStyle.secondary)
    async def mprev(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        view = self.view
        if view is None:
            return
        view.menuPage = max(0, view.menuPage - 1)
        await view.refresh(interaction)

    @discord.ui.button(label="names ▶", style=discord.ButtonStyle.secondary)
    async def mnext(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        view = self.view
        if view is None:
            return
        view.menuPage = min(view.menuPageCount - 1, view.menuPage + 1)
        await view.refresh(interaction)


class GenshinView(discord.ui.LayoutView):
    def __init__(self, uid: str, roster: dict, authorId: int) -> None:
        super().__init__(timeout=180)
        self.uid = uid
        self.roster = roster
        self.authorId = authorId
        self.owned = sorted(
            (c for c in roster["characters"] if c["owned"]),
            key=lambda c: (-(c.get("level") or 0), c["name"]),
        )
        self.mode = "overview"
        self.index = 0
        self.menuPage = 0
        self.showBuild = False
        self.buildError: str | None = None
        self.detailCache: dict[str, dict] = {}
        self.expired = False
        self.message: discord.Message | None = None

        self.box = discord.ui.Container(accent_colour=embedColor)
        self.overviewRow = OverviewRow()
        self.navRow = NavRow()
        self.jumpRow = JumpRow()
        self.menuPagerRow = MenuPagerRow()

        self.add_item(self.box)
        self.render()

    @property
    def menuPageCount(self) -> int:
        return max(1, -(-len(self.owned) // jumpPageSize))

    def goTo(self, index: int) -> None:
        """Move to a character and snap the jump menu to the block holding it."""
        self.index = index
        self.menuPage = index // jumpPageSize
        self.buildError = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.authorId:
            await interaction.response.send_message(
                "Only the person who ran this command can use these controls.",
                ephemeral=True,
            )
            return False
        return True

    async def refresh(self, interaction: discord.Interaction) -> None:
        self.render()
        await interaction.response.edit_message(view=self)

    async def loadBuild(self, interaction: discord.Interaction) -> None:
        char = self.owned[self.index]
        if char["id"] in self.detailCache:
            self.render()
            await interaction.response.edit_message(view=self)
            return

        self.render()
        await interaction.response.edit_message(view=self)
        try:
            self.detailCache[char["id"]] = await dough.getGenshinCharacter(
                self.uid, char["id"]
            )
        except apiErrors:
            self.buildError = (
                "Couldn't load this character's build — they may not be in the "
                "live showcase."
            )
        self.render()
        await interaction.edit_original_response(view=self)

    def render(self) -> None:
        self.box.clear_items()
        if self.mode == "overview" or not self.owned:
            self._renderOverview()
        else:
            self._renderBrowser()
        if self.expired:
            rows = (self.overviewRow, self.navRow, self.jumpRow, self.menuPagerRow)
            for row in rows:
                for child in row.children:
                    if isinstance(child, discord.ui.Button | discord.ui.Select):
                        child.disabled = True

    def _renderOverview(self) -> None:
        self.box.accent_colour = successColor
        header, fields = overviewSummary(self.roster)
        self.box.add_item(
            discord.ui.TextDisplay(
                sectionText(
                    f"📊 Genshin — {self.roster.get('nickname') or self.uid}",
                    header,
                    fields,
                )
            )
        )
        self.overviewRow.browse.disabled = not self.owned
        self.box.add_item(self.overviewRow)

    def _renderBrowser(self) -> None:
        self.box.accent_colour = embedColor
        char = self.owned[self.index]

        lines = [
            components.heading(f"{elementEmoji(char['element'])} {char['name']}"),
            f"{stars(char['rarity'])} • {char['element']}",
            f"**Level {char.get('level', '?')}** • "
            + ("🟢 Live showcase" if char.get("tracked") else "⚪ Last known"),
        ]

        fields: list[components.Field] = []
        if self.showBuild:
            if self.buildError:
                fields.append(("⚠️ Full build", self.buildError))
            elif char["id"] in self.detailCache:
                fields = characterFields(self.detailCache[char["id"]])
            else:
                lines.append("\n*Loading full build…*")

        text = "\n".join(lines)
        if fields:
            text += "\n\n" + components.renderFields(fields)
        text += f"\n\n-# Character {self.index + 1}/{len(self.owned)} • UID {self.uid}"

        icon = char.get("icon_url")
        if icon:
            self.box.add_item(
                discord.ui.Section(
                    discord.ui.TextDisplay(text),
                    accessory=discord.ui.Thumbnail(icon),
                )
            )
        else:
            self.box.add_item(discord.ui.TextDisplay(text))

        self.box.add_item(discord.ui.Separator())

        self.navRow.prev.disabled = self.index == 0
        self.navRow.next.disabled = self.index >= len(self.owned) - 1
        self.navRow.build.label = "Hide build" if self.showBuild else "Full build"
        self.navRow.build.style = (
            discord.ButtonStyle.primary
            if self.showBuild
            else discord.ButtonStyle.secondary
        )
        self.box.add_item(self.navRow)

        self.menuPage = min(self.menuPage, self.menuPageCount - 1)
        start = self.menuPage * jumpPageSize
        window = self.owned[start : start + jumpPageSize]
        self.jumpRow.jump.options = [
            discord.SelectOption(
                label=c["name"][:100],
                value=str(start + offset),
                description=f"Lv.{c.get('level', '?')} • {c['element']}"[:100],
                default=(start + offset) == self.index,
            )
            for offset, c in enumerate(window)
        ]
        self.jumpRow.jump.placeholder = (
            f"Jump to a character… (names {start + 1}–{start + len(window)})"
        )
        self.box.add_item(self.jumpRow)

        if self.menuPageCount > 1:
            self.menuPagerRow.mprev.disabled = self.menuPage == 0
            self.menuPagerRow.mnext.disabled = self.menuPage >= self.menuPageCount - 1
            self.box.add_item(self.menuPagerRow)

    async def on_timeout(self) -> None:
        self.expired = True
        self.render()
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class Genshin(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="genshin", description="Look up a Genshin Impact account by UID"
    )
    @app_commands.describe(uid="The 9–10 digit Genshin UID to look up")
    async def genshinSlash(self, interaction: discord.Interaction, uid: str) -> None:
        await interaction.response.defer()

        clean = validUid(uid)
        if clean is None:
            await interaction.followup.send(
                view=components.error(
                    "That doesn't look like a Genshin UID — it should be 9–10 digits."
                )
            )
            return

        try:
            roster = await dough.getGenshinRoster(clean)
        except apiErrors as error:
            await interaction.followup.send(view=buildErrorPanel(error, clean))
            return

        view = GenshinView(clean, roster, interaction.user.id)
        view.message = await interaction.followup.send(view=view, wait=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Genshin(bot))
