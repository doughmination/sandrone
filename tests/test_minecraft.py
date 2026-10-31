import base64
from commands.cogs.lookups import minecraft
from discord import ui
import json


def textOf(view: ui.LayoutView) -> str:
    return "\n".join(
        item.content
        for item in view.walk_children()
        if isinstance(item, ui.TextDisplay)
    )


def profileWith(textures: dict) -> dict:
    value = base64.b64encode(
        json.dumps({"textures": textures}).encode()
    ).decode()
    return {
        "id": "069a79f444e94726a5befca90e38aaf5",
        "name": "Notch",
        "properties": [{"name": "textures", "value": value}],
    }


def test_normalise_name_accepts_usernames_and_uuids() -> None:
    assert minecraft.normaliseName(" @Notch ") == "Notch"
    assert (
        minecraft.normaliseName("069A79F4-44E9-4726-A5BE-FCA90E38AAF5")
        == "069a79f444e94726a5befca90e38aaf5"
    )
    assert minecraft.normaliseName("not a name") is None
    assert minecraft.normaliseName("x" * 17) is None


def test_normalise_address_strips_noise_and_rejects_junk() -> None:
    assert (
        minecraft.normaliseAddress("https://Play.Example.com:25565/")
        == "play.example.com:25565"
    )
    assert minecraft.normaliseAddress("../etc/passwd") is None
    assert minecraft.normaliseAddress("a b") is None
    assert minecraft.normaliseAddress("   ") is None


def test_parse_textures_reads_skin_model_and_cape() -> None:
    textures = minecraft.parseTextures(
        profileWith(
            {
                "SKIN": {
                    "url": "http://textures.minecraft.net/texture/abc",
                    "metadata": {"model": "slim"},
                },
                "CAPE": {"url": "http://textures.minecraft.net/texture/c"},
            }
        )
    )
    assert textures.skin == "https://textures.minecraft.net/texture/abc"
    assert textures.slim
    assert textures.cape is not None


def test_parse_textures_handles_missing_or_broken_data() -> None:
    empty = minecraft.parseTextures({"properties": []})
    assert empty.skin is None and not empty.slim and empty.cape is None

    broken = minecraft.parseTextures(
        {"properties": [{"name": "textures", "value": "!!!"}]}
    )
    assert broken.skin is None


def test_status_panel_offline() -> None:
    text = textOf(
        minecraft.statusPanel({"online": False}, "example.com", "java")
    )
    assert "offline" in text


def test_status_panel_online_lists_details() -> None:
    data = {
        "online": True,
        "ip": "1.2.3.4",
        "port": 25565,
        "motd": {"clean": ["  Welcome!  ", ""]},
        "players": {
            "online": 12,
            "max": 100,
            "list": [{"name": f"p_{i}"} for i in range(12)],
        },
        "version": "§aPaper 1.21",
    }
    text = textOf(minecraft.statusPanel(data, "example.com", "java"))
    assert "online" in text
    assert "12 / 100" in text
    assert "Welcome!" in text
    assert "Paper 1.21" in text and "§" not in text
    assert "`1.2.3.4:25565`" in text
    assert "and 2 more" in text
