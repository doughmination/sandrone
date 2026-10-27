import asyncio
from dataclasses import dataclass
import datetime as dt
import discord
from discord import app_commands
from discord.ext import commands
import httpx2
import ipaddress
import re
from sandrone import mood
import time
from typing import Any
from utils import components
import whodap
from whodap.errors import WhodapError

ianaServer = "whois.iana.org"
whoisPort = 43
lookupTimeout = 10
maxHops = 4
# registered names sit at most this many labels above the tld, as in
# example.co.uk, so www.a.b.example.com can't fan out into dozens of
# requests
maxRdapLookups = 3
complaintForm = "https://www.icann.org/wicf/"
eppStatusDocs = "https://icann.org/epp#"

thumbnail = "https://raw.doughmination.gay/img/search.png"

cacheTtl = 300.0
maxCached = 64
rawLimit = 3500

PAGE_PREFIX = "whois:"
PAGE_TEMPLATE = r"whois:(?P<target>\S+)"

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
    (
        "Registrar",
        ("registrar", "sponsoring registrar", "registrar name"),
        False,
    ),
    (
        "Owner",
        (
            "registrant name",
            "registrant organization",
            "holder",
            "org",
        ),
        False,
    ),
    ("Country", ("registrant country", "country"), False),
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
        (
            "updated date",
            "last updated",
            "last-update",
            "modified",
            "changed",
        ),
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
    ("DNSSEC", ("dnssec",), False),
)

domainContactFields = (
    ("URL", ("registrar url", "referral url"), False),
    (
        "Abuse Email",
        ("registrar abuse contact email", "abuse contact"),
        False,
    ),
    ("Abuse Phone", ("registrar abuse contact phone",), False),
)

networkFields = (
    ("Range", ("netrange", "inetnum", "inet6num"), False),
    ("CIDR", ("cidr", "route", "route6"), False),
    ("Network", ("netname",), False),
    (
        "Organisation",
        (
            "orgname",
            "org-name",
            "organization",
            "organisation",
            "owner",
            "descr",
        ),
        False,
    ),
    ("Country", ("country",), False),
    ("Registered", ("regdate", "created"), True),
    ("Updated", ("updated", "last-modified", "changed"), True),
)

networkContactFields = (
    ("Email", ("orgabuseemail", "abuse-mailbox"), False),
    ("Phone", ("orgabusephone",), False),
    ("Handle", ("abuse-c",), False),
)

dateFormats = (
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%d-%b-%Y",
    "%Y.%m.%d",
    "%Y/%m/%d",
    "%d.%m.%Y",
)

redactionMarkers = (
    "redacted",
    "privacy",
    "withheld",
    "not disclosed",
    "data protected",
)

# the contact roles a domain record carries, as (heading, rdap key
# prefix, port 43 key prefix). the registrant is the owner and gets its
# own page, the rest share the contacts page
contactRoles = (
    ("Admin", "admin", "admin"),
    ("Technical", "technical", "tech"),
    ("Billing", "billing", "billing"),
)

eppPrefixes = ("client", "server", "pending")
eppStandalone = {
    "ok",
    "active",
    "inactive",
    "addperiod",
    "autorenewperiod",
    "renewperiod",
    "transferperiod",
    "redemptionperiod",
}


class WhoisError(Exception):
    pass


@dataclass(frozen=True)
class Page:
    key: str
    label: str
    description: str | None
    body: str


@dataclass(frozen=True)
class Report:
    title: str
    source: str
    pages: tuple[Page, ...]
    complaintForm: bool = False


_reports: dict[str, tuple[float, Report]] = {}


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


def isGeneric(domain: str) -> bool:
    # country codes are always two letters, and icann only polices
    # the rest
    return len(domain.rsplit(".", 1)[-1]) > 2


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
    lowered = value.lower()
    if lowered in (
        "n/a",
        "na",
        "none",
        "null",
        "-",
        "not applicable",
    ):
        return True
    if any(marker in lowered for marker in redactionMarkers):
        return True
    return value.startswith(("0000-00-00", "0001-01-01"))


def firstValue(
    fields: dict[str, list[str]], keys: tuple[str, ...]
) -> str | None:
    for key in keys:
        for value in fields.get(key, []):
            if not isPlaceholder(value):
                return value
    return None


def formatStamp(stamp: dt.datetime) -> str:
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dt.UTC)
    seconds = int(stamp.timestamp())
    return f"<t:{seconds}:D> (<t:{seconds}:R>)"


