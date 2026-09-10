from types import SimpleNamespace

from sandrone import config
from sandrone.prefix import matchName, resolvePrefix


def test_matches_the_harbinger_name_case_insensitively() -> None:
    assert matchName("Marrionette ytdlp https://x") == "Marrionette "
    assert matchName("marrionette help") == "marrionette "
    assert matchName("MARRIONETTE help") == "MARRIONETTE "


def test_matches_the_canonical_spelling_too() -> None:
    assert matchName("Marionette help") == "Marionette "
    assert matchName("sandrone help") == "sandrone "


def test_returns_the_slice_verbatim_so_discord_py_can_strip_it() -> None:
    # discord.py compares prefixes against raw content, case-sensitively.
    content = "MaRrIoNeTtE kitty"
    matched = matchName(content)
    assert matched is not None
    assert content.startswith(matched)


def test_swallows_separators_between_the_name_and_the_command() -> None:
    assert matchName("Marrionette, kitty") == "Marrionette, "
    assert matchName("Marrionette:  kitty") == "Marrionette:  "


def test_ignores_sentences_that_merely_start_with_the_word() -> None:
    assert matchName("Marionettes are unsettling") is None
    assert matchName("Sandrones workshop") is None


def test_ignores_the_bare_name_with_no_command_behind_it() -> None:
    assert matchName("Marrionette") is None
    assert matchName("Marrionette   ") is None
    assert matchName("Marrionette,") is None


def test_ignores_unrelated_messages() -> None:
    assert matchName("hello there") is None
    assert matchName("") is None


def test_longest_name_wins_when_one_is_a_prefix_of_another() -> None:
    # config sorts longest-first; guard against a shorter name shadowing.
    assert config.prefixNames == sorted(config.prefixNames, key=len, reverse=True)


def fakeBot() -> SimpleNamespace:
    return SimpleNamespace(user=SimpleNamespace(id=123))


def test_mention_prefixes_are_always_offered() -> None:
    prefixes = resolvePrefix(fakeBot(), SimpleNamespace(content="hello"))
    assert prefixes == ["<@123> ", "<@!123> "]


def test_name_prefix_is_appended_to_the_mention_prefixes() -> None:
    prefixes = resolvePrefix(
        fakeBot(), SimpleNamespace(content="Marrionette bsky https://x")
    )
    assert prefixes == ["<@123> ", "<@!123> ", "Marrionette "]
