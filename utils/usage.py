"""Turn a badly-formed invocation into a panel showing the right format.

Prefix commands have no dropdowns or client-side validation, so a mistyped
argument needs an answer that teaches the shape of the command rather than
just reporting a failure. Everything here is derived from the command itself —
the signature, the ``@app_commands.describe`` text, and the choice lists — so a
new command documents itself with no extra work.
"""

import inspect
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin

import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import MISSING

from utils import components
from utils.markdown import codeBlock

# Beyond this, an inline "a|b|c" list crowds the usage line and the argument
# gets shown by name instead, with the options spelled out underneath.
inlineChoiceLimit = 32


def unwrapOptional(converter: Any) -> Any:
    """``Literal["a"] | None`` -> ``Literal["a"]``; anything else unchanged."""
    if get_origin(converter) in (Union, UnionType):
        real = [arg for arg in get_args(converter) if arg is not type(None)]
        if len(real) == 1:
            return real[0]
    return converter


def literalValues(converter: Any) -> tuple[str, ...]:
    inner = unwrapOptional(converter)
    if get_origin(inner) is Literal:
        return tuple(str(value) for value in get_args(inner))
    return ()


def rangeOf(converter: Any) -> commands.Range | None:
    inner = unwrapOptional(converter)
    return inner if isinstance(inner, commands.Range) else None


def isConsumeRest(param: commands.Parameter) -> bool:
    return param.kind is inspect.Parameter.KEYWORD_ONLY


def appParameters(command: commands.Command) -> dict[str, app_commands.Parameter]:
    """Slash-side metadata for the command, keyed by parameter name."""
    app = getattr(command, "app_command", None)
    if app is None:
        return {}
    return {param.name: param for param in app.parameters}


def optionValues(
    param: commands.Parameter, appParam: app_commands.Parameter | None
) -> tuple[str, ...]:
    """The canonical options for a parameter.

    A ChoiceSet widens its ``Literal`` with label spellings so the prefix parser
    accepts them; those are for parsing, not for display, so the slash choices
    win wherever they exist.
    """
    if appParam is not None and appParam.choices is not MISSING and appParam.choices:
        return tuple(str(choice.value) for choice in appParam.choices)
    return literalValues(param.converter)


def token(param: commands.Parameter, appParam: app_commands.Parameter | None) -> str:
    """One parameter as it should appear in the usage line."""
    options = optionValues(param, appParam)
    inner = param.name
    if options:
        joined = "|".join(options)
        if len(joined) <= inlineChoiceLimit:
            inner = joined

    if isConsumeRest(param):
        inner += "…"

    return f"<{inner}>" if param.required else f"[{inner}]"


def signatureFor(command: commands.Command) -> str:
    appParams = appParameters(command)
    return " ".join(
        token(param, appParams.get(name))
        for name, param in command.clean_params.items()
    )


def usageLine(ctx: commands.Context) -> str:
    parts = [f"{ctx.clean_prefix}{ctx.command.qualified_name}"]
    signature = signatureFor(ctx.command)
    if signature:
        parts.append(signature)
    return " ".join(parts)


def choiceLine(param: commands.Parameter, appParam: app_commands.Parameter | None) -> str:
    """The options for a parameter, preferring the slash menu's display names."""
    options = optionValues(param, appParam)
    if not options:
        return ""

    labels: dict[str, str] = {}
    if appParam is not None and appParam.choices is not MISSING:
        labels = {str(choice.value): choice.name for choice in appParam.choices}

    rendered = [
        f"`{value}` ({labels[value]})" if value in labels else f"`{value}`"
        for value in options
    ]
    return "One of: " + ", ".join(rendered)


def limitLine(param: commands.Parameter) -> str:
    bounds = rangeOf(param.converter)
    if bounds is None:
        return ""

    unit = "characters" if bounds.annotation is str else ""
    if bounds.min is not None and bounds.max is not None:
        return f"Between {bounds.min} and {bounds.max} {unit}".strip() + "."
    if bounds.max is not None:
        return f"At most {bounds.max} {unit}".strip() + "."
    if bounds.min is not None:
        return f"At least {bounds.min} {unit}".strip() + "."
    return ""


