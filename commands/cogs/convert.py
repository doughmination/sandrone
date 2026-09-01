import math
from typing import NamedTuple

import discord
from discord import app_commands
from discord.ext import commands

from sandrone import doughchecks


class Unit(NamedTuple):
    key: str
    name: str
    symbol: str
    scale: float
    aliases: tuple[str, ...] = ()
    offset: float = 0.0
    category: str = ""

    @property
    def label(self) -> str:
        return f"{self.name} ({self.symbol})"


categoryLabels = {
    "temperature": "Temperature",
    "length": "Length",
    "mass": "Mass",
    "digital": "Digital storage",
    "rate": "Data rate",
    "time": "Time",
    "speed": "Speed",
    "area": "Area",
    "volume": "Volume",
    "pressure": "Pressure",
    "energy": "Energy",
    "angle": "Angle",
}

fahrenheitOffset = 273.15 - 160 / 9

# Every unit converts through the first unit of its category:
#   base = value * scale + offset
# Only temperature needs the offset; everything else leaves it at zero.
unitTable: dict[str, tuple[Unit, ...]] = {
    "temperature": (
        Unit("kelvin", "Kelvin", "K", 1, ("k",)),
        Unit("celsius", "Celsius", "°C", 1, ("c", "degc", "centigrade"), 273.15),
        Unit("fahrenheit", "Fahrenheit", "°F", 5 / 9, ("f", "degf"), fahrenheitOffset),
        Unit("rankine", "Rankine", "°R", 5 / 9, ("r", "degr")),
    ),
    "length": (
        Unit("metre", "Metre", "m", 1, ("meter", "metres", "meters")),
        Unit("nanometre", "Nanometre", "nm", 1e-9, ("nanometer",)),
        Unit("micrometre", "Micrometre", "µm", 1e-6, ("um", "micron", "micrometer")),
        Unit("millimetre", "Millimetre", "mm", 1e-3, ("millimeter",)),
        Unit("centimetre", "Centimetre", "cm", 1e-2, ("centimeter",)),
        Unit("kilometre", "Kilometre", "km", 1e3, ("kilometer",)),
        Unit("inch", "Inch", "in", 0.0254, ("inches",)),
        Unit("foot", "Foot", "ft", 0.3048, ("feet",)),
        Unit("yard", "Yard", "yd", 0.9144, ("yards",)),
        Unit("mile", "Mile", "mi", 1609.344, ("miles",)),
        Unit("nautical_mile", "Nautical mile", "nmi", 1852),
        Unit("light_year", "Light-year", "ly", 9460730472580800, ("lightyear",)),
        Unit("au", "Astronomical unit", "AU", 149597870700),
    ),
    "mass": (
        Unit("kilogram", "Kilogram", "kg", 1, ("kilo", "kilos")),
        Unit("microgram", "Microgram", "µg", 1e-9, ("ug",)),
        Unit("milligram", "Milligram", "mg", 1e-6),
        Unit("gram", "Gram", "g", 1e-3, ("grams",)),
        Unit("tonne", "Tonne", "t", 1000, ("tonnes", "metricton")),
        Unit("ounce", "Ounce", "oz", 0.028349523125, ("ounces",)),
        Unit("pound", "Pound", "lb", 0.45359237, ("lbs", "pounds")),
        Unit("stone", "Stone", "st", 6.35029318),
        Unit("short_ton", "US ton", "ton", 907.18474, ("shortton",)),
        Unit("carat", "Carat", "ct", 0.0002),
    ),
    "digital": (
        Unit("byte", "Byte", "B", 1, ("bytes",)),
        Unit("bit", "Bit", "b", 0.125, ("bits",)),
        Unit("kilobyte", "Kilobyte", "kB", 1e3, ("kb",)),
        Unit("kibibyte", "Kibibyte", "KiB", 1024),
        Unit("megabyte", "Megabyte", "MB", 1e6),
        Unit("mebibyte", "Mebibyte", "MiB", 1048576),
        Unit("gigabyte", "Gigabyte", "GB", 1e9),
        Unit("gibibyte", "Gibibyte", "GiB", 1073741824),
        Unit("terabyte", "Terabyte", "TB", 1e12),
        Unit("tebibyte", "Tebibyte", "TiB", 1099511627776),
        Unit("petabyte", "Petabyte", "PB", 1e15),
        Unit("pebibyte", "Pebibyte", "PiB", 1125899906842624),
    ),
    "rate": (
        Unit("bit_s", "Bit/second", "bit/s", 1, ("bps",)),
        Unit("kilobit_s", "Kilobit/second", "kbit/s", 1e3, ("kbps",)),
        Unit("megabit_s", "Megabit/second", "Mbit/s", 1e6, ("mbps",)),
        Unit("gigabit_s", "Gigabit/second", "Gbit/s", 1e9, ("gbps",)),
        Unit("byte_s", "Byte/second", "B/s", 8),
        Unit("kilobyte_s", "Kilobyte/second", "kB/s", 8e3),
        Unit("megabyte_s", "Megabyte/second", "MB/s", 8e6),
        Unit("gigabyte_s", "Gigabyte/second", "GB/s", 8e9),
    ),
    "time": (
        Unit("second", "Second", "s", 1, ("sec", "secs", "seconds")),
        Unit("nanosecond", "Nanosecond", "ns", 1e-9),
        Unit("microsecond", "Microsecond", "µs", 1e-6, ("us",)),
        Unit("millisecond", "Millisecond", "ms", 1e-3),
        Unit("minute", "Minute", "min", 60, ("mins", "minutes")),
        Unit("hour", "Hour", "h", 3600, ("hr", "hrs", "hours")),
        Unit("day", "Day", "d", 86400, ("days",)),
        Unit("week", "Week", "wk", 604800, ("weeks",)),
        Unit("month", "Month", "mo", 2629746, ("months",)),
        Unit("year", "Year", "yr", 31556952, ("years",)),
    ),
    "speed": (
        Unit("metre_s", "Metre/second", "m/s", 1, ("ms",)),
        Unit("kilometre_h", "Kilometre/hour", "km/h", 1 / 3.6, ("kph", "kmh")),
        Unit("mile_h", "Mile/hour", "mph", 0.44704),
        Unit("foot_s", "Foot/second", "ft/s", 0.3048, ("fps",)),
        Unit("knot", "Knot", "kn", 1852 / 3600, ("kt", "knots")),
        Unit("mach", "Mach", "Ma", 340.29),
    ),
    "area": (
        Unit("sq_metre", "Square metre", "m²", 1, ("m2", "sqm")),
        Unit("sq_millimetre", "Square millimetre", "mm²", 1e-6, ("mm2",)),
        Unit("sq_centimetre", "Square centimetre", "cm²", 1e-4, ("cm2",)),
        Unit("sq_kilometre", "Square kilometre", "km²", 1e6, ("km2",)),
        Unit("sq_inch", "Square inch", "in²", 0.00064516, ("in2",)),
        Unit("sq_foot", "Square foot", "ft²", 0.09290304, ("ft2", "sqft")),
        Unit("sq_yard", "Square yard", "yd²", 0.83612736, ("yd2",)),
        Unit("acre", "Acre", "ac", 4046.8564224, ("acres",)),
        Unit("hectare", "Hectare", "ha", 10000),
        Unit("sq_mile", "Square mile", "mi²", 2589988.110336, ("mi2",)),
    ),
    "volume": (
        Unit("litre", "Litre", "L", 1, ("liter", "litres", "liters")),
        Unit("millilitre", "Millilitre", "ml", 1e-3, ("milliliter",)),
        Unit("centilitre", "Centilitre", "cl", 1e-2, ("centiliter",)),
        Unit("cubic_centimetre", "Cubic centimetre", "cm³", 1e-3, ("cc", "cm3")),
        Unit("cubic_metre", "Cubic metre", "m³", 1000, ("m3",)),
        Unit("teaspoon", "US teaspoon", "tsp", 0.00492892159375),
        Unit("tablespoon", "US tablespoon", "tbsp", 0.01478676478125),
        Unit("fluid_ounce", "US fluid ounce", "fl oz", 0.0295735295625, ("floz",)),
        Unit("cup", "US cup", "cup", 0.2365882365, ("cups",)),
        Unit("pint", "US pint", "pt", 0.473176473),
        Unit("quart", "US quart", "qt", 0.946352946),
        Unit("gallon", "US gallon", "gal", 3.785411784),
        Unit("imperial_pint", "Imperial pint", "imp pt", 0.56826125),
        Unit("imperial_gallon", "Imperial gallon", "imp gal", 4.54609),
    ),
    "pressure": (
        Unit("pascal", "Pascal", "Pa", 1),
        Unit("hectopascal", "Hectopascal", "hPa", 100),
        Unit("kilopascal", "Kilopascal", "kPa", 1000),
        Unit("millibar", "Millibar", "mbar", 100),
        Unit("bar", "Bar", "bar", 100000),
        Unit("atmosphere", "Atmosphere", "atm", 101325),
        Unit("psi", "Pound/square inch", "psi", 6894.757293168),
        Unit("torr", "Torr", "Torr", 101325 / 760, ("mmhg",)),
    ),
    "energy": (
        Unit("joule", "Joule", "J", 1, ("joules",)),
        Unit("kilojoule", "Kilojoule", "kJ", 1000),
        Unit("calorie", "Calorie", "cal", 4.184),
        Unit("kilocalorie", "Kilocalorie", "kcal", 4184, ("cals",)),
        Unit("watt_hour", "Watt-hour", "Wh", 3600),
        Unit("kilowatt_hour", "Kilowatt-hour", "kWh", 3600000),
        Unit("electronvolt", "Electronvolt", "eV", 1.602176634e-19),
        Unit("btu", "British thermal unit", "BTU", 1055.05585262),
        Unit("foot_pound", "Foot-pound", "ft⋅lb", 1.3558179483314004, ("ftlb",)),
    ),
    "angle": (
        Unit("degree", "Degree", "°", 1, ("deg", "degrees")),
        Unit("radian", "Radian", "rad", 180 / math.pi, ("radians",)),
        Unit("gradian", "Gradian", "gon", 0.9, ("grad", "gradians")),
        Unit("arcminute", "Arcminute", "′", 1 / 60, ("arcmin",)),
        Unit("arcsecond", "Arcsecond", "″", 1 / 3600, ("arcsec",)),
        Unit("turn", "Turn", "turn", 360, ("rev", "revolution")),
    ),
}

