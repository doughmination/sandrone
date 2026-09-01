import asyncio
import datetime as dt
import ipaddress
import re

import discord
from discord import app_commands
from discord.ext import commands

from sandrone import doughchecks

ianaServer = "whois.iana.org"
whoisPort = 43
lookupTimeout = 10
maxHops = 4

embedColor = discord.Color.fuchsia()
errorColor = discord.Color.red()
thumbnail = "https://m.doughmination.gay/img/search.png"

queryFormats = {
    "whois.verisign-grs.com": "domain {query}",
    "whois.jprs.jp": "{query}/e",
    "whois.denic.de": "-T dn {query}",
}

referralKeys = ("refer", "whois", "registrar whois server", "whois server")

notFoundMarkers = (
    "no match",
    "not found",
    "no entries found",
    "no data found",
    "no object found",
    "nothing found",
    "status: free",
    "status: available",
)

domainFields = (
    ("Registrar", ("registrar", "sponsoring registrar", "registrar name"), False),
    (
        "Registered",
        (
            "creation date",
            "created",
            "created on",
            "registered on",
            "registered",
        ),
        True,
    ),
    (
        "Updated",
        ("updated date", "last updated", "last-update", "modified", "changed"),
        True,
    ),
    (
        "Expires",
        (
            "registry expiry date",
            "registrar registration expiration date",
            "expiry date",
            "expiration date",
            "paid-till",
            "expires",
            "expires on",
        ),
        True,
    ),
    (
        "Registrant",
        ("registrant organization", "registrant name", "registrant", "holder", "org"),
        False,
    ),
    ("Country", ("registrant country", "country"), False),
    ("DNSSEC", ("dnssec",), False),
)

networkFields = (
    ("Range", ("netrange", "inetnum", "inet6num"), False),
    ("CIDR", ("cidr", "route", "route6"), False),
    ("Network", ("netname",), False),
    (
        "Organisation",
        ("orgname", "org-name", "organization", "organisation", "owner", "descr"),
        False,
    ),
    ("Country", ("country",), False),
    ("Registered", ("regdate", "created"), True),
    ("Updated", ("updated", "last-modified", "changed"), True),
    ("Abuse", ("orgabuseemail", "abuse-mailbox", "abuse-c"), False),
)

dateFormats = (
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%d-%b-%Y",
    "%Y.%m.%d",
    "%Y/%m/%d",
    "%d.%m.%Y",
)


def normaliseQuery(query: str) -> str:
    query = query.strip().strip("<>").lower()
    query = re.sub(r"^[a-z][a-z0-9+.-]*://", "", query)
    query = query.split("/")[0].split("?")[0].split("#")[0]
    query = query.split("@")[-1]
    if query.count(":") == 1:
        query = query.split(":")[0]
    return query.removeprefix("www.").rstrip(".")


def isNetwork(query: str) -> bool:
    try:
        ipaddress.ip_address(query)
    except ValueError:
        return query.isdigit()
    return True


def addField(fields: dict[str, list[str]], key: str, value: str) -> None:
    key = key.strip().lower()
    value = value.strip()
    if not key or not value:
        return
    values = fields.setdefault(key, [])
    if value not in values:
        values.append(value)


def parseRecord(text: str) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    lines = text.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        index += 1
        stripped = line.strip()
        if not stripped or stripped[0] in "%#*>":
            continue

        if stripped.startswith("[") and "]" in stripped:
            key, _, value = stripped[1:].partition("]")
            addField(fields, key, value)
            continue

        if ":" not in stripped:
            continue

        key, _, value = stripped.partition(":")
        if value.strip():
            addField(fields, key, value)
            continue

        while index < len(lines):
            follow = lines[index]
            if (
                not follow.strip()
                or ":" in follow
                or not follow.startswith((" ", "\t"))
            ):
                break
            addField(fields, key, follow)
            index += 1

    return fields


def isPlaceholder(value: str) -> bool:
    value = value.strip()
    if value.lower() in ("n/a", "na", "none", "null", "-", "not applicable"):
        return True
    return value.startswith(("0000-00-00", "0001-01-01"))


def firstValue(fields: dict[str, list[str]], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        values = fields.get(key)
        if values:
            return values[0]
    return None


def formatDate(value: str) -> str:
    raw = value.split("(")[0].strip()
    stamp = None
    try:
        stamp = dt.datetime.fromisoformat(raw)
    except ValueError:
        for pattern in dateFormats:
            try:
                stamp = dt.datetime.strptime(raw, pattern).replace(tzinfo=dt.UTC)
                break
            except ValueError:
                continue
    if stamp is None:
        return value
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dt.UTC)
    return f"<t:{int(stamp.timestamp())}:D>"