def argumentFields(command: commands.Command) -> list[tuple[str, str]]:
    appParams = appParameters(command)
    fields: list[tuple[str, str]] = []

    for name, param in command.clean_params.items():
        appParam = appParams.get(name)
        label = f"`{name}`" if param.required else f"`{name}` · optional"

        lines = []
        if appParam is not None and appParam.description:
            description = str(appParam.description)
            if description != "…":  # discord.py's placeholder for undescribed
                lines.append(description)
        for extra in (choiceLine(param, appParam), limitLine(param)):
            if extra:
                lines.append(extra)
        if isConsumeRest(param):
            lines.append("Takes the rest of the message, so it can have spaces.")

        fields.append((label, "\n".join(lines) or "—"))

    return fields


# What a converter is actually asking for, when the failure is a type mismatch.
expectedKinds: dict[Any, str] = {
    int: "a whole number",
    float: "a number",
    bool: "a yes or a no",
    discord.Member: "a member of this server",
    discord.User: "a user",
    discord.TextChannel: "a channel",
    discord.Role: "a role",
}


def expectedKind(converter: Any) -> str:
    inner = unwrapOptional(converter)
    bounds = rangeOf(inner)
    if bounds is not None:
        inner = bounds.annotation
    return expectedKinds.get(inner, "")


def describeProblem(ctx: commands.Context, error: Exception) -> str:
    """One sentence naming what went wrong, in terms of a parameter."""
    if isinstance(error, commands.MissingRequiredArgument):
        return f"You didn't give me `{error.param.name}`."

    if isinstance(error, commands.MissingRequiredAttachment):
        return f"`{error.param.name}` needs a file attached to the message."

    if isinstance(error, commands.BadLiteralArgument):
        return f"`{error.argument}` isn't one of the options for `{error.param.name}`."

    if isinstance(error, commands.RangeError):
        name = ctx.current_parameter.name if ctx.current_parameter else "That"
        if error.minimum is not None and error.maximum is not None:
            return f"`{name}` has to be between {error.minimum} and {error.maximum}."
        if error.maximum is not None:
            return f"`{name}` has to be at most {error.maximum}."
        return f"`{name}` has to be at least {error.minimum}."

    if isinstance(error, commands.BadBoolArgument):
        return f"`{error.argument}` isn't a yes or a no."

    if isinstance(error, (commands.MemberNotFound, commands.UserNotFound)):
        return f"I couldn't find anyone called `{error.argument}`."

    if isinstance(error, commands.ChannelNotFound):
        return f"I couldn't find a channel called `{error.argument}`."

    if isinstance(error, commands.BadUnionArgument):
        return f"`{error.param.name}` isn't in a form I recognise."

    if isinstance(error, commands.TooManyArguments):
        # Whatever is left in the view is the part that didn't convert — often a
        # choice spelled wrong, which is more useful to name than to count.
        view = getattr(ctx, "view", None)
        leftover = view.buffer[view.index :].strip() if view is not None else ""
        if leftover:
            return f"I didn't know what to do with `{leftover}`."
        return "That's more than this one takes."

    if isinstance(error, commands.ArgumentParsingError):
        return "I couldn't read that — check for an unclosed quote."

    # The slash path converts through transformers, which fail with their own
    # error type rather than a UserInputError.
    if isinstance(error, app_commands.TransformerError):
        return f"`{error.value}` isn't something I could use there."

    if ctx.current_parameter is not None:
        name = ctx.current_parameter.name
        expected = expectedKind(ctx.current_parameter.converter)
        if expected:
            return f"`{name}` has to be {expected}."
        return f"`{name}` wasn't something I could use."

    return "That isn't the right shape."


def footerFor(ctx: commands.Context) -> str:
    parts = ["`<>` required", "`[]` optional"]
    if ctx.command.aliases:
        parts.append("also " + ", ".join(f"`{a}`" for a in ctx.command.aliases))
    parts.append(f"or use `/{ctx.command.qualified_name}`")
    return " · ".join(parts)


def usagePanel(ctx: commands.Context, error: Exception) -> components.Panel:
    body = f":x: {describeProblem(ctx, error)}\n\n{codeBlock(usageLine(ctx))}"
    return components.panel(
        title=f"How to use {ctx.command.qualified_name}",
        body=body,
        fields=argumentFields(ctx.command),
        footer=footerFor(ctx),
        color=components.RED,
    )
