from pathlib import Path

import pytest

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
