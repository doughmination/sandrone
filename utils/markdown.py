import re

from discord.utils import escape_markdown

_orderedListPrefix = re.compile(r"^(\s*\d+)(?=\.\s)", re.MULTILINE)


def escapeMarkdown(text: str) -> str:
    return _orderedListPrefix.sub(r"\1\\", escape_markdown(text))