units: tuple[Unit, ...] = tuple(
    unit._replace(category=category)
    for category, group in unitTable.items()
    for unit in group
)

unitsBySymbol = {unit.symbol: unit for unit in units}

unitLookup: dict[str, Unit] = {}
for lookupUnit in units:
    for token in (
        lookupUnit.key,
        lookupUnit.name,
        lookupUnit.symbol,
        *lookupUnit.aliases,
    ):
        unitLookup.setdefault(token.lower(), lookupUnit)


def resolveUnit(text: str | None) -> Unit | None:
    if not text:
        return None
    query = text.strip()
    # Exact symbol first, so "b" stays bits and "B" stays bytes.
    return unitsBySymbol.get(query) or unitLookup.get(query.lower())


def convertValue(value: float, source: Unit, target: Unit) -> float:
    base = value * source.scale + source.offset
    return (base - target.offset) / target.scale


def formatValue(value: float) -> str:
    if value == 0:
        return "0"

    magnitude = abs(value)
    if magnitude >= 1e15 or magnitude < 1e-4:
        return f"{value:.6g}"

    decimals = min(12, max(0, 6 - math.floor(math.log10(magnitude))))
    text = f"{value:,.{decimals}f}"
    # Only trim the fractional part — 3600000 must not become "3,6".
    return text.rstrip("0").rstrip(".") if "." in text else text


