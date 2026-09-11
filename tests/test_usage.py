from types import SimpleNamespace
from typing import Literal

import pytest
from discord import app_commands, ui
from discord.ext import commands

from utils import usage

Method = Literal["b64", "b32", "rot13", "caesar"]
LongStyle = Literal["lower", "upper", "title", "camel", "pascal", "snake", "kebab"]


@commands.hybrid_command(name="sample", description="A sample", aliases=["sam"])
@app_commands.describe(
    method="The encoding algorithm", text="What do you want to encode?"
)
@app_commands.choices(
    method=[
        app_commands.Choice(name="Base64", value="b64"),
        app_commands.Choice(name="Base32", value="b32"),
        app_commands.Choice(name="Rot13", value="rot13"),
        app_commands.Choice(name="Caesar Cipher", value="caesar"),
    ]
)
async def sample(
    ctx: commands.Context,
    method: Method | None = None,
    *,
    text: commands.Range[str, 1, 500],
) -> None: ...


@commands.hybrid_command(name="wide")
async def wide(ctx: commands.Context, style: LongStyle) -> None: ...


@commands.hybrid_command(name="counted")
async def counted(ctx: commands.Context, amount: int) -> None: ...


@commands.hybrid_command(name="bare")
async def bare(ctx: commands.Context) -> None: ...


def context(command, *, prefix="Marrionette ", current=None) -> SimpleNamespace:
    return SimpleNamespace(
        clean_prefix=prefix, command=command, current_parameter=current
    )


def textOf(panel) -> str:
    return "\n".join(
        child.content
        for child in panel.children[0].children
        if isinstance(child, ui.TextDisplay)
    )


def test_required_and_optional_are_bracketed_differently() -> None:
    assert usage.signatureFor(sample) == "[b64|b32|rot13|caesar] <text…>"


def test_consume_rest_parameters_are_marked_with_an_ellipsis() -> None:
    assert "<text…>" in usage.signatureFor(sample)


def test_a_long_choice_list_falls_back_to_the_parameter_name() -> None:
    assert usage.signatureFor(wide) == "<style>"


def test_commands_without_parameters_have_an_empty_signature() -> None:
    assert usage.signatureFor(bare) == ""


def test_usage_line_uses_the_prefix_that_was_actually_typed() -> None:
    assert usage.usageLine(context(bare)) == "Marrionette bare"
    assert usage.usageLine(context(bare, prefix="/")) == "/bare"


def test_choices_are_listed_with_their_slash_menu_labels() -> None:
    fields = dict(usage.argumentFields(sample))
    assert "`b64` (Base64)" in fields["`method` · optional"]
    assert "Caesar Cipher" in fields["`method` · optional"]


def test_describe_text_and_range_bounds_reach_the_argument_list() -> None:
    fields = dict(usage.argumentFields(sample))
    assert "What do you want to encode?" in fields["`text`"]
    assert "Between 1 and 500 characters." in fields["`text`"]


def test_optional_parameters_are_labelled_as_such() -> None:
    labels = [label for label, _ in usage.argumentFields(sample)]
    assert labels == ["`method` · optional", "`text`"]


def test_missing_argument_names_the_parameter() -> None:
    param = sample.clean_params["text"]
    problem = usage.describeProblem(
        context(sample), commands.MissingRequiredArgument(param)
    )
    assert problem == "You didn't give me `text`."


def test_bad_choice_names_both_the_value_and_the_parameter() -> None:
    param = wide.clean_params["style"]
    error = commands.BadLiteralArgument(param, ("lower", "upper"), [], "sneak")
    assert usage.describeProblem(context(wide), error) == (
        "`sneak` isn't one of the options for `style`."
    )


def test_range_errors_quote_the_bounds() -> None:
    param = sample.clean_params["text"]
    error = commands.RangeError("x" * 900, minimum=1, maximum=500)
    problem = usage.describeProblem(context(sample, current=param), error)
    assert problem == "`text` has to be between 1 and 500."


def test_type_mismatches_say_what_was_expected() -> None:
    param = counted.clean_params["amount"]
    problem = usage.describeProblem(
        context(counted, current=param), commands.BadArgument("nope")
    )
    assert problem == "`amount` has to be a whole number."


def test_unrecognised_failures_still_produce_a_sentence() -> None:
    assert usage.describeProblem(context(bare), commands.BadArgument("?"))


def test_footer_lists_aliases_and_the_slash_form() -> None:
    footer = usage.footerFor(context(sample))
    assert "`<>` required" in footer
    assert "`sam`" in footer
    assert "/sample" in footer


def test_panel_carries_the_problem_the_usage_and_the_arguments() -> None:
    param = sample.clean_params["text"]
    panel = usage.usagePanel(
        context(sample), commands.MissingRequiredArgument(param)
    )
    body = textOf(panel)

    assert "You didn't give me `text`." in body
    assert "Marrionette sample [b64|b32|rot13|caesar] <text…>" in body
    assert "The encoding algorithm" in body


@pytest.mark.parametrize("command", [sample, wide, counted, bare])
def test_every_panel_stays_within_the_components_v2_text_cap(command) -> None:
    panel = usage.usagePanel(context(command), commands.BadArgument("x"))
    assert len(textOf(panel)) < 4000