def formatDate(value: str) -> str:
    raw = value.split("(")[0].strip()
    stamp = None
    try:
        stamp = dt.datetime.fromisoformat(raw)
    except ValueError:
        for pattern in dateFormats:
            try:
                stamp = dt.datetime.strptime(raw, pattern).replace(
                    tzinfo=dt.UTC
                )
                break
            except ValueError:
                continue
    if stamp is None:
        return value
    return formatStamp(stamp)


def formatPhone(value: str) -> str:
    return value.removeprefix("tel:")


def eppCode(status: str) -> str:
    words = status.split()
    if len(words) > 1 and all(word.isalpha() for word in words):
        return words[0].lower() + "".join(
            word.capitalize() for word in words[1:]
        )
    return words[0].strip(",") if words else ""


def formatStatus(status: str) -> str:
    code = eppCode(status)
    if code.startswith(eppPrefixes) or code.lower() in eppStandalone:
        return f"[`{code}`](<{eppStatusDocs}{code}>)"
    return f"`{code}`"


def quoteLines(fields: list[components.Field]) -> str:
    return "\n".join(f"> **{name}**: {value}" for name, value in fields)


def quoteList(items: list[str]) -> str:
    return "\n".join(f"> {item}" for item in items)


def pickFields(
    fields: dict[str, list[str]],
    spec: tuple[tuple[str, tuple[str, ...], bool], ...],
) -> list[components.Field]:
    return [
        (name, (formatDate(value) if isDate else value)[:1024])
        for name, keys, isDate in spec
        if (value := firstValue(fields, keys))
    ]


def statusesFrom(fields: dict[str, list[str]]) -> list[str]:
    statuses = (
        fields.get("domain status")
        or fields.get("status")
        or fields.get("state")
        or []
    )
    cleaned: list[str] = []
    for status in statuses:
        code = eppCode(status)
        if code and code not in cleaned:
            cleaned.append(code)
    return cleaned


def nameServersFrom(fields: dict[str, list[str]]) -> list[str]:
    servers: list[str] = []
    for key in (
        "name server",
        "name servers",
        "nserver",
        "nameserver",
        "ns",
    ):
        for value in fields.get(key, []):
            host = value.split()[0].lower().rstrip(".")
            if host and host not in servers:
                servers.append(host)
    return servers


def present(
    pairs: tuple[tuple[str, str | None], ...],
) -> list[components.Field]:
    return [(name, value[:1024]) for name, value in pairs if value]


def portContact(
    fields: dict[str, list[str]], prefix: str
) -> list[components.Field]:
    def get(*suffixes: str) -> str | None:
        return firstValue(
            fields, tuple(f"{prefix} {suffix}" for suffix in suffixes)
        )

    streets = [
        street
        for street in fields.get(f"{prefix} street", [])
        if not isPlaceholder(street)
    ]
    address = [
        part
        for part in (
            *streets,
            get("city"),
            get("state/province", "state", "province"),
            get("postal code"),
            get("country"),
        )
        if part
    ]
    phone = get("phone")
    fax = get("fax")
    return present(
        (
            ("Name", get("name")),
            ("Organisation", get("organization", "organisation")),
            ("Email", get("email")),
            ("Phone", formatPhone(phone) if phone else None),
            ("Fax", formatPhone(fax) if fax else None),
            ("Address", ", ".join(address) or None),
        )
    )


def contactsBody(
    groups: list[tuple[str, list[components.Field]]],
    owner: list[components.Field],
) -> str:
    # admin and tech are usually the owner again, so say so rather than
    # printing the same block three times
    return "\n\n".join(
        f"**{heading}**\n"
        + (
            "> Same as the owner"
            if owner and fields == owner
            else quoteLines(fields)
        )
        for heading, fields in groups
        if fields
    )


def buildPages(
    overview: list[components.Field],
    statuses: list[str],
    nameServers: list[str],
    owner: list[components.Field],
    contacts: list[tuple[str, list[components.Field]]],
    raw: str | None = None,
) -> tuple[Page, ...]:
    pages: list[Page] = []
    if overview:
        pages.append(
            Page(
                "overview",
                "Overview",
                "Registration, dates and ownership",
                quoteLines(overview),
            )
        )
    if owner:
        pages.append(
            Page(
                "owner",
                "Owner",
                "Who the domain is registered to",
                quoteLines(owner),
            )
        )
    if statuses:
        pages.append(
            Page(
                "status",
                "Status",
                f"{len(statuses)} status code(s)",
                quoteList([formatStatus(s) for s in statuses]),
            )
        )
    if nameServers:
        pages.append(
            Page(
                "nameservers",
                "Name Servers",
                f"{len(nameServers)} name server(s)",
                quoteList([f"`{server}`" for server in nameServers]),
            )
        )
    if any(fields for _, fields in contacts):
        pages.append(
            Page(
                "contacts",
                "Contacts",
                "Registrar, abuse and other contacts",
                contactsBody(contacts, owner),
            )
        )
    if raw:
        clipped = raw[:rawLimit] + ("\n…" if len(raw) > rawLimit else "")
        pages.append(
            Page(
                "raw",
                "Raw Record",
                "The record as the server sent it",
                components.codeBlock(clipped),
            )
        )
    return tuple(pages)


