"""Choice sets that read the same way in a dropdown and in a typed message.

A slash user picks "Audio" from a menu and never sees the ``mp3`` behind it, so
when they later type the command they type the label they remember. A bare
``Literal`` accepts only the raw value and matches case-sensitively, and on an
optional argument a mismatch doesn't even fail loudly — it backtracks to the
default and quietly does the wrong thing.

A ChoiceSet accepts the value, the label, and the obvious spellings of the
label, in any case, and yields the canonical value on both halves of a hybrid
command.
"""

from discord import app_commands
from discord.ext import commands


def spellings(label: str, value: str) -> set[str]:
    """Every form of one choice someone might reasonably type, lowercased."""
    lowered = label.lower()
    forms = {
        value.lower(),
        lowered,
        lowered.replace(" ", ""),
        lowered.replace(" ", "-"),
        lowered.replace(" ", "_"),
    }
    return {form for form in forms if form}


class ChoiceSet:
    """A ``{label: value}`` mapping usable on both halves of a hybrid command.

    ``options`` feeds ``@app_commands.choices`` and stays label-and-value only,
    so the slash menu is unchanged. ``converter`` is the parameter annotation;
    it accepts the wider spelling table and is never shown to anyone.
    """

    def __init__(self, choices: dict[str, str]) -> None:
        self.choices = choices
        self.values = tuple(dict.fromkeys(choices.values()))

        table: dict[str, str] = {}
        for label, value in choices.items():
            for form in spellings(label, value):
                table.setdefault(form, value)
        self.table = table

        self.converter = self._buildConverter()

    def _buildConverter(self) -> type[commands.Converter]:
        table, values = self.table, self.values

        class Choice(commands.Converter):
            async def convert(self, ctx: commands.Context, argument: str) -> str:
                match = table.get(argument.strip().lower())
                if match is not None:
                    return match

                # BadLiteralArgument so the usage panel can name both the value
                # and the parameter. It is a CommandError either way, so an
                # optional parameter still backtracks and takes its default.
                if ctx.current_parameter is not None:
                    raise commands.BadLiteralArgument(
                        ctx.current_parameter, values, [], argument
                    )
                raise commands.BadArgument(f"{argument!r} is not a valid choice")

        return Choice

    @property
    def options(self) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=label, value=value)
            for label, value in self.choices.items()
        ]

    def resolve(self, typed: str | None, default: str) -> str:
        """The canonical value for whatever arrived, or ``default`` for nothing.

        The converter has normally done the work already; this covers the
        not-supplied case and stays correct if a raw value slips through.
        """
        if typed is None:
            return default
        return self.table.get(typed.lower(), default)
