"""Flag overlay rendering, ported from the LGBTQ+ Profile Picture Overlay
Generator at https://pride-pfp.xyz (MIT).

The original paints an HTML canvas: it fills oversized flag rectangles, rotates
the drawing context around the centre, then clips a circle or square out of the
middle and draws the avatar into it. Pillow has no clipping context and cannot
rotate mid-draw, so the same result comes from painting the flag flat into a
layer twice the canvas size, rotating that whole layer, and cropping the middle
back out. Doubling the layer is what the oversized rects were doing: it keeps
the corners covered once the flag is turned.
"""

import io
import math
from typing import NamedTuple

from PIL import Image, ImageDraw

flagColours: dict[str, tuple[str, ...]] = {
    "abrosexual": (
        "#75ca91",
        "#b3e4c7",
        "#ffffff",
        "#e695b5",
        "#d9446c",
    ),
    "agender": (
        "#000000",
        "#bababa",
        "#ffffff",
        "#b9f484",
        "#ffffff",
        "#bababa",
        "#000000",
    ),
    "aroace": (
        "#e28c00",
        "#eccd00",
        "#ffffff",
        "#62aedc",
        "#203856",
    ),
    "aromantic": (
        "#3aa63f",
        "#a8d47a",
        "#ffffff",
        "#aaaaaa",
        "#000000",
    ),
    "asexual": (
        "#000000",
        "#a3a3a3",
        "#ffffff",
        "#800080",
    ),
    "bigender": (
        "#ee79ac",
        "#fdf44c",
        "#ffffff",
        "#af6dbf",
        "#719fe4",
    ),
    "bisexual": (
        "#d9006f",
        "#744d98",
        "#0033ab",
    ),
    "demiboy": (
        "#7f7f7f",
        "#c3c3c3",
        "#99d9ea",
        "#ffffff",
        "#99d9ea",
        "#c3c3c3",
        "#7f7f7f",
    ),
    "demigender": (
        "#7f7f7f",
        "#c3c3c3",
        "#faff74",
        "#ffffff",
        "#faff74",
        "#c3c3c3",
        "#7f7f7f",
    ),
    "demigirl": (
        "#7f7f7f",
        "#c3c3c3",
        "#ffaec9",
        "#ffffff",
        "#ffaec9",
        "#c3c3c3",
        "#7f7f7f",
    ),
    "genderfluid": (
        "#f376a0",
        "#ffffff",
        "#ad4cbf",
        "#000000",
        "#3f47b6",
    ),
    "genderflux": (
        "#f47694",
        "#f2a2b9",
        "#cecece",
        "#7ce0f7",
        "#3ecdf9",
        "#fff48d",
    ),
    "genderqueer": (
        "#b67fdd",
        "#ffffff",
        "#49821e",
    ),
    "grayromantic": (
        "#000000",
        "#b2b2b2",
        "#ffffff",
        "#2da038",
        "#063609",
    ),
    "graysexual": (
        "#740194",
        "#aeb1aa",
        "#ffffff",
        "#aeb1aa",
        "#740194",
    ),
    "lesbian": (
        "#d62900",
        "#ff9b55",
        "#ffffff",
        "#d462a5",
        "#a50062",
    ),
    "mlm": (
        "#078d70",
        "#26ceaa",
        "#98e8c1",
        "#f1efff",
        "#7bade2",
        "#5049cc",
        "#3d1a78",
    ),
    "mlm_old": (
        "#0b7c6a",
        "#42a4a5",
        "#5cc8d2",
        "#f1eeff",
        "#7bade2",
        "#1483cb",
        "#073370",
    ),
    "nonbinary": (
        "#fff433",
        "#ffffff",
        "#9b59d0",
        "#000000",
    ),
    "omnisexual": (
        "#ff9ccd",
        "#ff53bd",
        "#270046",
        "#675ffe",
        "#8ca7ff",
    ),
    "pansexual": (
        "#ff148c",
        "#ffda00",
        "#05aeff",
    ),
    "plural": (
        "#31c69e",
        "#347dde",
        "#6b3fbd",
        "#000000",
    ),
    "poc": (
        "#000000",
        "#654321",
        "#e70000",
        "#ff8c00",
        "#ffef00",
        "#00811f",
        "#0044ff",
        "#760089",
    ),
    "polyamorous": (
        "#0000ff",
        "#ff0000",
        "#000000",
    ),
    "polysexual": (
        "#f61cb9",
        "#07d569",
        "#1c92f6",
    ),
    "pride": (
        "#e70000",
        "#ff8c00",
        "#ffef00",
        "#00811f",
        "#0044ff",
        "#760089",
    ),
    "queer": (
        "#000000",
        "#99d9ea",
        "#00a2e8",
        "#b5e61d",
        "#ffffff",
        "#ffc90e",
        "#fd6666",
        "#ffaec9",
        "#000000",
    ),
    "transfeminine": (
        "#74deff",
        "#ffe1ed",
        "#ffb5d6",
        "#fe8cbf",
        "#ffb5d6",
        "#ffe1ed",
        "#74deff",
    ),
    "transgender": (
        "#5bcffa",
        "#f5abb9",
        "#ffffff",
        "#f5abb9",
        "#5bcffa",
    ),
    "transmasculine": (
        "#f283b4",
        "#c2e9f2",
        "#91e0f2",
        "#6fd4f2",
        "#91e0f2",
        "#c2e9f2",
        "#f283b4",
    ),
}