def rdapCandidates(domain: str) -> list[tuple[str, str]]:
    # rdap wants the name and tld apart, so example.co.uk is example.co
    # + uk. longest first: www.example.com still falls back to
    # example.com, and registries like co.uk answer for themselves
    parts = domain.split(".")
    if len(parts) < 2:
        return []
    tld = parts[-1]
    first = max(0, len(parts) - 1 - maxRdapLookups)
    return [
        (".".join(parts[start:-1]), tld)
        for start in range(first, len(parts) - 1)
    ]


def rdapPages(record: dict[str, Any]) -> tuple[Page, ...]:
    def text(key: str) -> str | None:
        value = record.get(key)
        if not isinstance(value, str) or isPlaceholder(value):
            return None
        return value[:1024]

    def date(key: str) -> str | None:
        value = record.get(key)
        if not isinstance(value, dt.datetime):
            return None
        return formatStamp(value)

    def phone(key: str) -> str | None:
        value = text(key)
        return formatPhone(value) if value else None

    def contact(prefix: str) -> list[components.Field]:
        return present(
            (
                ("Name", text(f"{prefix}_name")),
                ("Organisation", text(f"{prefix}_organization")),
                ("Email", text(f"{prefix}_email")),
                ("Phone", phone(f"{prefix}_phone")),
                ("Fax", phone(f"{prefix}_fax")),
                ("Address", text(f"{prefix}_address")),
            )
        )

    overview = present(
        (
            ("Registrar", text("registrar_name")),
            (
                "Owner",
                text("registrant_name") or text("registrant_organization"),
            ),
            ("Registered", date("created_date")),
            ("Updated", date("updated_date")),
            ("Expires", date("expires_date")),
            ("DNSSEC", text("dnssec")),
        )
    )
    owner = contact("registrant")
    contacts = [
        ("Registrar", contact("registrar")),
        (
            "Abuse",
            present(
                (
                    ("Email", text("abuse_email")),
                    ("Phone", phone("abuse_phone")),
                )
            ),
        ),
        *(
            (heading, contact(prefix))
            for heading, prefix, _ in contactRoles
        ),
    ]
    statuses: list[str] = []
    for status in record.get("status") or []:
        code = eppCode(status) if isinstance(status, str) else ""
        if code and code not in statuses:
            statuses.append(code)
    servers = [
        server.lower().rstrip(".")
        for server in record.get("nameservers") or []
        if isinstance(server, str)
    ]
    return buildPages(overview, statuses, servers, owner, contacts)


async def askServer(server: str, query: str) -> str:
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


async def portLookup(query: str, isIp: bool) -> list[tuple[str, str]]:
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
                askServer(server, target), timeout=lookupTimeout
            )
        except OSError, TimeoutError:
            if hop == 0:
                raise
            break
        records.append((server, text))
        referral = firstValue(parseRecord(text), referralKeys)
        server = (
            referral.split()[0].lower().rstrip(".") if referral else ""
        )
        if not server and hop == 0 and not isIp:
            server = f"whois.nic.{target}"
        target = query

    return records


async def rdapLookup(domain: str) -> dict[str, Any] | None:
    candidates = rdapCandidates(domain)
    if not candidates:
        return None
    async with whodap.DNSClient.new_aio_client_context() as client:
        for name, tld in candidates:
            try:
                response = await asyncio.wait_for(
                    client.aio_lookup(name, tld),
                    timeout=lookupTimeout,
                )
            except WhodapError, httpx2.HTTPError, TimeoutError:
                continue
            return response.to_whois_dict()
    return None


def mergeRecords(records: list[tuple[str, str]]) -> dict[str, list[str]]:
    usable = records[1:] if len(records) > 1 else records
    merged: dict[str, list[str]] = {}
    for _, text in usable:
        for key, values in parseRecord(text).items():
            if key in merged and all(
                isPlaceholder(value) for value in values
            ):
                continue
            merged[key] = values
    return merged


