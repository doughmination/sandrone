import datetime as dt
import re
from urllib.parse import urlsplit

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from sandrone import doughchecks
from utils.markdown import escapeMarkdown

apiBase = "https://public.api.bsky.app/xrpc"
xskyBase = "https://xsky.app"
blueskyColor = discord.Color(0x1185FE)

allowedHosts = {
    "bsky.app",
    "www.bsky.app",
    "xsky.app",
    "www.xsky.app",
    "fxbsky.app",
    "www.fxbsky.app",
    "bskyx.app",
    "bskx.app",
    "psky.app",
    "cbsky.app",
}
postPattern = re.compile(r"/profile/([^/]+)/post/([A-Za-z0-9]+)")


def extractPostRef(url: str) -> tuple[str, str] | None:
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = f"https://{url}"

    parsed = urlsplit(url)
    if parsed.netloc.lower() not in allowedHosts:
        return None

    match = postPattern.search(parsed.path)
    return (match.group(1), match.group(2)) if match else None


def errorEmbed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        color=discord.Color.red(), title=title, description=description
    )


def mediaEmbed(embed: dict) -> dict:
    if embed.get("$type") == "app.bsky.embed.recordWithMedia#view":
        return embed.get("media") or {}
    return embed


def quotedRecord(embed: dict) -> dict | None:
    etype = embed.get("$type")
    if etype == "app.bsky.embed.record#view":
        record = embed.get("record") or {}
    elif etype == "app.bsky.embed.recordWithMedia#view":
        record = (embed.get("record") or {}).get("record") or {}
    else:
        return None

    return record if record.get("$type") == "app.bsky.embed.record#viewRecord" else None


def firstMediaThumb(embed: dict) -> tuple[str | None, bool]:
    etype = embed.get("$type")
    if etype in ("app.bsky.embed.images#view", "app.bsky.embed.gallery#view"):
        items = embed.get("images") or embed.get("items") or []
        if items:
            return items[0]["fullsize"], False
    elif etype == "app.bsky.embed.video#view" and embed.get("thumbnail"):
        return embed["thumbnail"], True
    return None, False