flagLabels: dict[str, str] = {
    "abrosexual": "Abrosexual",
    "agender": "Agender",
    "aroace": "Aroace",
    "aromantic": "Aromantic",
    "asexual": "Asexual",
    "bigender": "Bigender",
    "bisexual": "Bisexual",
    "demiboy": "Demiboy",
    "demigender": "Demigender",
    "demigirl": "Demigirl",
    "genderfluid": "Genderfluid",
    "genderflux": "Genderflux",
    "genderqueer": "Genderqueer",
    "grayromantic": "Grayromantic",
    "graysexual": "Graysexual",
    "lesbian": "Lesbian",
    "mlm": "MLM",
    "mlm_old": "MLM (older)",
    "nonbinary": "Nonbinary",
    "omnisexual": "Omnisexual",
    "pansexual": "Pansexual",
    "plural": "Plural",
    "poc": "POC",
    "polyamorous": "Polyamorous",
    "polysexual": "Polysexual",
    "pride": "Pride",
    "queer": "Queer",
    "transfeminine": "Transfeminine",
    "transgender": "Transgender",
    "transmasculine": "Transmasculine",
}

# Extra search terms, so the picker finds a flag by the word people reach for
# first rather than only by its formal name.
flagAliases: dict[str, tuple[str, ...]] = {
    "aroace": ("aro ace", "aroaceflux"),
    "aromantic": ("aro",),
    "asexual": ("ace",),
    "bisexual": ("bi",),
    "genderfluid": ("fluid",),
    "lesbian": ("wlw", "sapphic"),
    "mlm": ("gay", "achillean", "gay men", "vincian"),
    "mlm_old": ("gay",),
    "nonbinary": ("enby", "nb"),
    "pansexual": ("pan",),
    "plural": ("system", "did", "osdd"),
    "poc": ("progress", "inclusive", "black", "brown"),
    "polyamorous": ("poly",),
    "pride": ("rainbow", "lgbt", "lgbtq", "gay pride"),
    "transgender": ("trans",),
}

cutouts = ("circle", "square", "overlay")

# Tried in order until the encoded GIF fits the upload budget.
animationSteps = ((256, 36), (224, 30), (192, 24), (160, 20), (128, 16))

# Seconds for one full turn, held constant so the spin reads the same at
# every fallback size.
rotationSeconds = 3.0

stillSize = 512
transparentIndex = 255


class PrideOptions(NamedTuple):
    columns: tuple[tuple[str, ...], ...]
    cutout: str = "circle"
    cutoutSize: int = 90
    opacity: int = 100
    rotation: int = 0
    isGradient: bool = False
    resizeInwards: bool = True


def parseHex(value: str) -> tuple[int, int, int]:
    text = value.lstrip("#")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def mixColors(
    start: tuple[int, int, int], end: tuple[int, int, int], amount: float
) -> tuple[int, int, int]:
    return (
        round(start[0] + (end[0] - start[0]) * amount),
        round(start[1] + (end[1] - start[1]) * amount),
        round(start[2] + (end[2] - start[2]) * amount),
    )


def gradientStrip(colors: tuple[str, ...], size: int) -> Image.Image:
    """A one-pixel-wide gradient down the doubled layer.

    Canvas gradients run top to bottom across the canvas only, and clamp to the
    end colours beyond it, so the padding above and below stays solid.
    """
    offset = size // 2
    stops = [parseHex(color) for color in colors]
    last = len(stops) - 1

    strip = Image.new("RGB", (1, size * 2))
    pixels = strip.load()
    if pixels is None:
        return strip

    for y in range(size * 2):
        if last == 0:
            pixels[0, y] = stops[0]
            continue
        position = min(1.0, max(0.0, (y - offset) / size)) * last
        index = min(int(position), last - 1)
        pixels[0, y] = mixColors(stops[index], stops[index + 1], position - index)
    return strip


