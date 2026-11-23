# Generates the card's fonts and weather icons for the Pico W.
#
#   python tools/gen_card_assets.py
#
# Output (both uploaded to the Pico next to the other files):
#   demo/pico/card_assets.bin  all bitmaps, MONO_HLSB (MicroPython framebuf)
#   demo/pico/card_assets.py   index into the .bin: fonts and icons
#
# Fonts: DejaVu Sans (free licence, has Cyrillic and Polish letters), taken
# from matplotlib's bundled copy. Needs: pip install pillow matplotlib
#
# Each glyph is a cell of the font's full height; its bitmap is `w` pixels
# wide and the pen moves `adv` pixels. Icons have a black and a red plane.

import os
import string

import matplotlib
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "pico")
TTF = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")

CYR = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя"
LAT = string.ascii_letters + "ĄĆĘŁŃÓŚŹŻąćęłńóśźż"
NUM = "0123456789 .,:;-–−+°%/·()!?«»"

FONTS = {
    # name: (ttf, pixel size, charset)
    "title": ("DejaVuSans-Bold.ttf", 24, LAT + CYR + NUM),
    # Big temperature: two sizes, the smaller one for wide values like -18.
    "temp":  ("DejaVuSans-Bold.ttf", 46, "0123456789–°"),
    "temp2": ("DejaVuSans-Bold.ttf", 36, "0123456789–°"),
    "mid":   ("DejaVuSans-Bold.ttf", 17, LAT + CYR + NUM),   # Latin: city name
    "small": ("DejaVuSans.ttf", 13, CYR + LAT + NUM),
}

ICON_SIZES = (52, 30)
ICONS = ("sun", "part", "cloud", "fog", "rain", "sleet", "snow", "storm")


