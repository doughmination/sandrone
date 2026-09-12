from types import SimpleNamespace
from typing import Any, cast

import aiohttp
import discord
import pytest
from discord.ext import commands

from utils import errors


@pytest.fixture(autouse=True)
def store(tmp_path):
    errors.db.path = tmp_path / "errors.jp"
    errors.db.reload()
    return errors.db


def boom(message: str = "kaboom") -> Exception:
    try:
        raise RuntimeError(message)
    except RuntimeError as caught:
        return caught


def logged(error: Exception, **kwargs) -> errors.Entry:
    entry = errors.record(error, **kwargs)
    assert entry is not None
    return entry


def codeFor(error: Exception) -> str:
    return errors.codeOf(error, "slash command")


def test_a_recorded_error_keeps_what_debug_needs_to_show() -> None:
    errors.record(
        boom(),
        source="prefix command",
        command="qr",
        guild=None,
        channel=None,
        user=None,
    )

    entry = errors.recent()[0]
    assert entry["kind"] == "RuntimeError"
    assert entry["text"] == "kaboom"
    assert entry["command"] == "qr"
    assert "RuntimeError: kaboom" in entry["trace"]


def test_the_newest_error_comes_first() -> None:
    for name in ("first", "second", "third"):
        errors.record(boom(name), source="event on_message")

    assert [entry["text"] for entry in errors.recent()] == ["third", "second", "first"]


def test_the_log_stops_growing_at_the_keep_limit() -> None:
    for index in range(errors.keepLimit + 10):
        errors.record(boom(), source="event on_message", command="cmd" + "a" * index)

    assert errors.count() == errors.keepLimit


def test_missing_permissions_are_pulled_out_of_the_error() -> None:
    errors.record(
        commands.BotMissingPermissions(["attach_files", "embed_links"]),
        source="slash command",
        command="pride",
    )

    assert errors.recent()[0]["missing"] == ["attach_files", "embed_links"]


def test_entries_survive_a_reload_from_disk() -> None:
    errors.record(boom("written"), source="incident loop")
    errors.db.reload()

    assert errors.recent()[0]["text"] == "written"


def test_clearing_reports_how_many_went() -> None:
    errors.record(boom(), source="event on_ready")

    assert errors.clear() == 1
    assert errors.recent() == []
    assert errors.clear() == 0


def test_a_broken_log_never_replaces_the_error_it_was_logging(monkeypatch) -> None:
    def refuse(*args, **kwargs):
        raise OSError("disk is on fire")

    monkeypatch.setattr(errors.db, "save", refuse)

    assert errors.record(boom(), source="event on_message") is None


# -- references ----------------------------------------------------------


def test_a_fault_reads_as_a_code_and_a_digest() -> None:
    ref = logged(boom(), source="event on_message")["ref"]
    code, _, digest = ref.partition("-")

    assert code in errors.codeMeanings
    assert len(digest) == errors.refLength
    assert set(digest) <= set(errors.refAlphabet)
    assert not set(digest) & set("ILOU")


def test_the_same_fault_twice_keeps_one_reference_and_counts_up() -> None:
    first = logged(boom(), source="slash command", command="qr")
    second = logged(boom(), source="slash command", command="qr")

    assert second["ref"] == first["ref"]
    assert errors.count() == 1
    assert second["count"] == 2
    assert second["first"] == first["first"]


def test_the_same_fault_in_a_different_command_gets_its_own_reference() -> None:
    first = logged(boom(), source="slash command", command="qr")
    other = logged(boom(), source="slash command", command="pride")

    assert other["ref"] != first["ref"]
    assert errors.count() == 2


def test_ids_in_the_message_do_not_split_one_fault_into_many() -> None:
    mine = logged(boom("member 777888999000111222 is gone"), source="command")
    yours = logged(boom("member 111222333444555666 is gone"), source="command")

    assert yours["ref"] == mine["ref"]
    assert yours["count"] == 2


def test_a_quoted_fault_is_found_however_it_was_typed() -> None:
    ref = logged(boom(), source="event on_message")["ref"]
    code, _, digest = ref.partition("-")

    typings = (
        ref,
        ref.lower(),
        f"`{ref}`",
        f"#{ref}",
        f"  {ref} ",
        ref.replace("-", " "),
        ref.replace("-", "—"),
        digest,
        code,
    )
    for typed in typings:
        assert errors.find(typed) is not None, typed

    assert errors.find("ZZZZ") is None
    assert errors.find("") is None


def test_the_note_carries_the_reference_to_whoever_hit_the_error() -> None:
    entry = logged(boom(), source="slash command", command="qr")

    assert entry["ref"] in errors.note(entry)
    assert errors.note(None) == ""


# -- codes ---------------------------------------------------------------


def test_a_missing_permission_is_a_workshop_fault() -> None:
    entry = logged(
        commands.BotMissingPermissions(["attach_files"]),
        source="slash command",
        command="qr",
    )

    assert entry["code"] == "WORKSHOP"
    assert entry["ref"].startswith("WORKSHOP-")


def test_discord_refusing_is_told_apart_from_discord_breaking() -> None:
    response = cast(Any, SimpleNamespace(status=403, reason="Forbidden"))

    forbidden = logged(discord.Forbidden(response, "no"), source="slash command")
    broken = logged(discord.DiscordServerError(response, "oh dear"), source="command")

    assert forbidden["code"] == "WORKSHOP"
    assert broken["code"] == "STRINGS"


def test_the_outside_world_and_the_disk_get_their_own_codes() -> None:
    assert codeFor(aiohttp.ClientError("no route")) == "BLIZZARD"
    assert codeFor(TimeoutError("too slow")) == "BLIZZARD"
    assert codeFor(OSError("disk is on fire")) == "FOUNDRY"
    assert codeFor(KeyError("content")) == "BLUEPRINT"
    assert codeFor(commands.MemberNotFound("nobody")) == "VANISHED"


def test_an_unknown_fault_depends_on_whether_a_command_was_running() -> None:
    assert errors.codeOf(boom(), "slash command") == errors.fallbackCode
    assert errors.codeOf(boom(), "event on_message") == errors.loneWorkCode
    assert errors.codeOf(boom(), "incident loop") == errors.loneWorkCode


def test_every_code_that_can_be_issued_has_a_meaning() -> None:
    issuable = {name for name, _, _ in errors.codes}
    issuable |= {errors.fallbackCode, errors.loneWorkCode}

    assert issuable == set(errors.codeMeanings)


def test_faults_can_be_pulled_out_by_their_code() -> None:
    logged(
        commands.BotMissingPermissions(["embed_links"]), source="command", command="a"
    )
    logged(boom(), source="slash command", command="b")

    assert [entry["code"] for entry in errors.byCode("workshop")] == ["WORKSHOP"]
    assert errors.byCode("BLIZZARD") == []