def matchesQuery(unit: Unit, query: str) -> bool:
    if not query:
        return True
    return (
        query in unit.name.lower()
        or query in unit.symbol.lower()
        or query in unit.key
        or any(query in alias for alias in unit.aliases)
    )


def matchRank(unit: Unit, query: str) -> int:
    if not query:
        return 1
    if unit.symbol.lower() == query or query in unit.aliases:
        return 0
    if unit.name.lower().startswith(query) or unit.symbol.lower().startswith(query):
        return 0
    return 1


def suggestUnits(current: str, partner: str | None) -> list[app_commands.Choice[str]]:
    query = current.strip().lower()
    other = resolveUnit(partner)

    found = [
        unit
        for unit in units
        if (other is None or unit.category == other.category)
        and matchesQuery(unit, query)
    ]
    found.sort(key=lambda unit: matchRank(unit, query))

    return [app_commands.Choice(name=unit.label, value=unit.key) for unit in found[:25]]


class Convert(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def sourceAutocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return suggestUnits(current, getattr(interaction.namespace, "to", None))

    async def targetAutocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return suggestUnits(current, getattr(interaction.namespace, "source", None))

    @app_commands.command(name="convert", description="Convert a value between units")
    @app_commands.describe(
        value="The number to convert",
        source="The unit the value is in",
        to="The unit to convert into",
    )
    @app_commands.autocomplete(source=sourceAutocomplete, to=targetAutocomplete)
    @doughchecks.has_permissions(embed_links=True)
    async def convertSlash(
        self, interaction: discord.Interaction, value: float, source: str, to: str
    ) -> None:
        await interaction.response.send_message(
            embed=self.getConversionEmbed(value, source, to)
        )

    def getConversionEmbed(self, value: float, source: str, to: str) -> discord.Embed:
        sourceUnit = resolveUnit(source)
        targetUnit = resolveUnit(to)

        if sourceUnit is None or targetUnit is None:
            unknown = [
                raw
                for raw, unit in ((source, sourceUnit), (to, targetUnit))
                if unit is None
            ]
            return self.errorEmbed(
                f"I have no unit called `{'`, `'.join(unknown)}` — "
                "pick one from the suggestions."
            )

        if sourceUnit.category != targetUnit.category:
            return self.errorEmbed(
                f"{sourceUnit.label} is {categoryLabels[sourceUnit.category].lower()} "
                f"and {targetUnit.label} is "
                f"{categoryLabels[targetUnit.category].lower()} — those don't convert."
            )

        if not math.isfinite(value):
            return self.errorEmbed("That isn't a number I can convert.")

        result = convertValue(value, sourceUnit, targetUnit)
        if not math.isfinite(result):
            return self.errorEmbed("That conversion overflowed — try a smaller number.")

        user = self.bot.user
        embed = discord.Embed(
            color=discord.Color.fuchsia(),
            title=(
                f"{formatValue(value)} {sourceUnit.symbol}"
                f" → {formatValue(result)} {targetUnit.symbol}"
            ),
            description=f"{sourceUnit.name} → {targetUnit.name}",
        )
        embed.set_footer(
            text=f"{categoryLabels[sourceUnit.category]} · Sandrone",
            icon_url=user.avatar.url if user and user.avatar else None,
        )
        return embed

    def errorEmbed(self, message: str) -> discord.Embed:
        return discord.Embed(color=discord.Color.red(), description=f":x: {message}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Convert(bot))
