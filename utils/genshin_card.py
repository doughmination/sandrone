from __future__ import annotations

import io
from functools import lru_cache
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from sandrone import config

CANVAS = (1462, 609)

FONT_DIR = config.assetsDir / "fonts"
FONT_FILES = {
    "regular": FONT_DIR / "IBMPlexSans-Regular.ttf",
    "medium": FONT_DIR / "IBMPlexSans-Medium.ttf",
    "semibold": FONT_DIR / "IBMPlexSans-SemiBold.ttf",
    "bold": FONT_DIR / "IBMPlexSans-Bold.ttf",
}

WHITE = (255, 255, 255, 255)
DIM = (255, 255, 255, 150)
GREEN = (150, 255, 169, 255)
BEIGE = (245, 222, 179, 255)
GOLD = (255, 206, 100, 255)

ELEMENT_TINT = {
    "Pyro": (186, 140, 131),
    "Hydro": (132, 161, 198),
    "Dendro": (77, 142, 82),
    "Electro": (152, 118, 173),
    "Anemo": (82, 176, 177),
    "Cryo": (70, 168, 186),
    "Geo": (187, 159, 75),
    "All": (150, 150, 150),
}

STAT_ABBR = {
    "HP": "HP",
    "HP%": "HP%",
    "ATK": "ATK",
    "ATK%": "ATK%",
    "DEF": "DEF",
    "DEF%": "DEF%",
    "CRIT Rate": "CR",
    "CRIT DMG": "CD",
    "Energy Recharge": "ER",
    "Elemental Mastery": "EM",
    "Healing Bonus": "Heal",
    "Base ATK": "Base ATK",
}

SLOT_LETTER = {
    "flower": "❀",
    "plume": "↑",
    "sands": "⧖",
    "goblet": "∪",
    "circlet": "◉",
}


@lru_cache(maxsize=64)
def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONT_FILES.get(weight, FONT_FILES["regular"])
    return ImageFont.truetype(str(path), size)


def _open(images: dict[str, bytes], url: str | None) -> Image.Image | None:
    if not url:
        return None
    blob = images.get(url)
    if not blob:
        return None
    try:
        return Image.open(io.BytesIO(blob)).convert("RGBA")
    except (OSError, ValueError):
        return None


def _fit_height(im: Image.Image, height: int) -> Image.Image:
    if im.height == height:
        return im
    width = max(1, round(im.width * height / im.height))
    return im.resize((width, height), Image.Resampling.LANCZOS)


def formatStatValue(stat: dict[str, Any]) -> str:
    value = stat.get("value", 0) or 0
    if stat.get("is_percent"):
        return f"{value:.1f}%"
    return f"{round(value):,}"


def _star_points(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    import math

    pts: list[tuple[float, float]] = []
    for i in range(5):
        outer = math.radians(-90 + i * 72)
        inner = math.radians(-90 + i * 72 + 36)
        pts.append((cx + r * math.cos(outer), cy + r * math.sin(outer)))
        pts.append((cx + r * 0.42 * math.cos(inner), cy + r * 0.42 * math.sin(inner)))
    return pts


def _draw_stars(
    draw: ImageDraw.ImageDraw, x: int, y: int, count: int, r: int = 8
) -> int:
    gap = int(r * 2.15)
    for i in range(count):
        draw.polygon(_star_points(x + r + i * gap, y + r, r), fill=GOLD)
    return count * gap


def _draw_diamond(
    draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, fill: tuple[int, int, int, int]
) -> None:
    draw.polygon(
        [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)],
        fill=fill,
    )


def _draw_heart(
    draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, fill: tuple[int, int, int, int]
) -> None:
    draw.ellipse((cx - r, cy - r, cx, cy), fill=fill)
    draw.ellipse((cx, cy - r, cx + r, cy), fill=fill)
    draw.polygon(
        [(cx - r, cy - r // 3), (cx + r, cy - r // 3), (cx, cy + r)], fill=fill
    )


def _rounded(
    base: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int, int],
) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius=radius, fill=fill)
    base.alpha_composite(layer)


