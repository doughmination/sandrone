import asyncio
import json
from pathlib import Path

import pytest
from aiohttp.test_utils import make_mocked_request

from sandrone import config, website


@pytest.fixture
def webRoot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "webDir", tmp_path)
    return tmp_path


def test_web_asset_serves_only_files_inside_the_web_directory(webRoot: Path) -> None:
    index = webRoot / "index.html"
    index.write_text("Sandrone", encoding="utf-8")
    secret = webRoot.parent / "secret.txt"
    secret.write_text("not public", encoding="utf-8")

    assert website.webAsset("index.html") == index.resolve()
    assert website.webAsset("../secret.txt") is None
    assert website.webAsset("missing.html") is None


def test_website_routes_keep_downloads_under_d() -> None:
    app = website.createApp()
    routes = {
        resource.canonical
        for route in app.router.routes()
        if (resource := route.resource) is not None
    }

    assert "/" in routes
    assert "/d/{slot}/{name}" in routes


def test_website_exposes_a_status_route() -> None:
    app = website.createApp()
    routes = {
        resource.canonical
        for route in app.router.routes()
        if (resource := route.resource) is not None
    }

    assert "/api/status" in routes


def statusPayload(bot: object | None = None) -> dict:
    app = website.createApp(bot)
    request = make_mocked_request("GET", "/api/status", app=app)
    response = asyncio.run(website.status(request))
    return json.loads(response.text or "")


def test_status_reports_the_bot_when_one_is_attached() -> None:
    class FakeBot:
        guilds = (object(), object())
        latency = 0.042

    payload = statusPayload(FakeBot())

    assert payload["servers"] == 2
    assert payload["latency"] == 42
    assert payload["version"] == config.version
    assert payload["uptime"] >= 0


def test_status_omits_bot_details_when_there_is_no_bot() -> None:
    payload = statusPayload()

    assert "servers" not in payload
    assert "latency" not in payload


def renderSitemap(webRoot: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(config, "siteUrl", "https://sandrone.example")
    app = website.createApp()
    request = make_mocked_request("GET", "/sitemap.xml", app=app)
    return asyncio.run(website.sitemap(request)).text or ""


def test_sitemap_lists_pages_that_exist_and_skips_the_ones_that_should_not(
    webRoot: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (webRoot / "index.html").write_text("Sandrone", encoding="utf-8")
    (webRoot / "privacy.html").write_text("Privacy", encoding="utf-8")
    (webRoot / "404.html").write_text("Not found", encoding="utf-8")
    (webRoot / "meta-example.html").write_text("Example", encoding="utf-8")
    (webRoot / "style.css").write_text("body{}", encoding="utf-8")

    body = renderSitemap(webRoot, monkeypatch)

    assert "<loc>https://sandrone.example/</loc>" in body
    assert "<loc>https://sandrone.example/privacy.html</loc>" in body
    assert "404.html" not in body
    assert "meta-example.html" not in body
    assert "style.css" not in body


def test_sitemap_ignores_pages_that_are_still_empty(
    webRoot: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (webRoot / "index.html").write_text("Sandrone", encoding="utf-8")
    (webRoot / "terms.html").write_text("", encoding="utf-8")

    body = renderSitemap(webRoot, monkeypatch)

    assert "<loc>https://sandrone.example/</loc>" in body
    assert "terms.html" not in body


def test_sitemap_picks_up_a_page_added_after_the_app_was_built(
    webRoot: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (webRoot / "index.html").write_text("Sandrone", encoding="utf-8")
    monkeypatch.setattr(config, "siteUrl", "https://sandrone.example")
    app = website.createApp()

    (webRoot / "terms.html").write_text("Terms", encoding="utf-8")

    request = make_mocked_request("GET", "/sitemap.xml", app=app)
    body = asyncio.run(website.sitemap(request)).text or ""

    assert "<loc>https://sandrone.example/terms.html</loc>" in body


def test_robots_points_at_the_sitemap_and_hides_downloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "siteUrl", "https://sandrone.example")
    app = website.createApp()
    request = make_mocked_request("GET", "/robots.txt", app=app)

    body = asyncio.run(website.robots(request)).text or ""

    assert "Sitemap: https://sandrone.example/sitemap.xml" in body
    assert "Disallow: /d/" in body
    assert "Disallow: /api/" in body


def test_website_exposes_the_sitemap_and_robots_routes() -> None:
    app = website.createApp()
    routes = {
        resource.canonical
        for route in app.router.routes()
        if (resource := route.resource) is not None
    }

    assert "/sitemap.xml" in routes
    assert "/robots.txt" in routes