def formatStatuses(fields: dict[str, list[str]]) -> str | None:
    statuses = (
        fields.get("domain status") or fields.get("status") or fields.get("state")
    )
    if not statuses:
        return None
    cleaned: list[str] = []
    for status in statuses:
        name = status.split()[0].strip(",")
        if name and name not in cleaned:
            cleaned.append(name)
    return ", ".join(f"`{name}`" for name in cleaned[:6]) or None


def formatNameServers(fields: dict[str, list[str]]) -> str | None:
    servers: list[str] = []
    for key in ("name server", "name servers", "nserver", "nameserver", "ns"):
        for value in fields.get(key, []):
            host = value.split()[0].lower().rstrip(".")
            if host and host not in servers:
                servers.append(host)
    if not servers:
        return None
    return "\n".join(servers[:8])


class Whois(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="whois", description="Look up the WHOIS record for a domain or IP"
    )
    @app_commands.describe(query="The domain name or IP address to look up")
    @doughchecks.has_permissions(embed_links=True)
    async def whoisSlash(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        embed = await self.getWhoisEmbed(query)
        await interaction.followup.send(embed=embed)

    async def askServer(self, server: str, query: str) -> str:
        request = queryFormats.get(server, "{query}").format(query=query)
        reader, writer = await asyncio.open_connection(server, whoisPort)
        try:
            writer.write(f"{request}\r\n".encode())
            await writer.drain()
            data = await reader.read(-1)
        finally:
            writer.close()
            await writer.wait_closed()
        return data.decode("utf-8", errors="replace")

    async def lookup(self, query: str, isIp: bool) -> list[tuple[str, str]]:
        server = ianaServer
        target = query if isIp else query.rsplit(".", 1)[-1]
        records: list[tuple[str, str]] = []
        seen: set[str] = set()

        for hop in range(maxHops):
            if not server or server in seen:
                break
            seen.add(server)
            try:
                text = await asyncio.wait_for(
                    self.askServer(server, target), timeout=lookupTimeout
                )
            except OSError, TimeoutError:
                if hop == 0:
                    raise
                break
            records.append((server, text))
            referral = firstValue(parseRecord(text), referralKeys)
            server = referral.split()[0].lower().rstrip(".") if referral else ""
            if not server and hop == 0 and not isIp:
                server = f"whois.nic.{target}"
            target = query

        return records

    def mergeRecords(self, records: list[tuple[str, str]]) -> dict[str, list[str]]:
        usable = records[1:] if len(records) > 1 else records
        merged: dict[str, list[str]] = {}
        for _, text in usable:
            for key, values in parseRecord(text).items():
                if key in merged and all(isPlaceholder(value) for value in values):
                    continue
                merged[key] = values
        return merged

    async def getWhoisEmbed(self, query: str) -> discord.Embed:
        target = normaliseQuery(query)
        embed = discord.Embed(color=errorColor)
        embed.set_thumbnail(url=thumbnail)

        isIp = isNetwork(target)
        if not target or (not isIp and "." not in target):
            embed.description = (
                ":x: That doesn't look like a domain or IP address. Try `example.com`."
            )
            return embed

        try:
            records = await self.lookup(target, isIp)
        except OSError, TimeoutError:
            embed.description = (
                ":x: Couldn't reach the WHOIS servers — try again in a moment."
            )
            return embed

        if len(records) < 2:
            embed.description = (
                f":x: No WHOIS server published a record for `{target}`."
            )
            return embed

        fields = self.mergeRecords(records)
        body = records[-1][1].lower()
        fieldSet = networkFields if isIp else domainFields
        values = [
            (name, formatDate(value) if isDate else value)
            for name, keys, isDate in fieldSet
            if (value := firstValue(fields, keys))
        ]

        if not values and any(marker in body for marker in notFoundMarkers):
            embed.description = f":x: No WHOIS record found for `{target}`."
            return embed

        embed.color = embedColor
        embed.title = target
        embed.set_footer(text=f"Powered by WHOIS · {records[-1][0]}")

        for name, value in values:
            embed.add_field(name=name, value=value[:1024], inline=True)

        statuses = formatStatuses(fields)
        if statuses:
            embed.add_field(name="Status", value=statuses[:1024], inline=False)

        nameServers = formatNameServers(fields)
        if nameServers and not isIp:
            embed.add_field(name="Name Servers", value=nameServers, inline=False)

        if not embed.fields:
            snippet = records[-1][1].strip()[:1000]
            embed.description = (
                f"```\n{snippet}\n```"
                if snippet
                else ":x: The WHOIS server returned nothing useful."
            )

        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Whois(bot))
