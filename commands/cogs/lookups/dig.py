import asyncio
from dataclasses import dataclass
import discord
from discord import app_commands
from discord.ext import commands
from dns import asyncresolver, exception, name, resolver, reversename
import ipaddress
import re
from sandrone import mood
import time
from typing import Any
from utils import components

recordTypes = ("A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "CAA")
# public resolvers rather than the host's, which would answer for
# internal names too
publicNameservers = ["1.1.1.1", "9.9.9.9"]
lookupTimeout = 5.0
maxNameLength = 253

thumbnail = "https://raw.doughmination.gay/img/search.png"

cacheTtl = 120.0
maxCached = 64
overviewLimit = 300
pageLimit = 3500

PAGE_PREFIX = "dig:"
PAGE_TEMPLATE = r"dig:(?P<target>\S+)"


class DigError(Exception):
    pass


@dataclass(frozen=True)
class RecordSet:
    kind: str
    ttl: int
    values: tuple[str, ...]


@dataclass(frozen=True)
class DigResult:
    name: str
    sets: tuple[RecordSet, ...]


_results: dict[str, tuple[float, DigResult]] = {}


def normaliseName(query: str) -> str:
    query = query.strip().strip("<>")
    query = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", query)
    query = query.split("/")[0].split("?")[0].split("#")[0]
    query = query.split("@")[-1]
    if query.count(":") == 1:
        query = query.split(":")[0]
    return query.rstrip(".").lower()


def isAddress(query: str) -> bool:
    try:
        ipaddress.ip_address(query)
    except ValueError:
        return False
    return True


def makeResolver() -> asyncresolver.Resolver:
    dns = asyncresolver.Resolver(configure=False)
    dns.nameservers = publicNameservers
    dns.lifetime = lookupTimeout
    return dns


async def queryType(
    dns: asyncresolver.Resolver, target: name.Name, kind: str
) -> RecordSet | None:
    try:
        answer = await dns.resolve(target, kind, search=False)
    except resolver.NoAnswer, resolver.NoNameservers:
        return None
    if answer.rrset is None:
        return None
    return RecordSet(
        kind,
        answer.rrset.ttl,
        tuple(record.to_text() for record in answer),
    )


async def dig(query: str) -> DigResult:
    target = normaliseName(query)
    if not target or len(target) > maxNameLength:
        raise DigError(
            "That doesn't look like a domain or IP address. Try "
            "`example.com`."
        )

    try:
        if isAddress(target):
            dnsName = reversename.from_address(target)
            kinds: tuple[str, ...] = ("PTR",)
        else:
            dnsName = name.from_text(target)
            kinds = recordTypes
    except exception.DNSException:
        raise DigError(f"`{target}` is not a valid domain.") from None

    dns = makeResolver()
    outcomes = await asyncio.gather(
        *(queryType(dns, dnsName, kind) for kind in kinds),
        return_exceptions=True,
    )

    if any(isinstance(out, resolver.NXDOMAIN) for out in outcomes):
        raise DigError(f"`{target}` does not exist.")
    sets = tuple(out for out in outcomes if isinstance(out, RecordSet))
    if not sets:
        if all(isinstance(out, exception.Timeout) for out in outcomes):
            raise DigError("The DNS lookup timed out.")
        raise DigError(f"No DNS records found for `{target}`.")
    for out in outcomes:
        # anything that isn't dns trouble is a real bug, so let it out
        if isinstance(out, BaseException) and not isinstance(
            out, exception.DNSException
        ):
            raise out

    return DigResult(target, sets)


async def getResult(target: str) -> DigResult:
    hit = _results.get(target)
    if hit and time.monotonic() - hit[0] < cacheTtl:
        return hit[1]
    result = await dig(target)
    if len(_results) >= maxCached:
        _results.clear()
    _results[target] = (time.monotonic(), result)
    return result


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "\n…"


def recordCount(records: RecordSet) -> str:
    count = len(records.values)
    return (
        f"{count} record{'s' if count != 1 else ''} · TTL {records.ttl}s"
    )


def overviewBody(result: DigResult) -> str:
    return "\n".join(
        f"> **{records.kind}** · {recordCount(records)}\n"
        + components.codeBlock(
            clip("\n".join(records.values), overviewLimit)
        )
        for records in result.sets
    )


def recordBody(records: RecordSet) -> str:
    return f"> **{records.kind}** · {recordCount(records)}\n" + (
        components.codeBlock(clip("\n".join(records.values), pageLimit))
    )


def renderResult(
    target: str, result: DigResult, pageKey: str = "all"
) -> components.Panel:
    picked = next(
        (records for records in result.sets if records.kind == pageKey),
        None,
    )
    if len(result.sets) == 1:
        picked = result.sets[0]
    body = recordBody(picked) if picked else overviewBody(result)
    label = f"{picked.kind} Records" if picked else "All Records"

    customId = f"{PAGE_PREFIX}{target}"
    menu = (
        components.pagePicker(
            customId,
            [("all", "All Records", "A short look at every type")]
            + [
                (
                    records.kind,
                    f"{records.kind} Records",
                    recordCount(records),
                )
                for records in result.sets
            ],
            picked.kind if picked else "all",
            placeholder="Pick a record type…",
        )
        if len(result.sets) > 1 and len(customId) <= 100
        else None
    )
    return components.panel(
        title=f"DNS Records for {result.name}"[:256],
        body=body,
        thumbnail=thumbnail,
        menu=menu,
        footer=f"{label} · Resolved via 1.1.1.1 and 9.9.9.9",
    )


async def digPanel(query: str, pageKey: str = "all") -> components.Panel:
    target = normaliseName(query)
    try:
        result = await getResult(target)
    except DigError as error:
        return components.panel(
            body=f":x: {error}",
            thumbnail=thumbnail,
            color=components.RED,
        )
    return renderResult(target, result, pageKey)


class DigPage(
    discord.ui.DynamicItem[discord.ui.Select], template=PAGE_TEMPLATE
):
    def __init__(self, target: str, customId: str) -> None:
        self.target = target
        super().__init__(
            discord.ui.Select(
                custom_id=customId,
                options=[discord.SelectOption(label="_", value="all")],
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> DigPage:
        return cls(match["target"], match.string)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await interaction.edit_original_response(
            view=await digPanel(self.target, self.item.values[0])
        )


class Dig(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="dig",
        description="Look up the DNS records for a domain or IP",
    )
    @app_commands.describe(
        query="The domain, URL or IP address to look up"
    )
    @mood.sassy
    async def dig(
        self, interaction: discord.Interaction, query: str
    ) -> None:
        await interaction.response.defer()
        await interaction.followup.send(view=await digPanel(query))


async def setup(bot: commands.Bot) -> None:
    bot.add_dynamic_items(DigPage)
    await bot.add_cog(Dig(bot))
