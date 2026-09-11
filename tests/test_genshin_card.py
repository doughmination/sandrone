import io
from typing import Any

import pytest
from PIL import Image

from utils import genshin_card


def _stat(name, value, is_percent, base=None, added=None):
    out = {"name": name, "value": value, "is_percent": is_percent}
    if base is not None:
        out["base"] = base
        out["added"] = added
    return out


FULL_DETAIL: dict[str, Any] = {
    "id": "10000087",
    "name": "Neuvillette",
    "nickname": "PrimordialTwo",
    "element": "Hydro",
    "rarity": 5,
    "icon_url": "https://cdn.example/UI_AvatarIcon_Neuvillette.png",
    "art_url": "https://cdn.example/UI_Gacha_AvatarImg_Neuvillette.png",
    "owned": True,
    "tracked": True,
    "level": 90,
    "constellation": 0,
    "friendship": 10,
    "talents": {"normal": 8, "skill": 6, "burst": 5},
    "updated_at": 1788803498943,
    "stats": [
        _stat("Max HP", 37032, False, base=14695, added=22337),
        _stat("ATK", 1328, False, base=718, added=610),
        _stat("DEF", 735, False, base=576, added=158),
        _stat("CRIT Rate", 48.5, True),
        _stat("CRIT DMG", 207.2, True),
        _stat("Energy Recharge", 118.1, True),
        _stat("Hydro DMG Bonus", 61.6, True),
    ],
    "weapon": {
        "name": "The Widsith",
        "rarity": 4,
        "level": 90,
        "refinement": 1,
        "base_stat": _stat("Base ATK", 510, False),
        "sub_stat": _stat("CRIT DMG", 55.1, True),
        "icon_url": "https://cdn.example/UI_EquipIcon_Catalyst_Troupe.png",
    },
    "artifacts": [
        {
            "slot": slot,
            "rarity": 5,
            "level": 20,
            "set_name": "Marechaussee Hunter",
            "main_stat": _stat("HP", 4780, False),
            "sub_stats": [
                _stat("CRIT DMG", 7.8, True),
                _stat("HP%", 9.9, True),
                _stat("CRIT Rate", 9.7, True),
                _stat("ATK", 29, False),
            ],
            "icon_url": f"https://cdn.example/UI_RelicIcon_15031_{i}.png",
        }
        for i, slot in enumerate(["flower", "plume", "sands", "goblet", "circlet"], 1)
    ],
    "sets": [{"name": "Marechaussee Hunter", "count": 4}],
}


def _dims(png: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(png)) as im:
        return im.size


def test_full_card_renders_png_at_canvas_size():
    png = genshin_card.renderCard(FULL_DETAIL, {}, uid="894958899", ar=56)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert _dims(png) == genshin_card.CANVAS


def test_bare_last_known_character_still_renders():
    bare = {
        "name": "Kaeya",
        "element": "Cryo",
        "rarity": 4,
        "art_url": "https://cdn.example/x.png",
        "level": 70,
        "constellation": 3,
        "friendship": None,
        "talents": None,
        "stats": [],
        "weapon": None,
        "artifacts": [],
        "sets": [],
    }
    png = genshin_card.renderCard(bare, {}, uid="123456789")
    assert _dims(png) == genshin_card.CANVAS


def test_partial_artifacts_and_missing_main_stat():
    detail = dict(FULL_DETAIL)
    detail["artifacts"] = [
        {
            "slot": "flower",
            "rarity": 5,
            "level": 12,
            "set_name": "Unknown",
            "main_stat": None,
            "sub_stats": [],
            "icon_url": "",
        }
    ]
    detail["sets"] = []
    png = genshin_card.renderCard(detail, {}, uid="123456789", ar=None)
    assert _dims(png) == genshin_card.CANVAS


@pytest.mark.parametrize(
    "element", ["Pyro", "Hydro", "Anemo", "Electro", "Cryo", "Geo", "Dendro", "All"]
)
def test_every_element_tint(element):
    detail = dict(FULL_DETAIL, element=element)
    png = genshin_card.renderCard(detail, {}, uid="1", ar=1)
    assert _dims(png) == genshin_card.CANVAS


def test_icon_urls_collects_every_remote_image():
    urls = genshin_card.iconUrls(FULL_DETAIL)
    assert FULL_DETAIL["art_url"] in urls
    assert FULL_DETAIL["weapon"]["icon_url"] in urls
    assert sum(1 for u in urls if "RelicIcon" in u) == 5
    assert len(urls) == len(set(urls))


def test_format_stat_value():
    assert genshin_card.formatStatValue(_stat("CRIT Rate", 48.53, True)) == "48.5%"
    assert genshin_card.formatStatValue(_stat("Max HP", 37032.4, False)) == "37,032"
