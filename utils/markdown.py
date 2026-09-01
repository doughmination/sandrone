import re

from discord.utils import escape_markdown

_orderedListPrefix = re.compile(r"^(\s*\d+)(?=\.\s)", re.MULTILINE)


def escapeMarkdown(text: str) -> str:
    return _orderedListPrefix.sub(r"\1\\", escape_markdown(text))


def codeBlock(text: str, language: str = "") -> str:
    # A fence inside the payload would end the block early, so break it up.
    return f"```{language}\n{text.replace('```', '`\u200b``')}\n```"


def caretAt(text: str, pos: int, window: int = 60) -> str:
    """The line containing pos, windowed, with a caret under the offender."""
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
