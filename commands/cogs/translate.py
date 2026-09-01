import asyncio
import re

import discord
from argostranslate import package, translate
from discord import app_commands
from discord.ext import commands

from sandrone import doughchecks

titleBrackets = (("『", "』"), ("《", "》"))
placeholderPattern = re.compile(r"X(\d+)X")

defaultTarget = "en"
maxInput = 1000
fieldLimit = 1024


class Translate(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.languageNames: dict[str, str] = {}
        self.pairs: set[tuple[str, str]] = set()
        self.lock = asyncio.Lock()

    async def languageAutocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        names = await self.ensureIndex()
        query = current.lower()
        return [
            app_commands.Choice(name=f"{name} ({code})", value=code)
            for code, name in sorted(names.items(), key=lambda item: item[1])
            if query in name.lower() or query == code
        ][:25]

    @app_commands.command(
        name="translate", description="Translate text between languages"
    )
    @app_commands.describe(
        text="The text to translate",
        source="The language the text is written in",
        to="The language to translate into (defaults to English)",
    )
    @app_commands.autocomplete(source=languageAutocomplete, to=languageAutocomplete)
    @doughchecks.has_permissions(embed_links=True)
    async def translateSlash(
        self,
        interaction: discord.Interaction,
        text: app_commands.Range[str, 1, maxInput],
        source: str,
        to: str | None = None,
    ) -> None:
        await interaction.response.defer()
        embed = await self.getTranslationEmbed(text, source, to or defaultTarget)
        await interaction.followup.send(embed=embed)

    async def getTranslationEmbed(
        self, text: str, source: str, to: str
    ) -> discord.Embed:
        names = await self.ensureIndex()
        if not names:
            return self.errorEmbed(
                "Couldn't reach the Argos package index — try again in a moment."
            )

        unknown = [code for code in (source, to) if code not in names]
        if unknown:
            return self.errorEmbed(
                f"I have no model for `{'`, `'.join(unknown)}` — "
                "pick a language from the suggestions."
            )

        if source == to:
            return self.errorEmbed("Those are the same language.")

        if not await self.ensureInstalled(source, to):
            return self.errorEmbed(
                f"Argos has no model that can go {names[source]} → {names[to]}."
            )

        protected, titles = self.protectTitles(text)

        try:
            result = await asyncio.to_thread(translate.translate, protected, source, to)
        except (OSError, RuntimeError, ValueError) as error:
            return self.errorEmbed(f"Translation failed: `{error}`")

        if titles:
            result = self.restoreTitles(result, titles)

        embed = discord.Embed(color=discord.Color.fuchsia())
        embed.add_field(name=names[source], value=text[:fieldLimit], inline=False)
        embed.add_field(name=names[to], value=result[:fieldLimit], inline=False)
        embed.set_footer(
            text="Powered by Argos Translate",
            icon_url="https://m.doughmination.gay/img/search.png",
        )
        return embed

    async def ensureIndex(self) -> dict[str, str]:
        if self.languageNames:
            return self.languageNames

        async with self.lock:
            if self.languageNames:
                return self.languageNames
            try:
                names, pairs = await asyncio.to_thread(self.loadIndex)
            except (OSError, ValueError) as error:
                print(f"[translate] could not load package index: {error}")
                return {}
            self.languageNames = names
            self.pairs = pairs

        return self.languageNames

    def loadIndex(self) -> tuple[dict[str, str], set[tuple[str, str]]]:
        package.update_package_index()
        names: dict[str, str] = {}
        pairs: set[tuple[str, str]] = set()
        for pkg in package.get_available_packages():
            names.setdefault(pkg.from_code, pkg.from_name)
            names.setdefault(pkg.to_code, pkg.to_name)
            pairs.add((pkg.from_code, pkg.to_code))
        return names, pairs

    async def ensureInstalled(self, source: str, to: str) -> bool:
        async with self.lock:
            return await asyncio.to_thread(self.installPair, source, to)

    def installPair(self, source: str, to: str) -> bool:
        if self.translatable(source, to):
            return True

        if (source, to) in self.pairs:
            installed = package.install_package_for_language_pair(source, to)
        elif (source, "en") in self.pairs and ("en", to) in self.pairs:
            installed = package.install_package_for_language_pair(source, "en")
            installed &= package.install_package_for_language_pair("en", to)
        else:
            return False

        if installed:
            translate.get_installed_languages.cache_clear()

        return self.translatable(source, to)

    def protectTitles(self, text: str) -> tuple[str, list[str]]:
        titles: list[str] = []

        def swap(match: re.Match[str]) -> str:
            titles.append(match.group(0))
            return f"X{len(titles)}X"

        for opener, closer in titleBrackets:
            pattern = re.compile(
                f"{re.escape(opener)}[^{re.escape(closer)}]*{re.escape(closer)}"
            )
            text = pattern.sub(swap, text)
        return text, titles

    def restoreTitles(self, text: str, titles: list[str]) -> str:
        def swap(match: re.Match[str]) -> str:
            index = int(match.group(1)) - 1
            return titles[index] if 0 <= index < len(titles) else match.group(0)

        restored = placeholderPattern.sub(swap, text)
        missing = [title for title in titles if title not in restored]
        if missing:
            restored = f"{restored} {' '.join(missing)}".strip()
        return restored

    def translatable(self, source: str, to: str) -> bool:
        fromLang = translate.get_language_from_code(source)
        toLang = translate.get_language_from_code(to)
        if fromLang is None or toLang is None:
            return False
        return fromLang.get_translation(toLang) is not None

    def errorEmbed(self, message: str) -> discord.Embed:
        return discord.Embed(color=discord.Color.red(), description=f":x: {message}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Translate(bot))
