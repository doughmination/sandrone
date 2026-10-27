from commands.cogs.lookups import whois
import datetime as dt
from discord import ui
import re


def selectsOf(view: ui.LayoutView) -> list[ui.Select]:
    return [
        item
        for item in view.walk_children()
        if isinstance(item, ui.Select)
    ]


def test_normalise_query_strips_url_noise() -> None:
    assert (
        whois.normaliseQuery("https://www.Example.com:443/path?q=1")
        == "example.com"
    )
    assert whois.normaliseQuery("someone@example.org") == "example.org"


def test_rdap_candidates_go_longest_first_and_stay_bounded() -> None:
    assert whois.rdapCandidates("www.example.co.uk") == [
        ("www.example.co", "uk"),
        ("example.co", "uk"),
        ("co", "uk"),
    ]
    assert len(whois.rdapCandidates("a.b.c.d.e.f.example.com")) == (
        whois.maxRdapLookups
    )
    assert whois.rdapCandidates("localhost") == []


def test_redacted_values_count_as_placeholders() -> None:
    assert whois.isPlaceholder("REDACTED FOR PRIVACY")
    assert whois.isPlaceholder("Data Protected")
    assert not whois.isPlaceholder("Markmonitor Inc.")


def test_first_value_skips_redacted_entries() -> None:
    fields = {"registrant organization": ["REDACTED", "Example Ltd"]}
    assert (
        whois.firstValue(fields, ("registrant organization",))
        == "Example Ltd"
    )


def test_epp_codes_from_rdap_and_port_43_agree() -> None:
    assert whois.eppCode("client transfer prohibited") == (
        "clientTransferProhibited"
    )
    assert whois.eppCode(
        "clientTransferProhibited https://icann.org/epp#x"
    ) == ("clientTransferProhibited")
    assert "icann.org/epp#ok" in whois.formatStatus("ok")
    assert whois.formatStatus("connect") == "`connect`"


def test_rdap_pages_never_leak_personal_contacts() -> None:
    record = {
        "domain_name": "example.gay",
        "registrar_name": "NAMECHEAP INC",
        "registrar_phone": "tel:+1.6613102107",
        "registrant_name": "Some Person",
        "registrant_email": "person@example.com",
        "registrant_address": "1 Home Street",
        "registrant_phone": "tel:+44.0000000000",
        "technical_email": "person@example.com",
        "abuse_email": "abuse@namecheap.com",
        "created_date": dt.datetime(2026, 3, 15, tzinfo=dt.UTC),
        "status": ["client transfer prohibited"],
        "nameservers": ["NS1.EXAMPLE.COM."],
    }

    pages = {page.key: page for page in whois.rdapPages(record)}
    rendered = "\n".join(page.body for page in pages.values())

    assert list(pages) == ["overview", "status", "nameservers", "contacts"]
    assert "> **Registrar**: NAMECHEAP INC" in pages["overview"].body
    assert ":R>" in pages["overview"].body
    assert "`ns1.example.com`" in pages["nameservers"].body
    assert "+1.6613102107" in pages["contacts"].body
    for leaked in ("Some Person", "person@example.com", "Home Street"):
        assert leaked not in rendered


def test_rdap_pages_drop_redacted_registrant() -> None:
    record = {"registrant_organization": "REDACTED FOR PRIVACY"}
    assert whois.rdapPages(record) == ()


def test_scrub_record_hides_people_but_keeps_registry_facts() -> None:
    lines = [
        "Domain Name: example.gay",
        "Registrar: NAMECHEAP INC",
        "Registrant Name: Some Person",
        "Registrant Organization: Example Ltd",
        "Registrant Street: 1 Home Street",
        "Registrant Country: GB",
        "Admin Email: person@example.com",
        "Tech Phone: +44.0000000000",
        "Registrar Abuse Contact Email: abuse@namecheap.com",
        "address:        1 Home Street",
        "e-mail:         person@example.com",
    ]
    raw = "\n".join(lines)

    scrubbed = whois.scrubRecord(raw)

    for leaked in ("Some Person", "Home Street", "person@example.com"):
        assert leaked not in scrubbed
    assert "Registrant Name: [hidden]" in scrubbed
    assert "Registrant Organization: Example Ltd" in scrubbed
    assert "Registrant Country: GB" in scrubbed
    assert "abuse@namecheap.com" in scrubbed


def test_report_menu_round_trips_through_its_custom_id() -> None:
    page = whois.Page("overview", "Overview", None, "> hi")
    other = whois.Page("raw", "Raw Record", None, "```\nx\n```")
    report = whois.Report("example.com", "RDAP", (page, other))

    view = whois.renderReport("example.com", report, "raw")
    selects = selectsOf(view)

    assert len(selects) == 1
    match = re.fullmatch(whois.PAGE_TEMPLATE, selects[0].custom_id)
    assert match and match["target"] == "example.com"
    assert [o.default for o in selects[0].options] == [False, True]


def test_single_page_reports_have_no_menu() -> None:
    page = whois.Page("overview", "Overview", None, "> hi")
    report = whois.Report("example.com", "RDAP", (page,))

    view = whois.renderReport("example.com", report)

    assert not selectsOf(view)
