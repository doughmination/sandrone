import asyncio
import io
import shutil
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

import discord
from discord import app_commands
from discord.ext import commands
from yt_dlp import YoutubeDL
from yt_dlp.utils import YoutubeDLError

from sandrone import config
from utils import downloads

opts = {
    "Audio": "mp3",
    "Video": "mp4",
}

containerSuffixes = {
    "mp3": {".mp3"},
    "mp4": {".mp4", ".m4v", ".mov"},
}

youtubeHosts = {
    "youtube.com",
    "youtu.be",
    "music.youtube.com",
}

defaultUploadLimit = 10 * 1024 * 1024

mib = 1024 * 1024

maxHeight = 1080


class DownloadTooLarge(RuntimeError):
    pass


class Result(NamedTuple):
    path: Path
    title: str
    height: int | None


def ffmpegLocation() -> str | None:
    if shutil.which("ffmpeg"):
        return None
    try:
        import imageio_ffmpeg
    except ImportError:
        return None
    return str(Path(imageio_ffmpeg.get_ffmpeg_exe()).parent)


def firstLine(error: Exception) -> str:
    lines = str(error).strip().splitlines()
    line = lines[0] if lines else error.__class__.__name__
    return line.removeprefix("ERROR: ").strip()[:300]


def videoFormats() -> str:
    """Best video up to maxHeight, preferring the pair that needs no transcode.

    Anything too big to attach gets hosted instead, so the only ceiling here is
    resolution — mp4/m4a first so the merge is a straight remux, and h264/aac
    via format_sort so browsers and the Discord player both handle the result.
    """
    return "/".join(
        (
            f"bestvideo[height<={maxHeight}][ext=mp4]+bestaudio[ext=m4a]",
            f"bestvideo[height<={maxHeight}]+bestaudio",
            f"best[height<={maxHeight}][ext=mp4]",
            f"best[height<={maxHeight}]",
            "best[ext=mp4]",
            "best",
        )
    )


def buildOptions(container: str, outDir: Path) -> dict:
    options: dict = {
        "outtmpl": str(outDir / "%(title).150B [%(id)s].%(ext)s"),
        "noplaylist": True,
        "restrictfilenames": True,
        "max_filesize": config.downloadsMaxSize,
        "retries": 3,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }

    location = ffmpegLocation()
    if location:
        options["ffmpeg_location"] = location

    if container == "mp3":
        options["format"] = "bestaudio/best"
        options["writethumbnail"] = True
        options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            },
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail", "already_have_thumbnail": False},
        ]
    else:
        options["format"] = videoFormats()
        options["format_sort"] = ["vcodec:h264", "acodec:aac"]
        options["merge_output_format"] = "mp4"
        options["final_ext"] = "mp4"
        options["postprocessors"] = [
            {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}
        ]

    return options


def formatParts(entry: dict) -> list[dict]:
    return entry.get("requested_formats") or [entry]


def mergeFragments(requested: list[dict]) -> set[Path]:
    """Paths of the separate video/audio streams that feed a merge."""
    return {
        Path(part["filepath"])
        for entry in requested
        for part in (entry.get("requested_formats") or [])
        if part.get("filepath")
    }


def pickFile(requested: list[dict], container: str, outDir: Path) -> Path | None:
    """The finished download, or None if only the wrong kind of file landed.

    Only files matching the requested container count. Without that check a
    video whose picture stream got skipped falls through to its leftover .m4a
    audio, which Discord renders as a voice note.
    """
    wanted = containerSuffixes[container]

    for entry in requested:
        filepath = entry.get("filepath")
        if not filepath:
            continue
        path = Path(filepath)
        if path.is_file() and path.suffix.lower() in wanted:
            return path

    fragments = mergeFragments(requested)
    leftovers = [
        p
        for p in outDir.iterdir()
        if p.is_file() and p.suffix.lower() in wanted and p not in fragments
    ]
    return max(leftovers, key=lambda p: p.stat().st_size) if leftovers else None


def expectedSize(requested: list[dict]) -> int | None:
    sizes = [
        total
        for entry in requested
        if (
            total := sum(
                part.get("filesize") or part.get("filesize_approx") or 0
                for part in formatParts(entry)
            )
        )
    ]
    return max(sizes) if sizes else None


def download(url: str, container: str, outDir: Path) -> Result:
    with YoutubeDL(buildOptions(container, outDir)) as ydl:
        info = ydl.extract_info(url, download=True)

    if info.get("entries"):
        info = info["entries"][0]
    title = info.get("title") or "download"

    requested = info.get("requested_downloads") or []
    path = pickFile(requested, container, outDir)
    if path:
        return Result(path, title, info.get("height"))

    approx = expectedSize(requested)
    raise DownloadTooLarge(f"~{approx / mib:.1f} MiB" if approx else "too large")


class YtDlp(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="yt-dlp", description="Get a YouTube video as a file or audio"
    )
    @app_commands.describe(
        url="YouTube URL", type="Audio or Video? (defaults to Video)"
    )
    @app_commands.choices(
        type=[
            app_commands.Choice(name=name, value=value) for name, value in opts.items()
        ]
    )
    async def ytDlpSlash(
        self,
        interaction: discord.Interaction,
        url: str,
        type: app_commands.Choice[str] | None = None,
    ) -> None:
        await interaction.response.defer()
        container = type.value if type else "mp4"
        uploadLimit = (
            interaction.guild.filesize_limit
            if interaction.guild
            else defaultUploadLimit
        )
        content, file = await self.getVideoOrAudio(url, container, uploadLimit)
        await interaction.followup.send(content, file=file or discord.utils.MISSING)

    async def getVideoOrAudio(
        self, url: str, container: str, uploadLimit: int
    ) -> tuple[str, discord.File | None]:
        parsed = urlsplit(url if "://" in url else f"https://{url}")
        host = parsed.netloc.lower().removeprefix("www.")
        if parsed.scheme not in ("http", "https") or not host:
            return "❌ That doesn't look like a URL.", None
        if host not in youtubeHosts:
            return "❌ Only YouTube links are supported.", None

        slot = downloads.newSlot()
        keep = False
        try:
            result = await asyncio.to_thread(download, url, container, slot)
            size = result.path.stat().st_size

            # Small enough to attach, so Discord can play it inline.
            if size <= uploadLimit:
                data = await asyncio.to_thread(result.path.read_bytes)
                return (
                    f"🎬 **{result.title}**",
                    discord.File(io.BytesIO(data), filename=result.path.name),
                )

            keep = True
            details = " · ".join(
                part
                for part in (
                    f"{result.height}p" if result.height else "",
                    f"{size / mib:.1f} MiB",
                    f"expires in {config.downloadsRetention}h",
                )
                if part
            )
            link = downloads.publicUrl(slot, result.path.name)
            return f"🎬 **{result.title}**\n{details}\n{link}", None
        except DownloadTooLarge as error:
            return (
                (
                    f"❌ That one's {error}, over the "
                    f"{config.downloadsMaxSize // mib} MiB download cap. "
                    "Try the Audio option?"
                ),
                None,
            )
        except YoutubeDLError as error:
            line = firstLine(error)
            missing = "requested format is not available" in line.lower()
            if container == "mp4" and missing:
                return "❌ That link has no video stream. Try the Audio option?", None
            return f"❌ yt-dlp couldn't fetch that: `{line}`", None
        except (OSError, RuntimeError) as error:
            return f"❌ Something went wrong handling that download: `{error}`", None
        finally:
            if not keep:
                downloads.discard(slot)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(YtDlp(bot))