def _background(element: str) -> Image.Image:
    tint = ELEMENT_TINT.get(element, (150, 150, 150))
    base = Image.new("RGBA", CANVAS, (0, 0, 0, 255))
    top = (
        min(tint[0] // 2 + 24, 255),
        min(tint[1] // 2 + 24, 255),
        min(tint[2] // 2 + 26, 255),
    )
    bottom = (14, 15, 22)
    grad = Image.new("RGBA", (1, CANVAS[1]))
    for y in range(CANVAS[1]):
        t = y / CANVAS[1]
        grad.putpixel(
            (0, y),
            (
                round(top[0] + (bottom[0] - top[0]) * t),
                round(top[1] + (bottom[1] - top[1]) * t),
                round(top[2] + (bottom[2] - top[2]) * t),
                255,
            ),
        )
    base.paste(grad.resize(CANVAS), (0, 0))
    wash = Image.new("RGBA", CANVAS, (*tint, 46))
    base.alpha_composite(wash)
    return base


def _hgrad_mask(
    size: tuple[int, int], left_val: int, right_val: int, ease: float = 1.0
) -> Image.Image:
    w = size[0]
    row = Image.new("L", (w, 1))
    row.putdata(
        [
            round(left_val + (right_val - left_val) * (x / max(1, w - 1)) ** ease)
            for x in range(w)
        ]
    )
    return row.resize(size)


def _character_art(base: Image.Image, art: Image.Image | None) -> None:
    if art is None:
        return
    art = _fit_height(art, int(CANVAS[1] * 1.1))
    slice_w = min(art.width, 620)
    left = max(0, int(art.width * 0.30))
    left = min(left, art.width - slice_w)
    top = 6
    art = art.crop((left, top, left + slice_w, min(art.height, top + CANVAS[1])))

    fade_from = int(art.width * 0.78)
    mask = Image.new("L", art.size, 255)
    mask.paste(
        _hgrad_mask((art.width - fade_from, art.height), 255, 0),
        (fade_from, 0),
    )
    alpha = art.split()[-1]
    art.putalpha(Image.composite(alpha, Image.new("L", art.size, 0), mask))

    base.alpha_composite(art, (-8, 0))


def _left_scrim(base: Image.Image) -> None:
    scrim = Image.new("RGBA", (380, CANVAS[1]), (8, 9, 14, 255))
    scrim.putalpha(_hgrad_mask((380, CANVAS[1]), 205, 0, ease=1.6))
    base.alpha_composite(scrim, (0, 0))


def _left_column(
    base: Image.Image,
    draw: ImageDraw.ImageDraw,
    detail: dict,
    roster_uid: str,
    ar: int | None,
) -> None:
    name = detail.get("name", "Unknown")
    draw.text((40, 30), name, font=_font("semibold", 34), fill=WHITE)
    w = draw.textlength(name, font=_font("semibold", 34))
    nick = detail.get("nickname")
    if nick:
        draw.text((48 + w, 46), str(nick), font=_font("regular", 16), fill=DIM)

    level = detail.get("level") or "?"
    draw.text((40, 74), f"Lv. {level}", font=_font("medium", 22), fill=WHITE)

    friendship = detail.get("friendship")
    if friendship is not None:
        _draw_heart(draw, 44, 114, 8, (255, 120, 140, 255))
        draw.text((62, 104), str(friendship), font=_font("medium", 20), fill=WHITE)

    total_c = 6
    unlocked = int(detail.get("constellation") or 0)
    accent = (*ELEMENT_TINT.get(detail.get("element", ""), (200, 200, 200)), 255)
    draw.text((38, 148), f"C{unlocked}", font=_font("medium", 15), fill=DIM)
    for i in range(total_c):
        cy = 176 + i * 42
        box = (36, cy, 62, cy + 26)
        if i < unlocked:
            draw.ellipse(box, fill=accent, outline=WHITE, width=2)
        else:
            draw.ellipse(
                box, fill=(24, 26, 34, 200), outline=(255, 255, 255, 90), width=2
            )

    y = CANVAS[1] - 44
    draw.text((40, y), f"UID {roster_uid}", font=_font("regular", 17), fill=DIM)
    if ar:
        draw.text((40, y - 24), f"AR {ar}", font=_font("medium", 17), fill=BEIGE)


def _talents(base: Image.Image, talents: dict | None) -> None:
    if not talents:
        return
    labels = [
        ("A", talents.get("normal")),
        ("E", talents.get("skill")),
        ("Q", talents.get("burst")),
    ]
    for i, (label, lvl) in enumerate(labels):
        if lvl is None:
            continue
        cx, cy = 500, 250 + i * 82
        layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.ellipse(
            (cx - 26, cy - 26, cx + 26, cy + 26),
            fill=(20, 22, 30, 210),
            outline=WHITE,
            width=2,
        )
        d.text((cx, cy - 4), label, font=_font("semibold", 20), fill=WHITE, anchor="mm")
        boosted = int(lvl) >= 10
        pill = (cx - 16, cy + 16, cx + 16, cy + 38)
        d.rounded_rectangle(
            pill, radius=11, fill=(79, 188, 212, 255) if boosted else (20, 22, 30, 220)
        )
        d.text(
            (cx, cy + 27), str(lvl), font=_font("medium", 15), fill=WHITE, anchor="mm"
        )
        base.alpha_composite(layer)


def _weapon(
    base: Image.Image, draw: ImageDraw.ImageDraw, images: dict, weapon: dict | None
) -> None:
    x0 = 560
    if not weapon:
        draw.text((x0, 40), "No weapon equipped", font=_font("regular", 18), fill=DIM)
        return

    icon = _open(images, weapon.get("icon_url"))
    if icon is not None:
        icon = _fit_height(icon, 118)
        base.alpha_composite(icon, (x0, 24))
    else:
        _rounded(base, (x0, 24, x0 + 110, 134), 8, (255, 255, 255, 25))
    _draw_stars(draw, x0 + 6, 138, int(weapon.get("rarity") or 4), r=7)

    tx = x0 + 130
    draw.text(
        (tx, 30), str(weapon.get("name", "")), font=_font("semibold", 22), fill=WHITE
    )

    pills: list[tuple[str, tuple[int, int, int, int], tuple[int, int, int, int]]] = []
    for key in ("base_stat", "sub_stat"):
        stat = weapon.get(key)
        if stat:
            pills.append((formatStatValue(stat), (235, 235, 235, 40), WHITE))
    pills.append((f"R{weapon.get('refinement', 1)}", (0, 0, 0, 110), BEIGE))
    lvl = weapon.get("level", 1)
    pills.append((f"Lv. {lvl}/90", (0, 0, 0, 110), WHITE))

    px = tx
    py = 66
    for i, (text, bg, fg) in enumerate(pills):
        if i == 2:
            px = tx
            py = 104
        tw = int(draw.textlength(text, font=_font("medium", 20)))
        _rounded(base, (px, py, px + tw + 34, py + 30), 5, bg)
        _draw_diamond(draw, px + 15, py + 15, 6, (*(fg[:3]), 220))
        draw.text((px + 27, py + 4), text, font=_font("medium", 20), fill=fg)
        px += tw + 46


def _stats(
    base: Image.Image, draw: ImageDraw.ImageDraw, stats: list[dict], element: str
) -> None:
    if not stats:
        draw.text(
            (600, 300),
            "No live stat sheet for this character.",
            font=_font("regular", 16),
            fill=DIM,
        )
        return
    stats = stats[:8]
    top, bottom = 176, 548
    step = (bottom - top) // len(stats)
    accent = (*ELEMENT_TINT.get(element, (200, 200, 200)), 255)
    for i, stat in enumerate(stats):
        y = top + i * step
        _draw_diamond(draw, 566, y + 12, 6, accent)
        draw.text((584, y), stat.get("name", ""), font=_font("regular", 20), fill=WHITE)
        if stat.get("base") is not None and not stat.get("is_percent"):
            draw.text(
                (990, y - 8),
                f"{round(stat['value']):,}",
                font=_font("medium", 20),
                fill=WHITE,
                anchor="ra",
            )
            added = f"+{round(stat.get('added') or 0):,}"
            aw = draw.textlength(added, font=_font("regular", 12))
            draw.text(
                (990, y + 14),
                added,
                font=_font("regular", 12),
                fill=(150, 255, 169, 220),
                anchor="ra",
            )
            draw.text(
                (990 - aw - 5, y + 14),
                f"{round(stat['base']):,}",
                font=_font("regular", 12),
                fill=DIM,
                anchor="ra",
            )
        else:
            draw.text(
                (990, y),
                formatStatValue(stat),
                font=_font("medium", 20),
                fill=WHITE,
                anchor="ra",
            )


def _sets(base: Image.Image, draw: ImageDraw.ImageDraw, sets: list[dict]) -> None:
    y = 556
    _rounded(base, (560, y, 604, y + 44), 6, (0, 0, 0, 60))
    _draw_diamond(draw, 582, y + 22, 12, (150, 255, 169, 200))
    if not sets:
        draw.text(
            (770, y + 22),
            "No set bonus",
            font=_font("medium", 16),
            fill=GREEN,
            anchor="mm",
        )
        return
    rows = sets[:2]
    for i, s in enumerate(rows):
        ry = y + 22 + (i * 22 - 11 if len(rows) > 1 else 0)
        draw.text(
            (770, ry),
            s.get("name", ""),
            font=_font("medium", 16),
            fill=GREEN,
            anchor="mm",
        )
        _rounded(base, (938, ry - 11, 968, ry + 11), 4, (0, 0, 0, 70))
        draw.text(
            (953, ry),
            str(s.get("count", "")),
            font=_font("medium", 16),
            fill=WHITE,
            anchor="mm",
        )


def _artifacts(
    base: Image.Image, draw: ImageDraw.ImageDraw, images: dict, artifacts: list[dict]
) -> None:
    order = ["flower", "plume", "sands", "goblet", "circlet"]
    by_slot = {a.get("slot"): a for a in artifacts}
    spacer = 118
    div_x = 1180
    val_x = 1174
    for i, slot in enumerate(order):
        y0 = 14 + spacer * i
        art = by_slot.get(slot)
        _rounded(
            base, (1008, y0, 1452, y0 + 106), 6, (0, 0, 0, 70) if art else (0, 0, 0, 26)
        )
        if not art:
            draw.text(
                (1030, y0 + 44), f"No {slot}", font=_font("regular", 15), fill=DIM
            )
            continue

        icon = _open(images, art.get("icon_url"))
        if icon is not None:
            icon = _fit_height(icon, 120).crop((24, 14, 86, 88))
            icon.putalpha(icon.split()[-1].point(lambda a: int(a * 0.55)))
            base.alpha_composite(icon, (1004, y0 + 14))
        else:
            draw.text(
                (1036, y0 + 34),
                SLOT_LETTER.get(slot, "?"),
                font=_font("semibold", 34),
                fill=DIM,
            )

        draw.line((div_x, y0 + 12, div_x, y0 + 94), fill=(255, 255, 255, 30), width=2)

        main = art.get("main_stat")
        _draw_diamond(draw, 1100, y0 + 30, 6, (255, 255, 255, 210))
        draw.text(
            (val_x, y0 + 16),
            formatStatValue(main) if main else "—",
            font=_font("semibold", 25),
            fill=WHITE,
            anchor="ra",
        )
        lvl = f"+{art.get('level', 0)}"
        lw = draw.textlength(lvl, font=_font("medium", 13))
        _rounded(
            base, (int(val_x - lw - 12), y0 + 52, val_x, y0 + 72), 3, (0, 0, 0, 180)
        )
        draw.text(
            (val_x - 2, y0 + 54), lvl, font=_font("medium", 13), fill=WHITE, anchor="ra"
        )
        _draw_stars(
            draw, int(val_x - 5 * 13), y0 + 80, int(art.get("rarity") or 5), r=6
        )

        subs = (art.get("sub_stats") or [])[:4]
        for j, sub in enumerate(subs):
            col, row = j % 2, j // 2
            sx = 1190 + col * 138
            sy = y0 + 22 + row * 42
            label = STAT_ABBR.get(sub.get("name", ""), sub.get("name", ""))
            _draw_diamond(draw, sx + 5, sy + 11, 4, DIM)
            draw.text(
                (sx + 16, sy),
                f"{label} +{formatStatValue(sub)}",
                font=_font("regular", 14),
                fill=WHITE,
            )


def renderCard(
    detail: dict[str, Any], images: dict[str, bytes], *, uid: str, ar: int | None = None
) -> bytes:
    element = detail.get("element", "All")
    base = _background(element)
    _character_art(base, _open(images, detail.get("art_url")))
    _left_scrim(base)

    _rounded(base, (548, 12, 1000, 596), 12, (10, 12, 20, 140))

    draw = ImageDraw.Draw(base)
    _left_column(base, draw, detail, uid, ar)
    _talents(base, detail.get("talents"))
    _weapon(base, draw, images, detail.get("weapon"))
    _stats(base, draw, detail.get("stats") or [], element)
    _sets(base, draw, detail.get("sets") or [])
    _artifacts(base, draw, images, detail.get("artifacts") or [])

    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


def iconUrls(detail: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for key in ("art_url",):
        if detail.get(key):
            urls.append(detail[key])
    weapon = detail.get("weapon") or {}
    if weapon.get("icon_url"):
        urls.append(weapon["icon_url"])
    for art in detail.get("artifacts") or []:
        if art.get("icon_url"):
            urls.append(art["icon_url"])
    return list(dict.fromkeys(urls))
