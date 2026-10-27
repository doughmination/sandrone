from commands.cogs.lookups import dig
from discord import ui
import re


def textOf(view: ui.LayoutView) -> str:
    return "\n".join(
        item.content
        for item in view.walk_children()
        if isinstance(item, ui.TextDisplay)
    )


def selectsOf(view: ui.LayoutView) -> list[ui.Select]:
    return [
        item
        for item in view.walk_children()
        if isinstance(item, ui.Select)
    ]


def sample() -> dig.DigResult:
    return dig.DigResult(
        "example.com",
        (
            dig.RecordSet("A", 300, ("93.184.215.14",)),
            dig.RecordSet("TXT", 60, ('"v=spf1 -all"', '"a```b"')),
        ),
    )


def test_normalise_name_keeps_subdomains() -> None:
    assert dig.normaliseName("https://WWW.Example.com:8080/x?y") == (
        "www.example.com"
    )
    assert dig.normaliseName("example.com.") == "example.com"


def test_overview_lists_every_type() -> None:
    view = dig.renderResult("example.com", sample())
    text = textOf(view)

    assert "> **A** · 1 record · TTL 300s" in text
    assert "> **TXT** · 2 records · TTL 60s" in text
    assert "All Records ·" in text


def test_record_page_shows_one_type_and_defuses_backticks() -> None:
    view = dig.renderResult("example.com", sample(), "TXT")
    text = textOf(view)

    assert "93.184.215.14" not in text
    assert "a```b" not in text
    selects = selectsOf(view)
    match = re.fullmatch(dig.PAGE_TEMPLATE, selects[0].custom_id)
    assert match and match["target"] == "example.com"
    assert [o.value for o in selects[0].options if o.default] == ["TXT"]


def test_unknown_page_falls_back_to_overview() -> None:
    view = dig.renderResult("example.com", sample(), "MX")
    text = textOf(view)
    assert "All Records ·" in text
