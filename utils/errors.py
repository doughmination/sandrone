import hashlib
import re
import traceback
from pathlib import Path
from typing import Any

import aiohttp
import discord
from discord import app_commands
from discord.utils import utcnow
from jpml import JPError

from utils import cf, jp_storage

db = jp_storage.database("errors", version=1)

recentKey = "recent"
keepLimit = 50
textLimit = 400
traceLimit = 2400

# Crockford's alphabet: no I, L, O or U, so a code read aloud or retyped from a
# screenshot lands on the same entry.
refAlphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
refLength = 4

fallbackCode = "MALFUNCTION"
loneWorkCode = "PUPPET"

# What each code means, in the order they are tested. Discord's NotFound and
# Forbidden are HTTPExceptions, so the narrow ones have to come first.
codes: tuple[tuple[str, str, tuple[type[BaseException], ...]], ...] = (
    (
        "WORKSHOP",
        "She is not allowed to do that here — a permission is missing.",
        (
            app_commands.BotMissingPermissions,
            app_commands.MissingPermissions,
            discord.Forbidden,
        ),
    ),
    (
        "VANISHED",
        "What was asked for is not there — a user, channel, role or page.",
        (app_commands.TransformerError, discord.NotFound),
    ),
    (
        "OVERLOAD",
        "Too much, too fast — a cooldown or a rate limit.",
        (app_commands.CommandOnCooldown,),
    ),
    (
        "STRINGS",
        "Discord itself refused or dropped the connection.",
        (
            discord.DiscordServerError,
            discord.GatewayNotFound,
            discord.ConnectionClosed,
            discord.HTTPException,
        ),
    ),
    (
        "BLIZZARD",
        "Somewhere outside Discord did not answer — an API or the network.",
        (aiohttp.ClientError, TimeoutError, ConnectionError),
    ),
    (
        "FOUNDRY",
        "Storage went wrong — a file, a path, or the .jp databases.",
        (JPError, OSError),
    ),
    (
        "BLUEPRINT",
        "The data was the wrong shape — bad JSON, a missing key, a bad value.",
        (ValueError, KeyError, TypeError, AttributeError, IndexError),
    ),
)

codeMeanings: dict[str, str] = {
    **{name: meaning for name, meaning, _ in codes},
    loneWorkCode: "The puppet broke on its own, away from any command.",
    fallbackCode: "Nothing she recognises. Read the traceback.",
}

type Entry = dict[str, Any]

_numbers = re.compile(r"\d{2,}")


def label(target: Any) -> str:
    if target is None:
        return "—"
    name = getattr(target, "name", None) or str(target)
    targetId = getattr(target, "id", None)
    return f"{name} ({targetId})" if targetId else str(name)


def traceOf(error: BaseException) -> str:
    if error.__traceback__ is None:
        return ""
    return "".join(traceback.format_exception(error)).strip()[-traceLimit:]


def missingOf(error: BaseException) -> list[str]:
    missing = getattr(error, "missing_permissions", None)
    return [str(perm) for perm in missing] if missing else []


def frameOf(error: BaseException) -> str:
    frames = traceback.extract_tb(error.__traceback__)
    if not frames:
        return ""
    last = frames[-1]
    return f"{Path(last.filename).name}:{last.lineno}"


def codeOf(error: BaseException, source: str = "") -> str:
    """Which of Sandrone's codes *error* falls under."""
    for name, _, kinds in codes:
        if isinstance(error, kinds):
            return name
    return fallbackCode if source.endswith("command") else loneWorkCode


def digestOf(error: BaseException, command: str | None = None) -> str:
    """The part of a code that tells two faults apart.

    Built from the kind, the command and where it was raised, with ids and
    other long numbers blanked out — so the same fault reported by three
    different people in three different servers comes back as one code.
    """
    seed = "|".join(
        (
            type(error).__name__,
            command or "",
            _numbers.sub("#", str(error)),
            frameOf(error),
        )
    )
    value = int.from_bytes(
        hashlib.blake2b(seed.encode("utf-8"), digest_size=8).digest(), "big"
    )

    characters = []
    for _ in range(refLength):
        value, index = divmod(value, len(refAlphabet))
        characters.append(refAlphabet[index])
    return "".join(reversed(characters))


