"""Prefix resolution for text commands.

Sandrone answers to a mention or to her Harbinger name, case-insensitively:

    @Sandrone bsky <link>
    Marrionette ytdlp <link>
    marionette, help

The name has to be followed by whitespace or light punctuation, so ordinary
sentences that merely start with the word ("Marionette strings are fiddly")
don't get parsed as commands.
"""

import discord
from discord.ext import commands

from sandrone import config

# Characters allowed between the name and the command word. Whatever is matched
# is folded into the returned prefix so discord.py strips it for us.
SEPARATORS = " \t\n,:;"


def matchName(content: str) -> str | None:
    """The literal prefix slice of ``content``, or ``None`` if no name matched.

    The slice is returned verbatim (not lowercased) because discord.py compares
    prefixes against the raw message content, case-sensitively.
    """
    lowered = content.lower()
    for name in config.prefixNames:
        if not lowered.startswith(name):
            continue

        rest = content[len(name) :]
        if not rest:
            return None  # Just her name, no command behind it.

        stripped = rest.lstrip(SEPARATORS)
        if stripped == rest:
            continue  # "Marionettes", not "Marionette ..." — keep looking.
        if not stripped:
            return None  # Name plus trailing punctuation, still no command.

        return content[: len(content) - len(stripped)]
    return None


def resolvePrefix(bot: commands.Bot, message: discord.Message) -> list[str]:
    prefixes = commands.when_mentioned(bot, message)
    matched = matchName(message.content)
    if matched is not None:
        prefixes.append(matched)
    return prefixes
