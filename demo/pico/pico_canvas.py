# MicroPython 2D canvas for the 152x296 SE2266 card.
# Planes pack like demo/tag/card.h: 19 bytes per row, bit 0x80>>(x%8) =
# leftmost pixel (framebuf MONO_HLSB). 1 in `black` = black, 1 in `red` = red.
#
# Fonts and icons come from card_assets.py / card_assets.bin, made on the PC
# by tools/gen_card_assets.py. On the Pico, glyphs are blitted with framebuf;
# on CPython (tools/preview_card.py) a plain Python fallback is used.

import card_assets

try:
    import framebuf
except ImportError:            # CPython preview
    framebuf = None

# Bitmaps are read from flash one glyph/icon at a time into a small reused
# buffer: the whole card_assets.bin (~30 KB) does not fit in the Pico's heap
# next to Wi-Fi and the card planes.
_file = None
_buf = bytearray(512)


def _read(off, n):
    global _file, _buf
    if _file is None:
        _file = open(card_assets.BIN, "rb")
    if n > len(_buf):
        _buf = bytearray(n)
    mv = memoryview(_buf)[:n]
    _file.seek(off)
    _file.readinto(mv)
    return mv


class Canvas:
    def __init__(self, w=152, h=296, debug=False):
        self.w = w
        self.h = h
        self.stride = (w + 7) // 8
        self.black = bytearray(self.stride * h)
        self.red = bytearray(self.stride * h)
        # Debug (PC only): every pixel remembers which element drew it, so
        # tools/preview_card.py can colour elements and check the gaps.
        self.debug = debug
        self.ids = bytearray(w * h) if debug else None
        self.elements = []            # (name, box) per element id 1..n
        self.problems = []
        self._cur = 0
        if framebuf and not debug:
            fmt = framebuf.MONO_HLSB
            self._fb = (framebuf.FrameBuffer(self.black, w, h, fmt),
                        framebuf.FrameBuffer(self.red, w, h, fmt))

    # --- primitives ---------------------------------------------------------

    def _fast(self):
        return framebuf is not None and not self.debug

    def _set(self, buf, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            buf[y * self.stride + x // 8] |= 0x80 >> (x % 8)
            if self.ids is not None:
                i = y * self.w + x
                if self.ids[i] and self.ids[i] != self._cur:
                    self.problems.append("overlap at %d,%d: %s / %s" % (
                        x, y, self.elements[self.ids[i] - 1][0], self.elements[self._cur - 1][0]))
                self.ids[i] = self._cur

    def begin(self, name, box):
        """Start a new element (debug bookkeeping only)."""
        self.elements.append((name, box))
        self._cur = len(self.elements)

    def rect(self, x, y, w, h, red=False):
        if self._fast():
            self._fb[1 if red else 0].fill_rect(x, y, w, h, 1)
            return
        buf = self.red if red else self.black
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self._set(buf, xx, yy)

    def _blit(self, off, w, h, x, y, red):
        """OR a MONO_HLSB bitmap from the assets blob into a plane."""
        stride = (w + 7) // 8
        blob = _read(off, stride * h)
        if self._fast():
            src = framebuf.FrameBuffer(blob, w, h, framebuf.MONO_HLSB)
            self._fb[1 if red else 0].blit(src, x, y, 0)
            return
        buf = self.red if red else self.black
        for yy in range(h):
            row = yy * stride
            for xx in range(w):
                if blob[row + xx // 8] & (0x80 >> (xx % 8)):
                    self._set(buf, x + xx, y + yy)

    # --- text -----------------------------------------------------------------

    def font_height(self, font):
        return card_assets.FONTS[font][0]

    def measure(self, s, font, track=0):
        glyphs = card_assets.FONTS[font][1]
        w = 0
        for ch in s:
            g = glyphs.get(ch) or glyphs.get("?")
            w += g[2] + track
        return w - track if s else 0

    def text(self, x, y, s, font, red=False, track=0):
        """Draw `s` with its cell top at y. Returns the x after the text."""
        h, glyphs = card_assets.FONTS[font]
        for ch in s:
            g = glyphs.get(ch) or glyphs.get("?")
            off, w, adv = g
            if ch != " ":
                self._blit(off, w, h, x, y, red)
            x += adv + track
        return x

    def text_box(self, name, box, s, fonts, align="l", valign="m", red=False, track=0):
        """Draw `s` inside box (x, y, w, h) with the first font from `fonts`
        that fits. align: l / c / r, valign: t / m / b. Returns the font."""
        x, y, w, h = box
        self.begin(name, box)
        if isinstance(fonts, str):
            fonts = (fonts,)
        font = fonts[-1]
        for f in fonts:
            if self.measure(s, f, track) <= w and self.font_height(f) <= h:
                font = f
                break
        if self.debug:
            glyphs = card_assets.FONTS[font][1]
            missing = "".join(sorted(set(ch for ch in s if ch not in glyphs)))
            if missing:
                self.problems.append("%s: font %s has no %r" % (name, font, missing))
        tw, th = self.measure(s, font, track), self.font_height(font)
        if tw > w or th > h:
            self.problems.append("%s: %r does not fit %dx%d (needs %dx%d)" % (name, s, w, h, tw, th))
        tx = x if align == "l" else x + w - tw if align == "r" else x + (w - tw) // 2
        ty = y if valign == "t" else y + h - th if valign == "b" else y + (h - th) // 2
        self.text(tx, ty, s, font, red, track)
        return font

    def rule(self, name, box, red=False):
        """A filled bar filling its box (used for the red separator lines)."""
        self.begin(name, box)
        self.rect(box[0], box[1], box[2], box[3], red)

    # --- icons ----------------------------------------------------------------

    def icon_box(self, name, box, kind):
        """Icon centred in box; the largest icon size that fits is used."""
        x, y, w, h = box
        self.begin(name, box)
        sizes = sorted({v[0] for v in card_assets.ICONS.values()}, reverse=True)
        size = next((s for s in sizes if s <= w and s <= h), sizes[-1])
        if size > w or size > h:
            self.problems.append("%s: icon %d does not fit %dx%d" % (name, size, w, h))
        sz, ob, orr = card_assets.ICONS["%s%d" % (kind, size)]
        ix, iy = x + (w - sz) // 2, y + (h - sz) // 2
        self._blit(ob, sz, sz, ix, iy, False)
        self._blit(orr, sz, sz, ix, iy, True)
