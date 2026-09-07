import re
from urllib.parse import urlsplit

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from sandrone import doughchecks
from utils import components
from utils.markdown import escapeMarkdown

apiBase = "https://api.girlcockx.com"

allowedHosts = {
    "x.com",
    "www.x.com",
    "mobile.x.com",
    "twitter.com",
    "www.twitter.com",
    "mobile.twitter.com",
}
statusPattern = re.compile(r"/status/(\d+)")

mentionPattern = re.compile(r"(?<![\w@/])@(\w{1,15})\b")


def linkifyMentions(text: str) -> str:
    parts: list[str] = []
    lastEnd = 0
    for match in mentionPattern.finditer(text):
        parts.append(escapeMarkdown(text[lastEnd : match.start()]))
        handle = match.group(1)
        parts.append(f"[@{handle}](https://twitter.com/{handle})")
        lastEnd = match.end()
    parts.append(escapeMarkdown(text[lastEnd:]))
    return "".join(parts)


def extractStatusId(url: str) -> str | None:
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = f"https://{url}"

    parsed = urlsplit(url)
    if parsed.netloc.lower() not in allowedHosts:
        return None

    match = statusPattern.search(parsed.path)
    return match.group(1) if match else None


def errorPanel(title: str, description: str) -> components.Panel:
    return components.panel(title=title, body=description, color=components.RED)


def formatDuration(seconds: float) -> str:
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}"


def bestVideoUrl(video: dict) -> str | None:
    mp4Variants = [
        v for v in (video.get("variants") or []) if v.get("content_type") == "video/mp4"
    ]
    if not mp4Variants:
        return video.get("url")
    return max(mp4Variants, key=lambda v: v.get("bitrate", 0))["url"]


class Twitter(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        await self.session.close()

    @app_commands.command(
        name="tweet", description="Embed an X/Twitter post via girlcockx.com"
    )
    @app_commands.describe(url="A twitter.com or x.com post link")
    @doughchecks.has_permissions(embed_links=True)
    async def tweetSlash(self, interaction: discord.Interaction, url: str) -> None:
        await interaction.response.defer()

        statusId = extractStatusId(url)
        if statusId is None:
            await interaction.followup.send(
                view=errorPanel(
                    "❌ Invalid link",
                    "That doesn't look like a `twitter.com` or `x.com` post link.",
                )
            )
            return

        panel, videoUrl = await self.fetchTweetPanel(statusId)
        await interaction.followup.send(view=panel)
        if videoUrl:
            await interaction.followup.send(content=videoUrl)

    async def fetchTweetPanel(
        self, statusId: str
    ) -> tuple[components.Panel, str | None]:
        try:
            async with self.session.get(f"{apiBase}/status/{statusId}") as resp:
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError):
            return (
                errorPanel(
                    "❌ Error", "Couldn't reach girlcockx.com — try again in a moment."
                ),
                None,
            )

        tweet = body.get("tweet")
        if body.get("code") != 200 or tweet is None:
            message = body.get("message", "NOT_FOUND")
            description = (
                "That post doesn't exist, was deleted, or is private."
                if message in ("NOT_FOUND", "PRIVATE_TWEET", "SUSPENDED")
                else f"girlcockx.com returned an error: {message}"
            )
            return errorPanel("❓ Post not found", description), None

        return self.buildTweetPanel(tweet)

    def buildTweetPanel(self, tweet: dict) -> tuple[components.Panel, str | None]:
        author = tweet["author"]
        tweetUrl = tweet.get("url")

        text = tweet.get("text")
        body = linkifyMentions(text) if text else None

        media = tweet.get("media") or {}
        photos = media.get("photos") or []
        videos = media.get("videos") or []

        images = [p["url"] for p in photos[:10]]
        if not images and videos and videos[0].get("thumbnail_url"):
            images = [videos[0]["thumbnail_url"]]

        stats = []
        if tweet.get("likes") is not None:
            stats.append(f"❤️ {tweet['likes']:,}")
        if tweet.get("retweets") is not None:
            stats.append(f"🔁 {tweet['retweets']:,}")
        if tweet.get("replies") is not None:
            stats.append(f"💬 {tweet['replies']:,}")
        if tweet.get("views") is not None:
            stats.append(f"👁️ {tweet['views']:,}")

        hidden = len(photos) - len(images)
        if hidden > 0:
            stats.append(f"📎 +{hidden} more")

        videoUrl = None
        if videos:
            video = videos[0]
            stats.append(
                f"🎥 {formatDuration(video['duration'])}"
                if video.get("duration")
                else "🎥 Video"
            )
            videoUrl = bestVideoUrl(video)

        panel = components.panel(
            title=f"{escapeMarkdown(author['name'])} (@{author['screen_name']})",
            url=tweetUrl,
            body=body,
            images=images or None,
            footer="  ".join(stats) if stats else "girlcockx.com",
        )
        return panel, videoUrl


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Twitter(bot))
