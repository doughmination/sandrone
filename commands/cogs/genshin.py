import asyncio
import hashlib
import io
import re
import time
from pathlib import Path
from typing import Any, NamedTuple

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils import components, genshin_card
from utils.doughmination import DoughminationError, GenshinNotFoundError, dough

embedColor = components.FUCHSIA

jumpPageSize = 25
apiErrors = (DoughminationError, RuntimeError, aiohttp.ClientError, TimeoutError)

CACHE_DIR = Path("img/genshin-cache")
ROSTER_TTL = 20.0

CONTROL_TEMPLATE = (
    r"gsc:(?P<action>[a-z]+):(?P<uid>\d{9,10}):(?P<index>\d+):(?P<menu>\d+)"
)
JUMP_TEMPLATE = r"gsj:(?P<uid>\d{9,10}):(?P<index>\d+):(?P<menu>\d+)"

ELEMENT_COLOR = {
    "Pyro": 0xE0684B,
    "Hydro": 0x3E9BD8,
    "Anemo": 0x52B0B1,
    "Electro": 0x9876AD,
    "Cryo": 0x46A8BA,
    "Geo": 0xBB9F4B,
    "Dendro": 0x4D8E52,
}

# --- small in-process caches -------------------------------------------------

_rosterCache: dict[str, tuple[float, dict]] = {}
_cardCache: dict[tuple[str, str, Any], bytes] = {}
_imageMem: dict[str, bytes] = {}


def validUid(raw: str) -> str | None:
    uid = raw.strip()
    return uid if uid.isdigit() and 9 <= len(uid) <= 10 else None