def paintFlag(size: int, options: PrideOptions) -> Image.Image:
    """The flag, flat and unrotated, on a layer twice the canvas size."""
    offset = size // 2
    span = size * 2
    layer = Image.new("RGBA", (span, span), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    columnCount = len(options.columns)
    for index, colors in enumerate(options.columns):
        # The outer columns stretch into the padding so a turn never uncovers
        # a corner; the inner ones only span their own slice.
        left = 0 if index == 0 else offset + size * index // columnCount
        right = (
            span
            if index == columnCount - 1
            else offset + size * (index + 1) // columnCount
        )

        if options.isGradient:
            strip = gradientStrip(colors, size).resize((right - left, span))
            layer.paste(strip, (left, 0))
            continue

        for stripe, color in enumerate(colors):
            top = 0 if stripe == 0 else offset + size * stripe // len(colors)
            bottom = (
                span
                if stripe == len(colors) - 1
                else offset + size * (stripe + 1) // len(colors)
            )
            draw.rectangle((left, top, right - 1, bottom - 1), fill=parseHex(color))

    return layer


def flagLayer(base: Image.Image, size: int, angle: float, opacity: int) -> Image.Image:
    """Rotate the doubled layer and crop the canvas back out of the middle."""
    offset = size // 2
    # Canvas rotates clockwise for a positive angle; Pillow rotates the other way.
    turned = base.rotate(-angle, resample=Image.Resampling.BILINEAR)
    layer = turned.crop((offset, offset, offset + size, offset + size))

    if opacity < 100:
        alpha = layer.getchannel("A").point(lambda value: value * opacity // 100)
        layer.putalpha(alpha)
    return layer


def cutoutMask(size: int, options: PrideOptions) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    inset = size * (100 - options.cutoutSize) / 200

    if options.cutout == "square":
        draw.rectangle((inset, inset, size - inset - 1, size - inset - 1), fill=255)
    else:
        radius = (size / 2) * options.cutoutSize / 100
        centre = size / 2
        draw.ellipse(
            (centre - radius, centre - radius, centre + radius, centre + radius),
            fill=255,
        )
    return mask


def placeAvatar(avatar: Image.Image, size: int, options: PrideOptions) -> Image.Image:
    """The avatar on a canvas-sized transparent layer, scaled as the site does."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    if options.resizeInwards and options.cutout != "overlay":
        inner = max(1, round(size * options.cutoutSize / 100))
        offset = (size - inner) // 2
        layer.paste(
            avatar.resize((inner, inner), Image.Resampling.LANCZOS), (offset, offset)
        )
    else:
        layer.paste(avatar.resize((size, size), Image.Resampling.LANCZOS), (0, 0))
    return layer


def composeFrame(
    avatarLayer: Image.Image,
    mask: Image.Image | None,
    flag: Image.Image,
    size: int,
    options: PrideOptions,
) -> Image.Image:
    if options.cutout == "overlay":
        # Avatar underneath, flag painted over the top.
        return Image.alpha_composite(avatarLayer, flag)

    # Flag behind, avatar clipped into the hole in the middle.
    frame = flag.copy()
    combined = avatarLayer.getchannel("A")
    if mask is not None:
        combined = Image.new("L", (size, size), 0)
        combined.paste(avatarLayer.getchannel("A"), (0, 0), mask)
    frame.paste(avatarLayer, (0, 0), combined)
    return frame


def renderFrame(
    avatar: Image.Image, size: int, options: PrideOptions, angle: float
) -> Image.Image:
    flat = paintFlag(size, options)
    flag = flagLayer(flat, size, angle, options.opacity)
    avatarLayer = placeAvatar(avatar, size, options)
    mask = None if options.cutout == "overlay" else cutoutMask(size, options)
    return composeFrame(avatarLayer, mask, flag, size, options)


def renderStill(avatar: Image.Image, options: PrideOptions) -> bytes:
    frame = renderFrame(avatar, stillSize, options, options.rotation)
    buffer = io.BytesIO()
    frame.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def toPalette(frame: Image.Image) -> Image.Image:
    """Quantise to 255 colours, keeping the last slot for transparency."""
    flat = frame.convert("RGB").quantize(colors=transparentIndex)
    clear = frame.getchannel("A").point(lambda value: 255 if value < 128 else 0)
    if clear.getbbox() is not None:
        flat.paste(transparentIndex, clear)
    return flat


def encodeGif(
    avatar: Image.Image, options: PrideOptions, size: int, count: int
) -> bytes:
    flat = paintFlag(size, options)
    avatarLayer = placeAvatar(avatar, size, options)
    mask = None if options.cutout == "overlay" else cutoutMask(size, options)

    frames = []
    for step in range(count):
        angle = options.rotation + step * 360 / count
        flag = flagLayer(flat, size, angle, options.opacity)
        frames.append(toPalette(composeFrame(avatarLayer, mask, flag, size, options)))

    buffer = io.BytesIO()
    frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=max(20, round(rotationSeconds * 1000 / count)),
        loop=0,
        disposal=2,
        transparency=transparentIndex,
        optimize=False,
    )
    return buffer.getvalue()


class Rendered(NamedTuple):
    data: bytes
    extension: str
    size: int
    frames: int


def render(avatar: Image.Image, options: PrideOptions, budget: int) -> Rendered:
    """Animated if it fits the budget, otherwise the still fallback."""
    if not math.isfinite(budget) or budget <= 0:
        budget = 10 * 1024 * 1024

    for size, count in animationSteps:
        data = encodeGif(avatar, options, size, count)
        if len(data) <= budget:
            return Rendered(data, "gif", size, count)

    return Rendered(renderStill(avatar, options), "png", stillSize, 1)


def renderPng(avatar: Image.Image, options: PrideOptions) -> Rendered:
    return Rendered(renderStill(avatar, options), "png", stillSize, 1)
