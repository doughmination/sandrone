import os
import platform
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import format_dt, utcnow

from commands.admin import ownerOnly
from sandrone import checks, config
from utils import components, errors, jp_storage

# What the bot wants everywhere, on top of whatever individual commands ask for.
basePermissions: dict[str, bool] = {
    "view_channel": True,
    "send_messages": True,
    "send_messages_in_threads": True,
    "embed_links": True,
    "attach_files": True,
    "read_message_history": True,
    "use_external_emojis": True,
}

traceDisplayLimit = 1500
listLimit = 10


def prettyPermission(name: str) -> str:
    return name.replace("_", " ").replace("guild", "server").title()


def loadedCommands(bot: commands.Bot) -> list[app_commands.Command]:
    """Every app command the tree holds, groups flattened out."""
    found: list[app_commands.Command] = []

    def walk(items) -> None:
        for item in items:
            if isinstance(item, app_commands.Group):
                walk(item.commands)
            elif isinstance(item, app_commands.Command):
                found.append(item)

    walk(bot.tree.get_commands())
    return found


def commandRequirements(bot: commands.Bot) -> dict[str, list[str]]:
    """Which loaded commands asked for which bot permission."""
    needed: dict[str, list[str]] = {}
    for command in loadedCommands(bot):
        for perm, value in checks.requiredPermissions(command).items():
            if value:
                needed.setdefault(perm, []).append(command.qualified_name)
    return {perm: sorted(names) for perm, names in needed.items()}


def since(moment: datetime | None) -> str:
    if moment is None:
        return "unknown"
    seconds = int((utcnow() - moment).total_seconds())
    minutes, _ = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    parts = [f"{days}d", f"{hours}h", f"{minutes}m"]
    return " ".join(parts[1:] if days == 0 else parts)


def times(entry: dict) -> str:
    seen = int(entry.get("count", 1) or 1)
    return f" · ×{seen}" if seen > 1 else ""


def summarise(entry: dict) -> str:
    when = entry.get("when")
    stamp = f"<t:{when}:R>" if isinstance(when, int) else "some time ago"
    missing = entry.get("missing") or []
    tail = f" · missing {', '.join(f'`{perm}`' for perm in missing)}" if missing else ""
    return (
        f"`{entry.get('ref', '?')}` — `{entry.get('kind', '?')}` in "
        f"`{entry.get('command', '—')}` — {stamp}{times(entry)}{tail}\n"
        f"-# {entry.get('source', '?')} · {entry.get('guild', '—')} · "
        f"{entry.get('channel', '—')}\n"
        f"{components.escapeMarkdown(str(entry.get('text', ''))[:160])}"
    )


