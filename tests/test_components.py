import discord
from discord import ui

from utils import components


def test_panel_wraps_single_container() -> None:
    view = components.panel(title="Hello", body="world")

    assert isinstance(view, discord.ui.LayoutView)
    assert len(view.children) == 1
    assert isinstance(view.children[0], ui.Container)


def test_container_lays_out_every_piece() -> None:
    box = components.container(
        title="Title",
        url="https://example.com",
        body="Body text",
        fields=[("One", "1"), ("Two", "2")],
        thumbnail="https://example.com/thumb.png",
        images=["https://example.com/a.png", "https://example.com/b.png"],
        footer="Sandrone",
        color=components.FUCHSIA,
    )

    kinds = [type(child) for child in box.children]
    assert ui.Section in kinds
    assert ui.MediaGallery in kinds
    assert ui.Separator in kinds
    assert box.accent_colour == components.FUCHSIA

    section = next(c for c in box.children if isinstance(c, ui.Section))
    text = "".join(
        child.content for child in section.children if isinstance(child, ui.TextDisplay)
    )
    assert "## [Title](https://example.com)" in text


def test_error_uses_red_accent() -> None:
    view = components.error("nope")
    box = view.children[0]

    assert isinstance(box, ui.Container)
    assert box.accent_colour == components.RED
    body = "".join(
        child.content for child in box.children if isinstance(child, ui.TextDisplay)
    )
    assert ":x: nope" in body


def test_buttons_render_as_a_row_inside_the_container() -> None:
    box = components.container(
        body="pick one",
        buttons=[
            components.linkButton("A", "https://example.com/a"),
            components.linkButton("B", "https://example.com/b", emoji="🔗"),
        ],
        footer="f",
    )

    rows = [c for c in box.children if isinstance(c, ui.ActionRow)]
    assert len(rows) == 1
    buttons = [c for c in rows[0].children if isinstance(c, ui.Button)]
    assert [b.label for b in buttons] == ["A", "B"]
    assert all(b.style is discord.ButtonStyle.link for b in buttons)
    assert all(b.url is not None for b in buttons)


def test_gallery_accepts_urls_and_image_items_and_caps_at_ten() -> None:
    box = components.container(
        images=[
            "https://example.com/0.png",
            components.image("https://example.com/1.png", alt="one"),
            *[f"https://example.com/{i}.png" for i in range(2, 20)],
        ]
    )

    galleries = [c for c in box.children if isinstance(c, ui.MediaGallery)]
    assert len(galleries) == 1
    assert len(galleries[0].items) == 10
    assert galleries[0].items[1].description == "one"


def test_container_renders_without_any_pieces() -> None:
    box = components.container()

    assert isinstance(box, ui.Container)
    assert len(box.children) == 1
