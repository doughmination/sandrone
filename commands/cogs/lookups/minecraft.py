import aiohttp
import base64
import binascii
import discord
from discord import app_commands
from discord.ext import commands
import json
import re
from sandrone import checks, config, mood
from typing import Any, Literal
import urllib.parse
from utils import components

userAgent = (
    f"Sandrone-{config.version} "
    "(https://github.com/doughmination/sandrone)"
)

mojangProfileUrl = "https://api.mojang.com/users/profiles/minecraft/{}"
sessionProfileUrl = (
    "https://sessionserver.mojang.com/session/minecraft/profile/{}"
)
renderBase = "https://mc-heads.net"
statusBase = "https://api.mcsrvstat.us"

maxListedPlayers = 10

usernamePattern = re.compile(r"^[A-Za-z0-9_]{1,16}$")
uuidPattern = re.compile(r"^[0-9a-fA-F]{32}$")
addressPattern = re.compile(r"^[A-Za-z0-9.\-_\[\]:]{1,255}$")
formattingCode = re.compile(r"§.?")

type Edition = Literal["java", "bedrock"]


class Textures:
    def __init__(
        self, skin: str | None, slim: bool, cape: str | None
    ) -> None:
        self.skin = skin
        self.slim = slim
        self.cape = cape


def normaliseName(query: str) -> str | None:
    """A username or (dashed or not) UUID, or None if it's neither."""
    text = query.strip().removeprefix("@")
    undashed = text.replace("-", "")
    if uuidPattern.match(undashed):
        return undashed.lower()
    if usernamePattern.match(text):
        return text
    return None


def normaliseAddress(address: str) -> str | None:
    text = address.strip().lower()
    text = text.removeprefix("https://").removeprefix("http://")
    text = text.removesuffix("/")
    if not text or not addressPattern.match(text):
        return None
    return text


def httpsUrl(url: str) -> str:
    return "https://" + url.removeprefix("http://").removeprefix(
        "https://"
    )


def parseTextures(profile: dict[str, Any]) -> Textures:
    """Pull the skin/cape out of a session server profile."""
    for prop in profile.get("properties") or []:
        if prop.get("name") != "textures":
            continue
        try:
            decoded = json.loads(base64.b64decode(prop.get("value", "")))
        except binascii.Error, ValueError:
            break
        textures = decoded.get("textures") or {}
        skin = textures.get("SKIN") or {}
        cape = textures.get("CAPE") or {}
        model = (skin.get("metadata") or {}).get("model")
        return Textures(
            skin=httpsUrl(skin["url"]) if skin.get("url") else None,
            slim=model == "slim",
            cape=httpsUrl(cape["url"]) if cape.get("url") else None,
        )
    return Textures(skin=None, slim=False, cape=None)


def dashedUuid(uuid: str) -> str:
    return (
        f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}"
    )


def stripFormatting(text: str) -> str:
    return formattingCode.sub("", text)


def skinPanel(
    name: str, uuid: str, textures: Textures
) -> components.Panel:
    model = "Slim (Alex)" if textures.slim else "Classic (Steve)"
    lines = [
        f"> **Model**: {model}",
        f"> **Cape**: {'Yes' if textures.cape else 'No'}",
    ]
    if textures.skin is None:
        lines.append(
            "\nThis player has no custom skin, so they get a default one."
        )

    buttons = [
        components.linkButton(
            "NameMC", f"https://namemc.com/profile/{uuid}"
        )
    ]
    if textures.skin:
        buttons.insert(
            0, components.linkButton("Download skin", textures.skin)
        )

    return components.panel(
        title=f"{name}'s skin",
        body="\n".join(lines),
        thumbnail=f"{renderBase}/avatar/{uuid}",
        images=[
            components.image(
                f"{renderBase}/body/{uuid}/right", alt=f"{name}'s skin"
            )
        ],
        buttons=buttons,
        footer=f"UUID: {dashedUuid(uuid)} · Minecraft",
    )


