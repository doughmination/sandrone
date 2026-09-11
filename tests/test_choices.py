import asyncio
from types import SimpleNamespace

import pytest
from discord.ext import commands

from utils.choices import ChoiceSet, spellings

containers = ChoiceSet({"Audio": "mp3", "Video": "mp4"})
encoders = ChoiceSet({"Base64": "b64", "Caesar Cipher": "caesar"})
indents = ChoiceSet({"2 spaces": "2", "Tab": "tab"})


def convert(choiceSet: ChoiceSet, argument: str, *, param=None):
    ctx = SimpleNamespace(current_parameter=param)
    return asyncio.run(choiceSet.converter().convert(ctx, argument))


def test_spellings_cover_the_value_and_the_label() -> None:
    assert spellings("Audio", "mp3") == {"audio", "mp3"}


def test_spellings_cover_punctuated_forms_of_a_two_word_label() -> None:
    assert spellings("Caesar Cipher", "caesar") == {
        "caesar",
        "caesar cipher",
        "caesarcipher",
        "caesar-cipher",
        "caesar_cipher",
    }


@pytest.mark.parametrize("typed", ["audio", "Audio", "AUDIO", "aUdIo", "mp3", " mp3 "])
def test_the_label_and_the_value_both_convert_regardless_of_case(typed) -> None:
    assert convert(containers, typed) == "mp3"


def test_a_two_word_label_converts_by_any_of_its_spellings() -> None:
    for typed in ("Caesar Cipher", "caesar-cipher", "CAESAR_CIPHER", "caesar"):
        assert convert(encoders, typed) == "caesar"


def test_an_unknown_spelling_raises_so_optional_parameters_can_backtrack() -> None:
    with pytest.raises(commands.CommandError):
        convert(containers, "nonsense")


def test_the_failure_names_the_parameter_when_one_is_in_flight() -> None:
    param = commands.Parameter(
        name="type", kind=commands.Parameter.POSITIONAL_OR_KEYWORD
    )
    with pytest.raises(commands.BadLiteralArgument) as caught:
        convert(containers, "nonsense", param=param)
    assert caught.value.argument == "nonsense"
    assert caught.value.param.name == "type"


def test_the_slash_menu_only_ever_sees_labels_and_values() -> None:
    assert [(c.name, c.value) for c in containers.options] == [
        ("Audio", "mp3"),
        ("Video", "mp4"),
    ]


def test_resolve_falls_back_to_the_default_for_nothing_supplied() -> None:
    assert containers.resolve(None, "mp4") == "mp4"


def test_resolve_normalises_a_label_that_reached_it_unconverted() -> None:
    assert containers.resolve("Audio", "mp4") == "mp3"


def test_resolve_uses_the_default_rather_than_inventing_a_value() -> None:
    assert containers.resolve("nonsense", "mp4") == "mp4"


def test_a_label_whose_spelling_needs_quoting_still_resolves() -> None:
    assert indents.resolve("2 spaces", "2") == "2"
    assert indents.resolve("2spaces", "2") == "2"
