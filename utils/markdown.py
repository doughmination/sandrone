import re

from discord.utils import escape_markdown

_orderedListPrefix = re.compile(r"^(\s*\d+)(?=\.\s)", re.MULTILINE)


def escapeMarkdown(text: str) -> str:
    """Escape every Discord markdown construct so quoted text renders verbatim.

    ``discord.utils.escape_markdown`` already covers the inline markers
    (``* _ ` ~ |``), masked links, line-leading blockquotes (``>``), headings
    (``#``) and unordered lists (``-``); it misses ordered lists, so escape
    those here too.

    Used for text that originates outside the bot (tweets, Bluesky posts, link
    cards) and is dropped into an embed description, where stray ``**`` or ``[]``
    would otherwise be rendered as formatting.
    """
    return _orderedListPrefix.sub(r"\1\\", escape_markdown(text))
