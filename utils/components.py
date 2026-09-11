import re
from collections.abc import Sequence

import discord
from discord import ui
from discord.utils import escape_markdown

FUCHSIA = discord.Color.fuchsia()
RED = discord.Color.red()

type Field = tuple[str, str]
type Media = str | discord.MediaGalleryItem


def image(
    url: str, *, alt: str | None = None, spoiler: bool = False
) -> discord.MediaGalleryItem:
    return discord.MediaGalleryItem(url, description=alt, spoiler=spoiler)


class Panel(ui.LayoutView):
    def __init__(self, box: ui.Container) -> None:
        super().__init__(timeout=None)
        self.add_item(box)


def heading(title: str, url: str | None = None) -> str:
    return f"## [{title}]({url})" if url else f"## {title}"


def renderFields(fields: list[Field]) -> str:
    return "\n\n".join(f"**{name}**\n{value}" for name, value in fields)


def linkButton(label: str, url: str, emoji: str | None = None) -> ui.Button:
    return ui.Button(label=label, url=url, emoji=emoji, style=discord.ButtonStyle.link)


def container(
    *,
    title: str | None = None,
    url: str | None = None,
    body: str | None = None,
    fields: list[Field] | None = None,
    thumbnail: str | None = None,
    images: Sequence[Media] | None = None,
    files: list[str] | None = None,
    buttons: list[ui.Button] | None = None,
    footer: str | None = None,
    color: discord.Color | int | None = FUCHSIA,
) -> ui.Container:
    lead = [part for part in (heading(title, url) if title else None, body) if part]
    leadText = "\n\n".join(lead)

    blocks: list[ui.Item] = []

    if thumbnail:
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
            ui.MediaGallery(
                *(
                    item if isinstance(item, discord.MediaGalleryItem) else image(item)
                    for item in images[:10]
                )
            )
        )

    for ref in files or []:
        blocks.append(ui.File(ref))

    if buttons:
        row = ui.ActionRow()
        for btn in buttons:
            row.add_item(btn)
        blocks.append(row)

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
    images: Sequence[Media] | None = None,
    files: list[str] | None = None,
    buttons: list[ui.Button] | None = None,
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
            buttons=buttons,
            footer=footer,
            color=color,
        )
    )


def error(message: str) -> Panel:
    return panel(body=f":x: {message}", color=RED)


_orderedListPrefix = re.compile(r"^(\s*\d+)(?=\.\s)", re.MULTILINE)


def escapeMarkdown(text: str) -> str:
    return _orderedListPrefix.sub(r"\1\\", escape_markdown(text))


def codeBlock(text: str, language: str = "") -> str:
    return f"```{language}\n{text.replace('```', '`\u200b``')}\n```"


def caretAt(text: str, pos: int, window: int = 60) -> str:
    lineStart = text.rfind("\n", 0, pos) + 1
    lineEnd = text.find("\n", pos)
    if lineEnd == -1:
        lineEnd = len(text)

    line = text[lineStart:lineEnd]
    column = pos - lineStart
    start = max(0, column - window)
    end = min(len(line), column + window)

    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(line) else ""
    caret = " " * (len(prefix) + column - start) + "^"
    return f"{prefix}{line[start:end]}{suffix}\n{caret}"