class Bluesky(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        await self.session.close()

    @app_commands.command(
        name="bluesky", description="Embed a Bluesky post via xsky.app"
    )
    @app_commands.describe(url="A bsky.app or xsky.app post link")
    @doughchecks.has_permissions(embed_links=True)
    async def blueskySlash(self, interaction: discord.Interaction, url: str) -> None:
        await interaction.response.defer()

        ref = extractPostRef(url)
        if ref is None:
            await interaction.followup.send(
                embed=errorEmbed(
                    "❌ Invalid link",
                    "That doesn't look like a `bsky.app` or `xsky.app` post link.",
                )
            )
            return

        actor, rkey = ref
        embed, linkUrl = await self.fetchPostEmbed(actor, rkey)
        await interaction.followup.send(embed=embed)
        if linkUrl:
            await interaction.followup.send(content=linkUrl)

    async def fetchPostEmbed(
        self, actor: str, rkey: str
    ) -> tuple[discord.Embed, str | None]:
        atUri = f"at://{actor}/app.bsky.feed.post/{rkey}"
        try:
            async with self.session.get(
                f"{apiBase}/app.bsky.feed.getPostThread",
                params={"uri": atUri, "depth": "0"},
            ) as resp:
                status = resp.status
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return (
                errorEmbed(
                    "❌ Error", "Couldn't reach Bluesky — try again in a moment."
                ),
                None,
            )

        if not isinstance(body, dict):
            return errorEmbed(
                "❌ Error", "Bluesky sent back something unexpected."
            ), None

        if status != 200:
            error = body.get("error", "")
            if error in ("NotFound", "InvalidRequest"):
                return (
                    errorEmbed(
                        "❓ Post not found",
                        "That post doesn't exist, was deleted, or the handle is wrong.",
                    ),
                    None,
                )
            return (
                errorEmbed("❌ Error", f"Bluesky returned an error: {error or status}"),
                None,
            )

        thread = body.get("thread") or {}
        threadType = thread.get("$type")
        if threadType == "app.bsky.feed.defs#notFoundPost":
            return (
                errorEmbed(
                    "❓ Post not found", "That post doesn't exist or was deleted."
                ),
                None,
            )
        if threadType == "app.bsky.feed.defs#blockedPost":
            return (
                errorEmbed(
                    "🚫 Blocked",
                    "That post is from an account that's blocked or blocking.",
                ),
                None,
            )
        if not thread.get("post"):
            return errorEmbed("❓ Post not found", "Couldn't read that post."), None

        return self.buildPostEmbed(thread["post"], actor, rkey)

    def buildPostEmbed(
        self, post: dict, actor: str, rkey: str
    ) -> tuple[discord.Embed, str | None]:
        author = post.get("author") or {}
        record = post.get("record") or {}
        handle = author.get("handle") or actor
        postUrl = f"{xskyBase}/profile/{handle}/post/{rkey}"

        embed = discord.Embed(color=blueskyColor, url=postUrl)
        embed.set_author(
            name=f"{escapeMarkdown(author.get('displayName') or handle)} (@{handle})",
            url=f"https://bsky.app/profile/{handle}",
            icon_url=author.get("avatar") or None,
        )

        created = record.get("createdAt")
        if created:
            try:
                embed.timestamp = dt.datetime.fromisoformat(created)
            except ValueError:
                pass

        parts = []
        if record.get("text"):
            parts.append(escapeMarkdown(record["text"]))

        embedData = post.get("embed") or {}
        media = mediaEmbed(embedData)
        mediaType = media.get("$type")
        extra = 0
        isVideo = False

        if mediaType in ("app.bsky.embed.images#view", "app.bsky.embed.gallery#view"):
            images = media.get("images") or media.get("items") or []
            if images:
                embed.set_image(url=images[0]["fullsize"])
            extra = len(images) - 1
        elif mediaType == "app.bsky.embed.video#view":
            if media.get("thumbnail"):
                embed.set_image(url=media["thumbnail"])
            isVideo = True
        elif mediaType == "app.bsky.embed.external#view":
            external = media.get("external") or {}
            if external.get("thumb"):
                embed.set_thumbnail(url=external["thumb"])
            card = "\n".join(
                line
                for line in (
                    escapeMarkdown(external.get("title") or ""),
                    escapeMarkdown(external.get("description") or ""),
                )
                if line
            )
            if card:
                parts.append(f"🔗 {card}")

        quoted = quotedRecord(embedData)
        if quoted:
            qAuthor = quoted.get("author") or {}
            qHandle = qAuthor.get("handle") or "unknown"
            qName = escapeMarkdown(qAuthor.get("displayName") or qHandle)
            qText = escapeMarkdown((quoted.get("value") or {}).get("text") or "")
            heading = f"📝 Quoting {qName} (@{qHandle})"
            parts.append(f"{heading}:\n{qText}" if qText else heading)

            if not embed.image.url:
                for quotedEmbed in quoted.get("embeds") or []:
                    thumb, quotedIsVideo = firstMediaThumb(quotedEmbed)
                    if thumb:
                        embed.set_image(url=thumb)
                        isVideo = isVideo or quotedIsVideo
                        break

        description = "\n\n".join(parts)
        embed.description = description[:4096] or None

        stats = []
        for emoji, key in (
            ("❤️", "likeCount"),
            ("🔁", "repostCount"),
            ("💬", "replyCount"),
            ("📝", "quoteCount"),
        ):
            value = post.get(key)
            if value is not None:
                stats.append(f"{emoji} {value:,}")
        if extra > 0:
            stats.append(f"📎 +{extra} more")
        if isVideo:
            stats.append("🎥 Video")

        embed.set_footer(
            text="  ".join(stats) if stats else "xsky.app",
            icon_url="https://m.doughmination.gay/img/icons/bluesky.png",
        )

        return embed, postUrl if isVideo else None


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Bluesky(bot))