def statusPanel(
    data: dict[str, Any], address: str, edition: Edition
) -> components.Panel:
    label = "Bedrock" if edition == "bedrock" else "Java"
    footer = f"{label} Edition · mcsrvstat.us"

    if not data.get("online"):
        return components.panel(
            title=f"🔴 {address} is offline",
            body=(
                "Couldn't get a response from that server. It may be "
                "down, or it may not exist at all."
            ),
            footer=footer,
            color=components.RED,
        )

    motd = "\n".join(
        line.strip()
        for line in (data.get("motd") or {}).get("clean") or []
        if line.strip()
    )
    players = data.get("players") or {}
    host = data.get("ip")
    port = data.get("port")

    fields: list[components.Field] = [
        (
            "Players",
            f"{players.get('online', 0)} / {players.get('max', 0)}",
        ),
    ]
    if data.get("version"):
        fields.append(
            (
                "Version",
                components.escapeMarkdown(
                    stripFormatting(str(data["version"]))
                ),
            )
        )
    if host:
        fields.append(
            ("Address", f"`{host}:{port}`" if port else f"`{host}`")
        )
    if data.get("software"):
        fields.append(("Software", str(data["software"])))
    if data.get("gamemode"):
        fields.append(("Game mode", str(data["gamemode"])))

    sample = [
        player.get("name")
        for player in players.get("list") or []
        if player.get("name")
    ]
    if sample:
        names = ", ".join(
            components.escapeMarkdown(name)
            for name in sample[:maxListedPlayers]
        )
        extra = len(sample) - maxListedPlayers
        if extra > 0:
            names += f" and {extra} more"
        fields.append(("Online now", names))

    return components.panel(
        title=f"🟢 {address} is online",
        body=components.codeBlock(motd) if motd else None,
        fields=fields,
        thumbnail=(
            f"{statusBase}/icon/{urllib.parse.quote(address)}"
            if edition == "java"
            else None
        ),
        footer=footer,
    )


class Minecraft(
    commands.GroupCog,
    group_name="minecraft",
    group_description="Minecraft skins and server status",
):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": userAgent},
            timeout=aiohttp.ClientTimeout(total=10),
        )

    async def cog_unload(self) -> None:
        await self.session.close()

    @app_commands.command(
        name="skin", description="Show a Minecraft player's skin"
    )
    @app_commands.describe(player="The player's username or UUID")
    @checks.hasPermissions(embed_links=True)
    @mood.sassy
    async def skin(
        self, interaction: discord.Interaction, player: str
    ) -> None:
        await interaction.response.defer()
        await interaction.followup.send(
            view=await self.fetchSkinPanel(player)
        )

    async def fetchSkinPanel(self, player: str) -> components.Panel:
        query = normaliseName(player)
        if query is None:
            return components.error(
                "That isn't a valid Minecraft username or UUID."
            )

        try:
            uuid = query if uuidPattern.match(query) else None
            if uuid is None:
                async with self.session.get(
                    mojangProfileUrl.format(query)
                ) as resp:
                    if resp.status in (204, 404):
                        return components.error(
                            "That Minecraft account does not exist."
                        )
                    resp.raise_for_status()
                    uuid = (await resp.json(content_type=None))["id"]

            async with self.session.get(
                sessionProfileUrl.format(uuid)
            ) as resp:
                if resp.status in (204, 404):
                    return components.error(
                        "That Minecraft account does not exist."
                    )
                resp.raise_for_status()
                profile = await resp.json(content_type=None)
        except aiohttp.ClientError, TimeoutError, ValueError, KeyError:
            return components.error(
                "Couldn't reach Mojang — try again in a moment."
            )

        return skinPanel(
            profile.get("name") or query, uuid, parseTextures(profile)
        )

    @app_commands.command(
        name="serverstatus",
        description="Check whether a Minecraft server is online",
    )
    @app_commands.describe(
        address="The server address, e.g. play.example.com:25565",
        edition="Java or Bedrock (defaults to Java)",
    )
    @checks.hasPermissions(embed_links=True)
    @mood.sassy
    async def serverstatus(
        self,
        interaction: discord.Interaction,
        address: str,
        edition: Edition = "java",
    ) -> None:
        await interaction.response.defer()
        await interaction.followup.send(
            view=await self.fetchStatusPanel(address, edition)
        )

    async def fetchStatusPanel(
        self, address: str, edition: Edition
    ) -> components.Panel:
        target = normaliseAddress(address)
        if target is None:
            return components.error("That isn't a valid server address.")

        path = "bedrock/3" if edition == "bedrock" else "3"
        url = f"{statusBase}/{path}/{urllib.parse.quote(target)}"
        try:
            async with self.session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except aiohttp.ClientError, TimeoutError, ValueError:
            return components.error(
                "Couldn't reach the status service — try again in a "
                "moment."
            )

        if not isinstance(data, dict):
            return components.error(
                "The status service sent back nonsense."
            )
        return statusPanel(data, target, edition)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Minecraft(bot))
