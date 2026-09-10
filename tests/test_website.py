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