def reference(
    error: BaseException, command: str | None = None, source: str = ""
) -> str:
    """The code a person quotes back, e.g. `WORKSHOP-4F2K`."""
    return f"{codeOf(error, source)}-{digestOf(error, command)}"


# -- reads ---------------------------------------------------------------


def entries() -> list[Entry]:
    return [entry for entry in db.key(recentKey).list() if isinstance(entry, dict)]


def recent(limit: int = 10) -> list[Entry]:
    return entries()[:limit]


def count() -> int:
    return len(entries())


def tidyRef(ref: str) -> str:
    """Take a code as a person types it: `workshop-4f2k`, #WORKSHOP–4F2K, spaced."""
    cleaned = ref.strip().strip("`").lstrip("#").upper()
    cleaned = re.sub(r"[\s_–—]+", "-", cleaned)
    return re.sub(r"-+", "-", cleaned).strip("-")


def find(ref: str) -> Entry | None:
    wanted = tidyRef(ref)
    if not wanted:
        return None

    stored = entries()
    for entry in stored:
        if str(entry.get("ref", "")).upper() == wanted:
            return entry

    # Someone quoted only half of it — the digest alone, or just the code.
    for entry in stored:
        code, _, digest = str(entry.get("ref", "")).upper().partition("-")
        if wanted in (digest, code):
            return entry
    return None


def byCode(code: str) -> list[Entry]:
    wanted = tidyRef(code)
    return [
        entry for entry in entries() if str(entry.get("code", "")).upper() == wanted
    ]


def note(entry: Entry | None) -> str:
    """The line appended to whatever the person who hit the error is told."""
    if not entry or not entry.get("ref"):
        return ""
    return f"\n-# Fault `{entry['ref']}` — quote that if you report this."


# -- writes --------------------------------------------------------------


def clear() -> int:
    total = count()
    if total:
        db.key(recentKey).delete().save()
    return total


def record(
    error: BaseException,
    *,
    source: str,
    command: str | None = None,
    guild: Any = None,
    channel: Any = None,
    user: Any = None,
) -> Entry | None:
    """Log *error* under a short reference and return the entry.

    The same fault hitting twice keeps its reference and bumps `count` instead
    of filling the log with copies. Called from error handlers, so it swallows
    its own failures rather than replacing one error with another.
    """
    try:
        code = codeOf(error, source)
        ref = f"{code}-{digestOf(error, command)}"
        now = int(utcnow().timestamp())
        seen = find(ref)

        entry: Entry = {
            "ref": ref,
            "code": code,
            "when": now,
            "first": seen.get("first", now) if seen else now,
            "count": int(seen.get("count", 1)) + 1 if seen else 1,
            "source": source,
            "command": command or "—",
            "kind": type(error).__name__,
            "text": (str(error) or repr(error))[:textLimit],
            "guild": label(guild),
            "channel": label(channel),
            "user": label(user),
            "missing": missingOf(error),
            "trace": traceOf(error),
        }
        others = [other for other in entries() if other.get("ref") != ref]
        db.key(recentKey).write([entry, *others[: keepLimit - 1]]).save()
        return entry
    except (JPError, OSError, TypeError, ValueError) as e:
        print(cf.red(f"[errors] could not record {type(error).__name__}: {e}"))
        return None


def fromInteraction(
    interaction: discord.Interaction, error: BaseException
) -> Entry | None:
    return record(
        error,
        source="slash command",
        command=interaction.command.qualified_name if interaction.command else None,
        guild=interaction.guild,
        channel=interaction.channel,
        user=interaction.user,
    )
