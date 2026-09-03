import asyncio
import io

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, UnidentifiedImageError

from sandrone import doughchecks
from utils.pride import (
    PrideOptions,
    Rendered,
    flagAliases,
    flagColours,
    flagLabels,
    render,
    renderPng,
)

avatarSize = 512
defaultUploadLimit = 10 * 1024 * 1024
# Headroom for the embed and multipart framing around the file itself.
uploadOverhead = 64 * 1024

styles = {
    "Circle": "circle",
    "Square": "square",
    "Overlay": "overlay",
}


def resolveFlag(name: str | None) -> str | None:
    if not name:
        return None
    key = name.strip().lower()
    if key in flagColours:
        return key
    for slug, label in flagLabels.items():
        if label.lower() == key:
            return slug
    return None


class Pride(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def flagAutocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        query = current.strip().lower()
        return [
            app_commands.Choice(name=label, value=slug)
            for slug, label in flagLabels.items()
            if query in label.lower()
            or query in slug
            or any(query in alias for alias in flagAliases.get(slug, ()))
        ][:25]

    @app_commands.command(
        name="pride", description="Put a pride flag around someone's profile picture"
    )
    @app_commands.describe(
        user="Whose profile picture to use (defaults to you)",
        flag="The flag to use (defaults to the rainbow pride flag)",
        flag2="A second flag, drawn beside the first",
        style="Ring the picture, or paint the flag over it",
        size="How much of the picture stays visible, as a percent",
        opacity="How solid the flag is, as a percent",
        rotation="Turn the flag by this many degrees",
        gradient="Blend the stripes instead of hard edges",
        animated="Spin the flag, as a GIF",
    )
    @app_commands.autocomplete(flag=flagAutocomplete, flag2=flagAutocomplete)
    @app_commands.choices(
        style=[
            app_commands.Choice(name=name, value=value)
            for name, value in styles.items()
        ]
    )
    @doughchecks.has_permissions(embed_links=True, attach_files=True)
    async def prideSlash(
        self,
        interaction: discord.Interaction,
        user: discord.Member | discord.User | None = None,
        flag: str | None = None,
        flag2: str | None = None,
        style: app_commands.Choice[str] | None = None,
        size: app_commands.Range[int, 10, 100] = 90,
        opacity: app_commands.Range[int, 0, 100] = 100,
        rotation: app_commands.Range[int, 0, 360] = 0,
        gradient: bool = False,
        animated: bool = False,
    ) -> None:
        await interaction.response.defer()

        requested = [name for name in (flag or "pride", flag2) if name]
        chosen = [resolveFlag(name) for name in requested]
        unknown = [name for name, slug in zip(requested, chosen) if slug is None]
        if unknown:
            await interaction.followup.send(
                embed=self.errorEmbed(
                    f"I have no flag called `{'`, `'.join(unknown)}` — "
                    "pick one from the suggestions."
                )
            )
            return

        target = user or interaction.user
        options = PrideOptions(
            columns=tuple(flagColours[slug] for slug in chosen if slug is not None),
            cutout=style.value if style else "circle",
            cutoutSize=int(size),
            opacity=int(opacity),
            rotation=int(rotation),
            isGradient=gradient,
        )

        try:
            source = (
                await target.display_avatar.with_format("png")
                .with_size(avatarSize)
                .read()
            )
        except discord.HTTPException:
            await interaction.followup.send(
                embed=self.errorEmbed("Couldn't download that profile picture.")
            )
            return

        budget = self.uploadBudget(interaction)
        try:
            result = await asyncio.to_thread(
                self.draw, source, options, animated, budget
            )
        except (UnidentifiedImageError, OSError, ValueError) as error:
            await interaction.followup.send(
                embed=self.errorEmbed(f"Couldn't render that one: `{error}`")
            )
            return

        filename = f"pride.{result.extension}"
        embed = discord.Embed(
            color=discord.Color.fuchsia(),
            title=" + ".join(flagLabels[slug] for slug in chosen if slug is not None),
        )
        embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)
        embed.set_image(url=f"attachment://{filename}")
        if animated and result.extension == "png":
            embed.description = (
                "The animation wouldn't fit under the upload limit here, "
                "so here's a still instead."
            )
        embed.set_footer(text=self.footerText(result))

        await interaction.followup.send(
            embed=embed, file=discord.File(io.BytesIO(result.data), filename=filename)
        )

    def draw(
        self, source: bytes, options: PrideOptions, animated: bool, budget: int
    ) -> Rendered:
        with Image.open(io.BytesIO(source)) as opened:
            avatar = opened.convert("RGBA")
        if animated:
            return render(avatar, options, budget)
        return renderPng(avatar, options)

    def uploadBudget(self, interaction: discord.Interaction) -> int:
        limit = (
            interaction.guild.filesize_limit
            if interaction.guild
            else defaultUploadLimit
        )
        return max(limit - uploadOverhead, uploadOverhead)

    def footerText(self, result: Rendered) -> str:
        parts = [f"{result.size}px"]
        if result.frames > 1:
            parts.append(f"{result.frames} frames")
        parts.append(f"{len(result.data) / 1024:.0f} KiB")
        parts.append("Sandrone")
        return " · ".join(parts)

    def errorEmbed(self, message: str) -> discord.Embed:
        return discord.Embed(color=discord.Color.red(), description=f":x: {message}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Pride(bot))
