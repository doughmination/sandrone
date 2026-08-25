import discord
from discord import app_commands
from discord.ext import commands

xSnips = {
    "adb": "Starting December 5, 2025, the active developer badge has been **removed**, and is **no longer** obtainable. There are also *no* plans for a new badge replacing this.",
    "refresh": "To refresh your client to fix bugs or reload commands, use:\nControl + R on Windows and Linux\nCommand(⌘) + R on Mac\nSwipe clear and reopen on Mobile",
    "pluralkit": "<@466378653216014359> is a bot used by plural systems to proxy their messages as their system members!\nYou can find more on the bot [online](<https://pluralkit.me>)",
    "plural": "<@1291501048493768784> is a bot used by plural systems to proxy their messages as their system members!\nYou can find more on the bot [online](<https://plural.gg>)",
    "plurality": "Plurality (or multiplicity) is the existence of multiple self-aware entities inside one physical brain.\nYou can find some simple information [here](<https://morethanone.info>)\nand some more advanced info [here](<https://pluralpedia.org/w/Main_Page>)",
    "userproxies": "You can setup a Userproxy using this guide <https://youtu.be/spRkTssPCqg>!",
}


class Snippets(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def snippetAuto(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        result = []
        for name in xSnips:
            if current.lower() in name.lower():
                result.append(app_commands.Choice(name=name, value=name))
        return result[:25]

    @app_commands.command(name="snippet", description="repost a commonly used snippet")
    @app_commands.describe(snip="The snippet to repos")
    @app_commands.autocomplete(snip=snippetAuto)
    async def snippetSlash(self, interaction: discord.Interaction, snip: str) -> None:
        await interaction.response.defer()
        embed = await self.getSnippetEmbed(snip)
        await interaction.followup.send(embed=embed)

    async def getSnippetEmbed(self, snip: str) -> discord.Embed:
        embed = discord.Embed(color=discord.Color.fuchsia())
        reply = xSnips.get(snip)
        embed.add_field(name=" ", value=reply)
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Snippets(bot))
