import asyncio
import io
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import discord
from discord import app_commands
from discord.ext import commands
from yt_dlp import YoutubeDL
from yt_dlp.utils import YoutubeDLError

opts = {
    "Audio": "mp3",
    "Video": "mp4",
}

youtubeHosts = {
    "youtube.com",
    "youtu.be",
    "music.youtube.com",
}

defaultUploadLimit = 10 * 1024 * 1024

mib = 1024 * 1024


class DownloadTooLarge(RuntimeError):
    pass


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


def buildOptions(container: str, outDir: Path, sizeLimit: int) -> dict:
    options: dict = {
        "outtmpl": str(outDir / "%(title).150B [%(id)s].%(ext)s"),
        "noplaylist": True,
        "restrictfilenames": True,
        "max_filesize": sizeLimit,
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
        options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        options["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        options["merge_output_format"] = "mp4"

    return options


def download(
    url: str, container: str, outDir: Path, sizeLimit: int
) -> tuple[Path, str]:
    with YoutubeDL(buildOptions(container, outDir, sizeLimit)) as ydl:
        info = ydl.extract_info(url, download=True)

    if info.get("entries"):
        info = info["entries"][0]
    title = info.get("title") or "download"

    requested = info.get("requested_downloads") or []
    for entry in requested:
        filepath = entry.get("filepath")
        if filepath and Path(filepath).is_file():
            return Path(filepath), title

    leftovers = [
        p
        for p in outDir.iterdir()
        if p.is_file() and p.suffix not in (".part", ".ytdl")
    ]
    if leftovers:
        return max(leftovers, key=lambda p: p.stat().st_size), title

    approx = next(
        (e["filesize_approx"] for e in requested if e.get("filesize_approx")), None
    )
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
        sizeLimit = (
            interaction.guild.filesize_limit
            if interaction.guild
            else defaultUploadLimit
        )
        content, file = await self.getVideoOrAudio(url, container, sizeLimit)
        await interaction.followup.send(content, file=file or discord.utils.MISSING)

    async def getVideoOrAudio(
        self, url: str, container: str, sizeLimit: int
    ) -> tuple[str, discord.File | None]:
        parsed = urlsplit(url if "://" in url else f"https://{url}")
        host = parsed.netloc.lower().removeprefix("www.")
        if parsed.scheme not in ("http", "https") or not host:
            return "❌ That doesn't look like a URL.", None
        if host not in youtubeHosts:
            return "❌ Only YouTube links are supported.", None

        try:
            with TemporaryDirectory(prefix="ytdlp-") as tmp:
                path, title = await asyncio.to_thread(
                    download, url, container, Path(tmp), sizeLimit
                )
                size = path.stat().st_size
                if size > sizeLimit:
                    return (
                        (
                            f"❌ **{title}** came out to {size / mib:.1f} MiB, over "
                            f"the {sizeLimit // mib} MiB upload limit here. "
                            "Try the Audio option?"
                        ),
                        None,
                    )
                data = await asyncio.to_thread(path.read_bytes)
                filename = path.name
        except DownloadTooLarge as error:
            return (
                (
                    f"❌ That one's {error}, over the {sizeLimit // mib} MiB upload "
                    "limit here. Try the Audio option?"
                ),
                None,
            )
        except YoutubeDLError as error:
            return f"❌ yt-dlp couldn't fetch that: `{firstLine(error)}`", None
        except (OSError, RuntimeError) as error:
            return f"❌ Something went wrong handling that download: `{error}`", None

        return f"🎬 **{title}**", discord.File(io.BytesIO(data), filename=filename)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(YtDlp(bot))
