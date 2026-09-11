from discord import app_commands
from discord.ext import commands


def spellings(label: str, value: str) -> set[str]:
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
        if typed is None:
            return default
        return self.table.get(typed.lower(), default)
