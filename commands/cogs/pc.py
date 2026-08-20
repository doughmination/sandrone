import discord
from discord import app_commands
from discord.ext import commands

mainSpecs = {
    "cpu": "AMD Ryzen 9 9950x3d",
    "gpu": "AMD Radeon RX 7900XTX",
    "memory": "Corsair Vengance 64GB DDR5-6000 CL-40",
    "motherboard": "Gigabyte B650M Aorus Elite",
    "case": "Montech XR ATX"
}

storage = {
    "primary-ssd": "Arch Linux (1TB NVMe)",
    "secondary-ssd": "Windows 11 (1TB NVMe)",
    "deep-storage": "Seagate Exos X14 12TB"
}

peripherals = {
    "monitor": "Gigabyte G34WQCP 34' 180Hz 1440x3440",
    "mouse": "Logitech G502 X PLUS",
    "keyboard": "Akko Sakura Miku",
}

pcPages = [
    ("Main Specs", mainSpecs),
    ("Storage", storage),
    ("Peripherals", peripherals),
]


def buildPcEmbed(index: int) -> discord.Embed:
    title, specs = pcPages[index]
    embed = discord.Embed(title=title, color=discord.Color.fuchsia())
    for name, value in specs.items():
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text=f"Page {index + 1}/{len(pcPages)}")
    return embed


class PcView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=120)
        self.index = 0
        self.message: discord.Message | None = None
        self._updateButtons()

    def _updateButtons(self) -> None:
        self.leftButton.disabled = self.index == 0
        self.rightButton.disabled = self.index == len(pcPages) - 1

    @discord.ui.button(emoji="<:rem:1539939307144613958>", style=discord.ButtonStyle.secondary)
    async def leftButton(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.index -= 1
        self._updateButtons()
        await interaction.response.edit_message(embed=buildPcEmbed(self.index), view=self)

    @discord.ui.button(emoji="<:ram:1539939306167337060>", style=discord.ButtonStyle.secondary)
    async def rightButton(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.index += 1
        self._updateButtons()
        await interaction.response.edit_message(embed=buildPcEmbed(self.index), view=self)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            await self.message.edit(view=self)


class Pc(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="pcspecs", description="Get the owner's PC Specs and setup")
    async def pcSlash(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        view = PcView()
        message = await interaction.followup.send(embed=buildPcEmbed(0), view=view, wait=True)
        view.message = message


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Pc(bot))