class Debug(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    debug = app_commands.Group(
        name="debug",
        description="(owner) Look inside the bot",
        default_permissions=discord.Permissions(administrator=True),
    )

    @debug.command(name="info", description="(owner) Runtime, cogs and storage state")
    @ownerOnly()
    async def info(self, interaction: discord.Interaction) -> None:
        bot = self.bot
        started = getattr(bot, "startedAt", None)

        runtime = [
            f"Version `{config.version}` · dev mode `{config.devMode}`",
            f"Python `{platform.python_version()}` · discord.py `{discord.__version__}`",
            f"{platform.system()} `{platform.release()}` · PID `{os.getpid()}`",
        ]

        connection = [
            f"Latency `{round(bot.latency * 1000)}ms`",
            f"Up `{since(started)}`"
            + (f" (since {format_dt(started, 'f')})" if started else ""),
            f"{len(bot.guilds)} servers · {len(bot.users)} cached users",
        ]

        cogs = [
            f"{len(bot.extensions)} extensions · {len(bot.cogs)} cogs",
            (
                f"{len(loadedCommands(bot))} slash commands · "
                f"{len(bot.tree.get_commands())} at top level"
            ),
        ]
        disabled = sorted(config.loadDisabled())
        if disabled:
            cogs.append("Disabled: " + ", ".join(f"`{name}`" for name in disabled))

        storage = []
        for db in sorted(jp_storage.databases(), key=lambda entry: entry.name):
            size = db.path.stat().st_size if db.path.exists() else 0
            state = "unsaved changes" if db.dirty else "clean"
            storage.append(
                f"`{db.name}.jp` — {len(db.sections())} sections · {size}B · {state}"
            )

        await interaction.response.send_message(
            view=components.panel(
                title="Debug · info",
                fields=[
                    ("Runtime", "\n".join(runtime)),
                    ("Connection", "\n".join(connection)),
                    ("Loaded", "\n".join(cogs)),
                    ("Storage", "\n".join(storage) or "No databases opened yet."),
                    (
                        "Errors",
                        f"{errors.count()} logged · `debug errors` to read them",
                    ),
                ],
                footer=f"Owner-only · data in {config.dataDir}",
            ),
            ephemeral=True,
        )

    @debug.command(
        name="perms",
        description="(owner) Compare the permissions I need against the ones I have",
    )
    @app_commands.describe(channel="Channel to check. Defaults to this one.")
    @app_commands.guild_only()
    @ownerOnly()
    async def perms(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | discord.Thread | None = None,
    ) -> None:
        guild = interaction.guild
        me = guild.me if guild is not None else None
        if guild is None or me is None:
            await interaction.response.send_message(
                view=components.error("I'm not in this server."), ephemeral=True
            )
            return

        target = channel or interaction.channel
        serverPerms = me.guild_permissions
        channelPerms = (
            target.permissions_for(me)
            if isinstance(target, (discord.TextChannel, discord.Thread))
            else serverPerms
        )

        required = dict(basePermissions)
        byCommand = commandRequirements(self.bot)
        for perm in byCommand:
            required.setdefault(perm, True)

        held, missing = [], []
        for perm in sorted(required):
            hasHere = getattr(channelPerms, perm, False)
            hasServer = getattr(serverPerms, perm, False)
            if hasHere:
                held.append(f"`{prettyPermission(perm)}`")
                continue

            reason = "channel overwrite" if hasServer else "not granted to my role"
            users = byCommand.get(perm, [])
            breaks = (
                " — breaks " + ", ".join(f"`{name}`" for name in users[:4])
                if users
                else ""
            )
            missing.append(f"❌ `{prettyPermission(perm)}` ({reason}){breaks}")

        fields = [
            (
                f"Missing in {getattr(target, 'mention', 'here')}",
                "\n".join(missing)
                if missing
                else "✅ Nothing — everything I need is here.",
            ),
            ("Have", ", ".join(held) or "Nothing."),
        ]

        extras = [
            f"`{prettyPermission(perm)}` → {', '.join(f'`{n}`' for n in names)}"
            for perm, names in sorted(byCommand.items())
        ]
        if extras:
            fields.append(("Asked for by commands", "\n".join(extras)))

        buttons = []
        if config.clientId is not None:
            invite = discord.utils.oauth_url(
                config.clientId,
                permissions=discord.Permissions(**required),
                guild=guild,
            )
            buttons.append(components.linkButton("Re-invite with these", invite))

        await interaction.response.send_message(
            view=components.panel(
                title="Debug · permissions",
                body=(
                    f"Checked as {me.mention} in "
                    f"{getattr(target, 'mention', '`unknown channel`')}.\n"
                    f"Top role {me.top_role.mention} · "
                    f"administrator `{serverPerms.administrator}`"
                ),
                fields=fields,
                buttons=buttons,
                footer=f"{len(missing)} missing · {len(required)} needed in total",
                color=components.RED if missing else components.FUCHSIA,
            ),
            ephemeral=True,
        )

    @debug.command(name="errors", description="(owner) Show the most recent faults")
    @app_commands.describe(
        code="Only show one kind, e.g. WORKSHOP.",
        limit="How many to show. Defaults to 10.",
    )
    @app_commands.choices(
        code=[
            app_commands.Choice(name=name, value=name)
            for name in list(errors.codeMeanings)[:25]
        ]
    )
    @ownerOnly()
    async def listErrors(
        self,
        interaction: discord.Interaction,
        code: str | None = None,
        limit: app_commands.Range[int, 1, 25] = listLimit,
    ) -> None:
        found = errors.byCode(code)[:limit] if code else errors.recent(limit)
        if not found:
            await interaction.response.send_message(
                view=components.panel(
                    title="Debug · faults",
                    body=(
                        f"Nothing logged under `{errors.tidyRef(code)}`."
                        if code
                        else "Nothing logged. Suspicious, but take the win."
                    ),
                    footer="Faults land here as commands and events fail.",
                ),
                ephemeral=True,
            )
            return

        body = "\n\n".join(summarise(entry) for entry in found)
        await interaction.response.send_message(
            view=components.panel(
                title="Debug · faults",
                body=body,
                footer=(
                    f"Showing {len(found)} of {errors.count()} · "
                    "`debug trace <code>` for the traceback · "
                    "`debug codes` for what they mean"
                ),
                color=components.RED,
            ),
            ephemeral=True,
        )

    @debug.command(
        name="codes", description="(owner) What each fault code means, and how many"
    )
    @ownerOnly()
    async def listCodes(self, interaction: discord.Interaction) -> None:
        tally: dict[str, int] = {}
        for entry in errors.entries():
            name = str(entry.get("code") or errors.fallbackCode)
            tally[name] = tally.get(name, 0) + int(entry.get("count", 1) or 1)

        lines = [
            f"`{name}` — {meaning}"
            + (f"\n-# {tally[name]} logged" if name in tally else "")
            for name, meaning in errors.codeMeanings.items()
        ]

        await interaction.response.send_message(
            view=components.panel(
                title="Debug · fault codes",
                body="\n".join(lines),
                footer=(
                    "A fault reads `CODE-XXXX`: the code says what went wrong, "
                    "the four characters say which one."
                ),
            ),
            ephemeral=True,
        )

    async def referenceAutocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        typed = errors.tidyRef(current)
        found = [
            entry
            for entry in errors.entries()
            if typed in str(entry.get("ref", "")).upper()
        ]
        return [
            app_commands.Choice(
                name=(
                    f"{entry.get('ref', '?')} — {entry.get('kind', '?')} in "
                    f"{entry.get('command', '—')}"
                )[:100],
                value=str(entry.get("ref", "")),
            )
            for entry in found[:25]
        ]

    @debug.command(
        name="trace",
        description="(owner) Look up one fault by the code someone quoted",
    )
    @app_commands.describe(
        reference="The code from the error message, e.g. WORKSHOP-4F2K."
    )
    @app_commands.autocomplete(reference=referenceAutocomplete)
    @ownerOnly()
    async def trace(self, interaction: discord.Interaction, reference: str) -> None:
        entry = errors.find(reference)
        if entry is None:
            await interaction.response.send_message(
                view=components.error(
                    f"Nothing logged under `{errors.tidyRef(reference)}`. It may have "
                    f"aged out of the last {errors.keepLimit}, or been cleared."
                ),
                ephemeral=True,
            )
            return

        when = entry.get("when")
        first = entry.get("first")
        seen = int(entry.get("count", 1) or 1)
        missing = entry.get("missing") or []
        trace = str(entry.get("trace") or "").strip()

        code = str(entry.get("code") or "")
        meaning = errors.codeMeanings.get(code, "")

        history = f"Hit **{seen}** time{'' if seen == 1 else 's'}"
        if isinstance(first, int) and seen > 1:
            history += f", first <t:{first}:R>"

        fields = [
            ("Message", components.codeBlock(str(entry.get("text", "—"))[:900])),
            (
                "Last seen",
                (
                    f"Source: `{entry.get('source', '?')}`\n"
                    f"Command: `{entry.get('command', '—')}`\n"
                    f"Server: `{entry.get('guild', '—')}`\n"
                    f"Channel: `{entry.get('channel', '—')}`\n"
                    f"User: `{entry.get('user', '—')}`"
                ),
            ),
        ]
        if missing:
            fields.append(
                (
                    "Missing permissions",
                    ", ".join(f"`{prettyPermission(perm)}`" for perm in missing),
                )
            )
        if trace:
            fields.append(
                ("Traceback", components.codeBlock(trace[-traceDisplayLimit:], "py"))
            )

        await interaction.response.send_message(
            view=components.panel(
                title=f"Debug · {entry.get('ref', '?')} · {entry.get('kind', '?')}",
                body=(
                    (f"{meaning}\n\n" if meaning else "")
                    + f"{history}.\n"
                    + (
                        f"Last <t:{when}:F> (<t:{when}:R>)"
                        if isinstance(when, int)
                        else ""
                    )
                ),
                fields=fields,
                footer=f"One of {errors.count()} logged · `debug errors` for the list",
                color=components.RED,
            ),
            ephemeral=True,
        )

    @debug.command(name="clear", description="(owner) Wipe the error log")
    @ownerOnly()
    async def clearErrors(self, interaction: discord.Interaction) -> None:
        cleared = errors.clear()
        body = f"Cleared {cleared} errors." if cleared else "Nothing to clear."
        await interaction.response.send_message(
            view=components.panel(body=body), ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Debug(bot))