def menuPages(count: int) -> int:
    return max(1, -(-count // jumpPageSize))


def sortedOwned(roster: dict) -> list[dict]:
    return sorted(
        (c for c in roster["characters"] if c["owned"]),
        key=lambda c: (-(c.get("level") or 0), c["name"]),
    )


async def getRoster(uid: str) -> dict:
    now = time.monotonic()
    hit = _rosterCache.get(uid)
    if hit and now - hit[0] < ROSTER_TTL:
        return hit[1]
    data = await dough.getGenshinRoster(uid)
    _rosterCache[uid] = (now, data)
    return data


async def _fetchImage(session: aiohttp.ClientSession, url: str) -> bytes | None:
    if url in _imageMem:
        return _imageMem[url]
    key = hashlib.sha1(url.encode()).hexdigest()
    path = CACHE_DIR / f"{key}.img"
    try:
        if path.exists():
            data = path.read_bytes()
            _imageMem[url] = data
            return data
    except OSError:
        pass
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return None
            data = await resp.read()
    except (aiohttp.ClientError, TimeoutError):
        return None
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    except OSError:
        pass
    _imageMem[url] = data
    return data


async def gatherImages(urls: list[str]) -> dict[str, bytes]:
    if not urls:
        return {}
    async with aiohttp.ClientSession() as session:
        blobs = await asyncio.gather(*(_fetchImage(session, u) for u in urls))
    return {u: b for u, b in zip(urls, blobs) if b}


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


async def renderCharacterPng(uid: str, hero: dict) -> tuple[bytes, dict]:
    detail = await dough.getGenshinCharacter(uid, hero["id"])
    key = (uid, hero["id"], detail.get("updated_at"))
    cached = _cardCache.get(key)
    if cached is not None:
        return cached, detail

    images = await gatherImages(genshin_card.iconUrls(detail))
    ar = None
    roster = _rosterCache.get(uid)
    if roster:
        ar = roster[1].get("player_level")
    png = await asyncio.to_thread(
        genshin_card.renderCard, detail, images, uid=uid, ar=ar
    )

    if len(_cardCache) > 48:
        _cardCache.clear()
    _cardCache[key] = png
    return png, detail


class State(NamedTuple):
    uid: str
    index: int
    menu: int

    def control(self, action: str) -> str:
        return f"gsc:{action}:{self.uid}:{self.index}:{self.menu}"

    def jumpId(self) -> str:
        return f"gsj:{self.uid}:{self.index}:{self.menu}"


def applyAction(action: str, uid: str, index: int, menu: int) -> State:
    """Next paginator state from a button press. Over-shoots are clamped once
    the roster is loaded in :func:`buildView`."""
    if action == "prev":
        target = max(0, index - 1)
        return State(uid, target, target // jumpPageSize)
    if action == "next":
        target = index + 1
        return State(uid, target, target // jumpPageSize)
    if action == "mprev":
        return State(uid, index, max(0, menu - 1))
    if action == "mnext":
        return State(uid, index, menu + 1)
    return State(uid, index, menu)


def renderContainer(
    state: State, owned: list[dict], filename: str
) -> discord.ui.Container:
    index = min(max(state.index, 0), len(owned) - 1)
    pages = menuPages(len(owned))
    menu = min(max(state.menu, 0), pages - 1)
    here = state._replace(index=index, menu=menu)
    char = owned[index]

    accent = ELEMENT_COLOR.get(char.get("element", ""), embedColor)
    box = discord.ui.Container(accent_colour=accent)
    box.add_item(
        discord.ui.MediaGallery(
            components.image(f"attachment://{filename}", alt=char["name"])
        )
    )
    tracked = "🟢 Live showcase" if char.get("tracked") else "⚪ Last known"
    box.add_item(
        discord.ui.TextDisplay(
            f"-# {char['name']} · Lv.{char.get('level', '?')} · {tracked} · "
            f"Character {index + 1}/{len(owned)} · UID {state.uid}"
        )
    )

    nav = discord.ui.ActionRow()
    nav.add_item(
        discord.ui.Button(
            emoji="◀",
            style=discord.ButtonStyle.secondary,
            custom_id=here.control("prev"),
            disabled=index == 0,
        )
    )
    nav.add_item(
        discord.ui.Button(
            emoji="▶",
            style=discord.ButtonStyle.secondary,
            custom_id=here.control("next"),
            disabled=index >= len(owned) - 1,
        )
    )
    box.add_item(nav)

    start = menu * jumpPageSize
    window = owned[start : start + jumpPageSize]
    jumpRow = discord.ui.ActionRow()
    jumpRow.add_item(
        discord.ui.Select(
            custom_id=here.jumpId(),
            placeholder=f"Jump to a character… ({start + 1}–{start + len(window)})",
            options=[
                discord.SelectOption(
                    label=c["name"][:100],
                    value=str(start + offset),
                    description=f"Lv.{c.get('level', '?')} · {c['element']}"[:100],
                    default=(start + offset) == index,
                )
                for offset, c in enumerate(window)
            ],
        )
    )
    box.add_item(jumpRow)

    if pages > 1:
        pager = discord.ui.ActionRow()
        pager.add_item(
            discord.ui.Button(
                label="◀ names",
                style=discord.ButtonStyle.secondary,
                custom_id=here.control("mprev"),
                disabled=menu == 0,
            )
        )
        pager.add_item(
            discord.ui.Button(
                label="names ▶",
                style=discord.ButtonStyle.secondary,
                custom_id=here.control("mnext"),
                disabled=menu >= pages - 1,
            )
        )
        box.add_item(pager)

    return box


async def buildView(state: State) -> tuple[components.Panel, discord.File | None]:
    roster = await getRoster(state.uid)
    owned = sortedOwned(roster)
    if not owned:
        note = (
            'This account has no visible characters. Enable "Display all your '
            'characters" on the in-game Character Showcase, or pin a few, then retry.'
        )
        if roster.get("stale"):
            note = "Enka.Network is unavailable right now — try again shortly."
        return components.panel(
            title="❓ Nothing to show", body=note, color=components.RED
        ), None

    index = min(max(state.index, 0), len(owned) - 1)
    filename = "genshin.png"
    png, _ = await renderCharacterPng(state.uid, owned[index])
    file = discord.File(io.BytesIO(png), filename=filename)
    return components.Panel(renderContainer(state, owned, filename)), file


async def _swapView(interaction: discord.Interaction, state: State) -> None:
    await interaction.response.defer()
    try:
        view, file = await buildView(state)
    except apiErrors as error:
        await interaction.edit_original_response(
            view=buildErrorPanel(error, state.uid), attachments=[]
        )
        return
    await interaction.edit_original_response(
        view=view, attachments=[file] if file else []
    )


class GenshinControl(
    discord.ui.DynamicItem[discord.ui.Button], template=CONTROL_TEMPLATE
):
    def __init__(self, nextState: State, customId: str) -> None:
        self.nextState = nextState
        super().__init__(
            discord.ui.Button(style=discord.ButtonStyle.secondary, custom_id=customId)
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "GenshinControl":
        nextState = applyAction(
            match["action"], match["uid"], int(match["index"]), int(match["menu"])
        )
        return cls(nextState, match.string)

    async def callback(self, interaction: discord.Interaction) -> None:
        await _swapView(interaction, self.nextState)


class GenshinJump(discord.ui.DynamicItem[discord.ui.Select], template=JUMP_TEMPLATE):
    def __init__(self, uid: str, customId: str) -> None:
        self.uid = uid
        super().__init__(
            discord.ui.Select(
                custom_id=customId,
                options=[discord.SelectOption(label="_", value="0")],
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "GenshinJump":
        return cls(match["uid"], match.string)

    async def callback(self, interaction: discord.Interaction) -> None:
        picked = int(self.item.values[0])
        state = State(self.uid, picked, picked // jumpPageSize)
        await _swapView(interaction, state)


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

        state = State(clean, 0, 0)
        try:
            view, file = await buildView(state)
        except apiErrors as error:
            await interaction.followup.send(view=buildErrorPanel(error, clean))
            return

        if file is not None:
            await interaction.followup.send(view=view, file=file)
        else:
            await interaction.followup.send(view=view)


async def setup(bot: commands.Bot) -> None:
    bot.add_dynamic_items(GenshinControl, GenshinJump)
    await bot.add_cog(Genshin(bot))
