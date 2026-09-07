import discord
from discord import app_commands
from discord.ext import commands

from sandrone import doughchecks
from utils import components

mainSpecs = {
    "CPU": "[AMD Ryzen 9 9950X3D](https://uk.pcpartpicker.com/product/Pk62FT/amd-ryzen-9-9950x3d-43-ghz-16-core-processor-100-100000719wof)",
    "GPU": "[XFX AMD Radeon RX 7900XTX](https://uk.pcpartpicker.com/product/GtXJ7P/xfx-speedster-merc-310-black-edition-radeon-rx-7900-xtx-24-gb-video-card-rx-79xmercb9)",
    "Memory": "[Corsair Vengance 64GB DDR5-6000 CL-40](https://uk.pcpartpicker.com/product/LWVmP6/corsair-vengeance-64-gb-2-x-32-gb-ddr5-6000-cl40-memory-cmk64gx5m2b6000z40)",
    "Motherboard": "[Gigabyte B650M Aorus Elite](https://uk.pcpartpicker.com/product/Q8KnTW/gigabyte-b850m-aorus-elite-wifi6e-ice-micro-atx-am5-motherboard-b850m-aorus-elite-wifi6e-ice)",
    "Case": "[Montech XR ATX](https://uk.pcpartpicker.com/product/nhbRsY/montech-xr-atx-mid-tower-case-xr-w)",
    "Cooler": "[Thermalright Aqua Elite V3](https://uk.pcpartpicker.com/product/YXFmP6/thermalright-aqua-elite-v3-6617-cfm-liquid-cpu-cooler-aqua-elite-360-white-v3)",
}

storage = {
    "Primary SSD": "Arch Linux KDE (1TB NVMe) - [Acer Predator GM7](https://uk.pcpartpicker.com/product/YPKscf/acer-predator-gm7-1-tb-m2-2280-pcie-40-x4-nvme-solid-state-drive-bl9bwwr118)",
    "Secondary SSD": "Windows 11 (1TB NVMe) - WD SN56\u200b0 SDDPNQE-\u200b1T00-1002",
    "Deep Storage": "Photos and Recordings - [Seagate Exos X14 12TB](https://uk.pcpartpicker.com/product/fmfhP6/seagate-exos-x14-12-tb-35-7200-rpm-internal-hard-drive-st12000nm0008)",
}

peripherals = {
    "Monitor": "[Gigabyte G34WQCP 34' 180Hz 1440x3440](https://www.gigabyte.com/Monitor/G34WQCP-rev-10)",
    "Mouse": "[Logitech G502 X PLUS](https://www.logitechg.com/en-us/shop/p/g502-x-plus-wireless-lightforce)",
    "Keyboard": "[Akko Sakura ](https://en.akkogear.com/product/sakura-miku-5108b-plus-mechanical-keyboard/)",
}

laptopSpecs = {
    "Type": "[ThinkPad T14s Gen 2a](https://nanoreview.net/en/laptop/lenovo-thinkpad-t14s-gen-2-amd?m=c%7e1362.d%7e1.r%7e16)",
    "C/GPU": "[AMD Ryzen 5 PRO 5650U](https://www.notebookcheck.net/AMD-Ryzen-5-PRO-5650U-Processor-Benchmarks-and-Specs.527811.0.html) /w Intergrated Graphics",
    "OS": "[Artix Linux](https://artixlinux.org/)",
    "WM": "[SwayFx](https://github.com/wlrfx/swayfx)",
    "Shell": "[Bash](https://www.gnu.org/software/bash)",
    "System Init": "[Runit](https://smarden.org/runit)",
    "Terminal": "[Kitty](https://sw.kovidgoyal.net/kitty/)",
}

pcPages = [
    ("Main PC Specs", mainSpecs),
    ("Storage", storage),
    ("Peripherals", peripherals),
    ("Laptop Specs", laptopSpecs),
]


def pcPageBody(index: int) -> str:
    title, specs = pcPages[index]
    lines = [f"## {title}", ""]
    lines += [f"**{name}**\n{value}" for name, value in specs.items()]
    lines += ["", f"-# Page {index + 1}/{len(pcPages)}"]
    return "\n".join(lines)


class PcNav(discord.ui.ActionRow["PcView"]):
    @discord.ui.button(
        emoji="<:rem:1539939307144613958>", style=discord.ButtonStyle.secondary
    )
    async def leftButton(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        view = self.view
        if view is None:
            return
        view.index -= 1
        view.render()
        await interaction.response.edit_message(view=view)

    @discord.ui.button(
        emoji="<:ram:1539939306167337060>", style=discord.ButtonStyle.secondary
    )
    async def rightButton(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        view = self.view
        if view is None:
            return
        view.index += 1
        view.render()
        await interaction.response.edit_message(view=view)


class PcView(discord.ui.LayoutView):
    def __init__(self, authorId: int) -> None:
        super().__init__(timeout=120)
        self.authorId = authorId
        self.index = 0
        self.message: discord.Message | None = None

        self.box = discord.ui.Container(accent_colour=components.FUCHSIA)
        self.nav = PcNav()

        self.add_item(self.box)
        self.render()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.authorId:
            await interaction.response.send_message(
                "Only the person who ran this command can use these buttons.",
                ephemeral=True,
            )
            return False
        return True

    def render(self) -> None:
        self.nav.leftButton.disabled = self.index == 0
        self.nav.rightButton.disabled = self.index == len(pcPages) - 1

        self.box.clear_items()
        self.box.add_item(discord.ui.TextDisplay(pcPageBody(self.index)))
        self.box.add_item(self.nav)

    async def on_timeout(self) -> None:
        self.render()
        self.nav.leftButton.disabled = True
        self.nav.rightButton.disabled = True
        if self.message is not None:
            await self.message.edit(view=self)


class Pc(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="pcspecs", description="Get the owner's PC Specs and setup"
    )
    @doughchecks.has_permissions(embed_links=True)
    async def pcSlash(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        view = PcView(interaction.user.id)
        view.message = await interaction.followup.send(view=view, wait=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Pc(bot))
