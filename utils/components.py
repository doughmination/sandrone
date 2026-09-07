"""Helpers for building Components V2 replies.

A :class:`Panel` is a :class:`discord.ui.LayoutView` wrapping a single
``Container``. Send it with ``view=`` (never alongside ``embed=`` or
``content=`` — Components V2 messages carry neither).
"""

import discord
from discord import ui

FUCHSIA = discord.Color.fuchsia()
RED = discord.Color.red()

type Field = tuple[str, str]


class Panel(ui.LayoutView):
    """A LayoutView holding one accent-barred container."""

    def __init__(self, box: ui.Container) -> None:
        super().__init__(timeout=None)
        self.add_item(box)


def heading(title: str, url: str | None = None) -> str:
    return f"## [{title}]({url})" if url else f"## {title}"


def renderFields(fields: list[Field]) -> str:
    return "\n\n".join(f"**{name}**\n{value}" for name, value in fields)


def container(
    *,
    title: str | None = None,
    url: str | None = None,
    body: str | None = None,
    fields: list[Field] | None = None,
    thumbnail: str | None = None,
    images: list[str] | None = None,
    files: list[str] | None = None,
    footer: str | None = None,
    color: discord.Color | int | None = FUCHSIA,
) -> ui.Container:
    """Build a Container from embed-shaped pieces, laid out the V2 way.

    ``images`` take URLs or ``attachment://name`` refs; ``files`` take
    ``attachment://name`` refs and render as downloadable file components.
    A V2 message hides any uploaded attachment it does not reference.
    """
    lead = [part for part in (heading(title, url) if title else None, body) if part]
    leadText = "\n\n".join(lead)

    blocks: list[ui.Item] = []

    if thumbnail:
        # A Section needs at least one text child.
        blocks.append(
            ui.Section(
                ui.TextDisplay(leadText or "\u200b"),
                accessory=ui.Thumbnail(thumbnail),
            )
        )
    elif leadText:
        blocks.append(ui.TextDisplay(leadText))

    if fields:
        blocks.append(ui.TextDisplay(renderFields(fields)))

    if images:
        blocks.append(
            ui.MediaGallery(*(discord.MediaGalleryItem(url) for url in images))
        )

    for ref in files or []:
        blocks.append(ui.File(ref))

    if footer:
        blocks.append(ui.Separator(visible=False))
        blocks.append(ui.TextDisplay(f"-# {footer}"))

    if not blocks:
        blocks.append(ui.TextDisplay("\u200b"))

    return ui.Container(*blocks, accent_colour=color)


def panel(
    *,
    title: str | None = None,
    url: str | None = None,
    body: str | None = None,
    fields: list[Field] | None = None,
    thumbnail: str | None = None,
    images: list[str] | None = None,
    files: list[str] | None = None,
    footer: str | None = None,
    color: discord.Color | int | None = FUCHSIA,
) -> Panel:
    return Panel(
        container(
            title=title,
            url=url,
            body=body,
            fields=fields,
            thumbnail=thumbnail,
            images=images,
            files=files,
            footer=footer,
            color=color,
        )
    )


def error(message: str) -> Panel:
    return panel(body=f":x: {message}", color=RED)