async def buildReport(target: str) -> Report:
    isIp = isNetwork(target)
    if not target or (not isIp and "." not in target):
        raise WhoisError(
            "That doesn't look like a domain or IP address. Try "
            "`example.com`."
        )

    if not isIp:
        try:
            record = await rdapLookup(target)
        except NotImplementedError, httpx2.HTTPError, TimeoutError:
            # no rdap server for this tld (.de and friends), so port 43
            # it is
            record = None
        if record and (pages := rdapPages(record)):
            return Report(
                title=str(record.get("domain_name") or target).lower(),
                source="RDAP",
                pages=pages,
                complaintForm=isGeneric(target),
            )

    try:
        records = await portLookup(target, isIp)
    except OSError, TimeoutError:
        raise WhoisError(
            "Couldn't reach the WHOIS servers — try again in a moment."
        ) from None

    if len(records) < 2:
        raise WhoisError(
            f"No WHOIS server published a record for `{target}`."
        )

    server, text = records[-1]
    fields = mergeRecords(records)
    overview = pickFields(fields, networkFields if isIp else domainFields)
    if isIp:
        owner: list[components.Field] = []
        contacts = [("Abuse", pickFields(fields, networkContactFields))]
    else:
        owner = portContact(fields, "registrant")
        contacts = [
            ("Registrar", pickFields(fields, domainContactFields)),
            *(
                (heading, portContact(fields, prefix))
                for heading, _, prefix in contactRoles
            ),
        ]
    raw = text.strip()

    if not overview and any(
        marker in text.lower() for marker in notFoundMarkers
    ):
        raise WhoisError(f"No WHOIS record found for `{target}`.")
    if not raw:
        raise WhoisError("The WHOIS server returned nothing useful.")

    return Report(
        title=target,
        source=f"WHOIS · {server}",
        pages=buildPages(
            overview,
            statusesFrom(fields),
            [] if isIp else nameServersFrom(fields),
            owner,
            contacts,
            raw,
        ),
        complaintForm=not isIp and isGeneric(target),
    )


async def getReport(target: str) -> Report:
    hit = _reports.get(target)
    if hit and time.monotonic() - hit[0] < cacheTtl:
        return hit[1]
    report = await buildReport(target)
    if len(_reports) >= maxCached:
        _reports.clear()
    _reports[target] = (time.monotonic(), report)
    return report


def renderReport(
    target: str, report: Report, pageKey: str = "overview"
) -> components.Panel:
    page = next(
        (page for page in report.pages if page.key == pageKey),
        report.pages[0],
    )
    customId = f"{PAGE_PREFIX}{target}"
    # custom ids cap at 100 characters, so a very long name just gets
    # its first page without the menu
    menu = (
        components.pagePicker(
            customId,
            [(p.key, p.label, p.description) for p in report.pages],
            page.key,
        )
        if len(report.pages) > 1 and len(customId) <= 100
        else None
    )
    return components.panel(
        title=f"WHOIS Information for {report.title}"[:256],
        body=page.body,
        thumbnail=thumbnail,
        menu=menu,
        buttons=[
            components.linkButton("Report inaccurate data", complaintForm)
        ]
        if report.complaintForm
        else None,
        footer=f"{page.label} · Powered by {report.source}",
    )


async def whoisPanel(
    query: str, pageKey: str = "overview"
) -> components.Panel:
    target = normaliseQuery(query)
    try:
        report = await getReport(target)
    except WhoisError as error:
        return components.panel(
            body=f":x: {error}",
            thumbnail=thumbnail,
            color=components.RED,
        )
    return renderReport(target, report, pageKey)


class WhoisPage(
    discord.ui.DynamicItem[discord.ui.Select], template=PAGE_TEMPLATE
):
    def __init__(self, target: str, customId: str) -> None:
        self.target = target
        super().__init__(
            discord.ui.Select(
                custom_id=customId,
                options=[
                    discord.SelectOption(label="_", value="overview")
                ],
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> WhoisPage:
        return cls(match["target"], match.string)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await interaction.edit_original_response(
            view=await whoisPanel(self.target, self.item.values[0])
        )


class Whois(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="whois",
        description="Look up the WHOIS record for a domain or IP",
    )
    @app_commands.describe(
        query="The domain name or IP address to look up"
    )
    @mood.sassy
    async def whois(
        self, interaction: discord.Interaction, query: str
    ) -> None:
        await interaction.response.defer()
        await interaction.followup.send(view=await whoisPanel(query))


async def setup(bot: commands.Bot) -> None:
    bot.add_dynamic_items(WhoisPage)
    await bot.add_cog(Whois(bot))