def pack(img):
    """1-bit PIL image -> MONO_HLSB bytes (bit 0x80 = leftmost pixel)."""
    w, h = img.size
    stride = (w + 7) // 8
    px = img.load()
    out = bytearray(stride * h)
    for y in range(h):
        for x in range(w):
            if px[x, y]:
                out[y * stride + x // 8] |= 0x80 >> (x % 8)
    return bytes(out)


def build_font(ttf, size, chars, blob):
    font = ImageFont.truetype(os.path.join(TTF, ttf), size)
    chars = "".join(sorted(set(chars)))
    top = min(font.getbbox(c, anchor="ls")[1] for c in chars if c != " ")
    bottom = max(font.getbbox(c, anchor="ls")[3] for c in chars if c != " ")
    h = bottom - top
    glyphs = {}
    for c in chars:
        adv = int(round(font.getlength(c)))
        l, _, r, _ = font.getbbox(c, anchor="ls")
        w = max(adv, r, 1)
        img = Image.new("1", (w, h), 0)
        d = ImageDraw.Draw(img)
        d.fontmode = "1"                       # hinted, no anti-aliasing
        d.text((0, -top), c, font=font, fill=1, anchor="ls")
        glyphs[c] = (len(blob), w, adv)
        blob += pack(img)
    return h, glyphs


# --- icons: drawn 8x larger, then box-filtered down and thresholded ---------

SS = 8


def _cloud(d, s, dx=0.0, dy=0.0, stroke=0.075):
    """Outlined cloud with white fill, in a unit box scaled by s."""
    parts = [(0.36, 0.56, 0.17), (0.56, 0.45, 0.22), (0.74, 0.60, 0.14)]
    body = (0.20, 0.56, 0.86, 0.74)

    def draw(grow, fill):
        for cx, cy, r in parts:
            r += grow
            d.ellipse([(cx - r + dx) * s, (cy - r + dy) * s,
                       (cx + r + dx) * s, (cy + r + dy) * s], fill=fill)
        x0, y0, x1, y1 = body
        d.rounded_rectangle([(x0 - grow + dx) * s, (y0 - grow + dy) * s,
                             (x1 + grow + dx) * s, (y1 + grow + dy) * s],
                            radius=(0.09 + grow) * s, fill=fill)

    draw(stroke / 2, 255)
    draw(-stroke / 2, 0)


def _sun(d, s, cx, cy, r, rays=True):
    import math
    d.ellipse([(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s], fill=255)
    if rays:
        for i in range(8):
            a = i * math.pi / 4
            x0, y0 = cx + math.cos(a) * r * 1.45, cy + math.sin(a) * r * 1.45
            x1, y1 = cx + math.cos(a) * r * 2.05, cy + math.sin(a) * r * 2.05
            d.line([x0 * s, y0 * s, x1 * s, y1 * s], fill=255, width=max(1, int(0.07 * s)))


def _drops(d, s, y, kinds):
    xs = (0.36, 0.53, 0.70)
    for x, k in zip(xs, kinds):
        if k == "rain":
            d.line([x * s, y * s, (x - 0.06) * s, (y + 0.17) * s], fill=255,
                   width=max(1, int(0.075 * s)))
        else:  # snow: a solid flake dot with a small cross
            r = 0.055
            d.ellipse([(x - r) * s, (y + 0.06 - r) * s, (x + r) * s, (y + 0.06 + r) * s], fill=255)
            d.ellipse([(x - 0.05 - r) * s, (y + 0.18 - r) * s, (x - 0.05 + r) * s, (y + 0.18 + r) * s], fill=255)


def draw_icon(name, size):
    s = size * SS
    black = Image.new("L", (s, s), 0)
    red = Image.new("L", (s, s), 0)
    db, dr = ImageDraw.Draw(black), ImageDraw.Draw(red)
    if name == "sun":
        _sun(dr, s, 0.5, 0.5, 0.2)
    elif name == "part":
        _sun(dr, s, 0.30, 0.30, 0.15)
        # Erase the sun under (and just around) the cloud, then draw it.
        red.paste(0, mask=_silhouette(s, 0.08, 0.14))
        _cloud(db, s, 0.08, 0.14)
    elif name == "cloud":
        _cloud(db, s, 0, 0.02)
    elif name == "fog":
        _cloud(db, s, 0, -0.10)
        for i, (x0, x1) in enumerate(((0.18, 0.70), (0.30, 0.84), (0.18, 0.62))):
            y = 0.76 + i * 0.09
            db.line([x0 * s, y * s, x1 * s, y * s], fill=255, width=max(1, int(0.06 * s)))
    elif name in ("rain", "snow", "sleet", "storm"):
        _cloud(db, s, 0, -0.14)
        if name == "rain":
            _drops(db, s, 0.68, ("rain", "rain", "rain"))
        elif name == "snow":
            _drops(db, s, 0.66, ("snow", "snow", "snow"))
        elif name == "sleet":
            _drops(db, s, 0.68, ("rain", "snow", "rain"))
        else:
            dr.polygon([(0.56 * s, 0.58 * s), (0.40 * s, 0.80 * s), (0.52 * s, 0.80 * s),
                        (0.44 * s, 0.98 * s), (0.66 * s, 0.72 * s), (0.54 * s, 0.72 * s),
                        (0.64 * s, 0.58 * s)], fill=255)
    out = []
    for img in (black, red):
        small = img.resize((size, size), Image.BOX)
        out.append(small.point(lambda v: 1 if v >= 110 else 0, "1"))
    return out


def _silhouette(s, dx, dy):
    # Filled cloud shape, a bit larger than the outline so the sun gets a
    # white gap around the cloud.
    m2 = Image.new("L", (s, s), 0)
    d2 = ImageDraw.Draw(m2)
    for cx, cy, r in [(0.36, 0.56, 0.17), (0.56, 0.45, 0.22), (0.74, 0.60, 0.14)]:
        r += 0.10
        d2.ellipse([(cx - r + dx) * s, (cy - r + dy) * s, (cx + r + dx) * s, (cy + r + dy) * s], fill=255)
    d2.rounded_rectangle([(0.10 + dx) * s, (0.46 + dy) * s, (0.96 + dx) * s, (0.84 + dy) * s],
                         radius=0.19 * s, fill=255)
    return m2


# Hand-drawn pixel icons (black only), crisper than a scaled drawing at
# this size. "#" = black.
PIXEL_ICONS = {
    "home": [
        "......#......",
        ".....###.....",
        "....##.##....",
        "...##...##...",
        "..##.....##..",
        ".##.......##.",
        "##.........##",
        ".#.........#.",
        ".#...###...#.",
        ".#...#.#...#.",
        ".#...#.#...#.",
        ".#...#.#...#.",
        ".###########.",
    ],
}


def pixel_icon(rows):
    img = Image.new("1", (len(rows[0]), len(rows)), 0)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                img.putpixel((x, y), 1)
    return img


def main():
    blob = bytearray()
    fonts = {}
    for name, (ttf, size, chars) in FONTS.items():
        fonts[name] = build_font(ttf, size, chars, blob)
    icons = {}
    for size in ICON_SIZES:
        for name in ICONS:
            b, r = draw_icon(name, size)
            ob = len(blob)
            blob += pack(b)
            orr = len(blob)
            blob += pack(r)
            icons["%s%d" % (name, size)] = (size, ob, orr)

    for name, rows in PIXEL_ICONS.items():
        img = pixel_icon(rows)
        size = img.size[0]
        assert img.size == (size, size)
        ob = len(blob)
        blob += pack(img)
        orr = len(blob)
        blob += pack(Image.new("1", img.size, 0))
        icons["%s%d" % (name, size)] = (size, ob, orr)

    with open(os.path.join(OUT, "card_assets.bin"), "wb") as f:
        f.write(blob)
    with open(os.path.join(OUT, "card_assets.py"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# Generated by tools/gen_card_assets.py from DejaVu Sans. Do not edit.\n")
        f.write("# Bitmaps live in card_assets.bin (MONO_HLSB).\n\n")
        f.write("BIN = 'card_assets.bin'\n\n")
        f.write("# font: (cell height, {char: (offset, width, advance)})\n")
        f.write("FONTS = {\n")
        for name, (h, glyphs) in fonts.items():
            f.write("    %r: (%d, {\n" % (name, h))
            for c, v in glyphs.items():
                f.write("        %r: %r,\n" % (c, v))
            f.write("    }),\n")
        f.write("}\n\n# icon: (size, black offset, red offset)\nICONS = {\n")
        for k, v in icons.items():
            f.write("    %r: %r,\n" % (k, v))
        f.write("}\n")
    print("card_assets.bin: %d bytes, %d fonts, %d icons" % (len(blob), len(fonts), len(icons)))


if __name__ == "__main__":
    main()
