import datetime as dt
import re
from urllib.parse import urlsplit

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from sandrone import doughchecks

apiBase = "https://api.girlcockx.com"

allowedHosts = {"x.com", "www.x.com", "mobile.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}
statusPattern = re.compile(r"/status/(\d+)")


def extractStatusId(url: str) -> str | None:
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = f"https://{url}"

    parsed = urlsplit(url)
    if parsed.netloc.lower() not in allowedHosts:
        return None

    match = statusPattern.search(parsed.path)
    return match.group(1) if match else None


def errorEmbed(title: str, description: str) -> discord.Embed:
    return discord.Embed(color=discord.Color.red(), title=title, description=description)


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
                embed=errorEmbed(
                    "❌ Invalid link",
                    "That doesn't look like a `twitter.com` or `x.com` post link.",
                )
            )
            return

        embed, videoUrl = await self.fetchTweetEmbed(statusId)
        await interaction.followup.send(embed=embed)
        if videoUrl:
            await interaction.followup.send(content=videoUrl)

    async def fetchTweetEmbed(self, statusId: str) -> tuple[discord.Embed, str | None]:
        try:
            async with self.session.get(f"{apiBase}/status/{statusId}") as resp:
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError):
            return (
                errorEmbed(
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
            return errorEmbed("❓ Post not found", description), None

        return self.buildTweetEmbed(tweet)

    def buildTweetEmbed(self, tweet: dict) -> tuple[discord.Embed, str | None]:
        author = tweet["author"]

        embed = discord.Embed(
            color=discord.Color.fuchsia(),
            description=tweet.get("text") or None,
            url=tweet.get("url"),
        )
        embed.set_author(
            name=f"{author['name']} (@{author['screen_name']})",
            url=author.get("url"),
            icon_url=author.get("avatar_url"),
        )

        if tweet.get("created_timestamp"):
            embed.timestamp = dt.datetime.fromtimestamp(
                tweet["created_timestamp"], tz=dt.UTC
            )

        media = tweet.get("media") or {}
        photos = media.get("photos") or []
        videos = media.get("videos") or []
        allMedia = media.get("all") or []

        if photos:
            embed.set_image(url=photos[0]["url"])
        elif videos and videos[0].get("thumbnail_url"):
            embed.set_image(url=videos[0]["thumbnail_url"])

        stats = []
        if tweet.get("likes") is not None:
            stats.append(f"❤️ {tweet['likes']:,}")
        if tweet.get("retweets") is not None:
            stats.append(f"🔁 {tweet['retweets']:,}")
        if tweet.get("replies") is not None:
            stats.append(f"💬 {tweet['replies']:,}")
        if tweet.get("views") is not None:
            stats.append(f"👁️ {tweet['views']:,}")

        extra = len(allMedia) - 1
        if extra > 0:
            stats.append(f"📎 +{extra} more")

        videoUrl = None
        if videos:
            video = videos[0]
            stats.append(
                f"🎥 {formatDuration(video['duration'])}"
                if video.get("duration")
                else "🎥 Video"
            )
            videoUrl = bestVideoUrl(video)

        embed.set_footer(text="  ".join(stats) if stats else "girlcockx.com", icon_url="https://abs.twimg.com/responsive-web/client-web/icon-svg.ea5ff4a45cd19faaa.svg")
        return embed, videoUrl


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Twitter(bot))
