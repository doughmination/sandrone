import discord
from discord import app_commands
from discord.ext import commands


class TheGame(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="explain-the-game", description="You just lost the game haha!"
    )
    async def gameSlash(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        reply = await self.buildTheGameRules()
        await interaction.followup.send(embed=reply)

    async def buildTheGameRules(self) -> discord.Embed:
        embed = discord.Embed(color=discord.Color.fuchsia(), title="Rules of The Game")
        parts: list[str] = []
        parts.append("**Rule 1:**\nThe Game is 'The Game'.")
        parts.append(
            "\n\n**Rule 2:**\nThe object, or aim, of The Game is not to think about The Game."
        )
        parts.append(
            "\n\n**Rule 3:**\nIf you think about The Game, you have lost The Game."
        )
        parts.append(
            '\n\n**Rule 4:**\n(a) If you lose The Game, you must instantly declare it to everyone around you in some manner of communication, usually by exclaiming loudly "I\'ve lost The Game". Consequently, everyone else will then have thought of The Game, and subsequently lost it.\n(b) If someone tells you they have lost The Game, you yourself DO NOT need to declare this, as from the point where the first person loses The Game everyone in the vicinity has immunity for ten minutes. In these ten minutes you cannot lose The Game. The idea of the ten minute rule is that this allows everybody to once again forget about The Game.'
        )
        parts.append(
            "\n\n**Rule 5:**\nThis immunity expires exactly after ten minutes. If, after these ten minutes, you think about The Game then you have once again lost The Game and must declare."
        )
        parts.append(
            "\n\n**Rule 6**\n(a) There is no limit to the number of times you can lose The Game. (Once you begin, you are playing forever muhahahaha!!)\n(b) Some people think that they can simply 'not play' The Game. They are in denial and deserve a reality check. You cannot escape The Game once you are involved (unless you win-see Rule 7)."
        )
        parts.append(
            "\n\n**Rule 7:**\n(a) There is only one way to win The Game, and that is to truly and honestly forget about it completely.\n(b) This also means that if you do manage to win The Game, you will never know that you have won. This is because if you know you have won, then you have just thought about it (and consequently lost)."
        )
        parts.append(
            '\n\n**Rule 8:**\nIf you lose The Game, and someone (foolishly) asks "whats The Game?", please either explain it to them, or direct them toward this command, as an unspoken purpose to The Game is to get as many people playing as possible'
        )
        embed.description = "".join(parts)
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TheGame(bot))
