# Renders the Pico's weather card on the PC, with the same code the Pico
# runs. Live wttr.in data plus edge cases (long text, -18, 100 %, ...).
#
#   python tools/preview_card.py            -> card-preview.png (black/red)
#   python tools/preview_card.py --debug    -> card-debug.png + layout checks
#
# Debug: every element in its own colour, sector frames dashed, element boxes
# thin. Checks: boxes inside their sector and not overlapping each other, no
# pixel outside its element's box, no text overflowing its box, and at least
# MIN_GAP empty pixels between pixels of different elements. Exit code 1 if
# any check fails.

import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PICO = os.path.join(ROOT, "pico")
sys.path.insert(0, PICO)
os.chdir(PICO)                          # card_assets.bin is opened by name

import pico_card                         # noqa: E402
import pico_json                         # noqa: E402

CITY = "Warszawa"
MIN_GAP = 2           # pixels of clearance between different elements
SCALE = 3

PALETTE = [(230, 25, 75), (60, 180, 75), (0, 130, 200), (245, 130, 48), (145, 30, 180),
           (70, 200, 200), (240, 50, 230), (150, 150, 0), (0, 128, 128), (170, 110, 40),
           (128, 0, 0), (0, 0, 128), (128, 128, 128), (255, 120, 120), (40, 40, 40),
           (100, 100, 255), (0, 160, 0), (200, 0, 100), (90, 60, 0), (0, 90, 160),
           (180, 80, 180), (0, 0, 0), (200, 150, 0)]


def cards():
    live = pico_card.parse_j1(pico_json.fetch_j1("wttr.in", b"/Warszawa?format=j1"))
    live["city"] = CITY
    import datetime
    live["time"] = datetime.datetime.now().strftime("%H:%M")
    live["home"] = 22.5
    out = [("live", live)]

    def synth(temp, feels, code, chance, mm, wind, days, dates):
        icon, text = pico_card.cond(code)
        return {"city": CITY, "time": "23:59", "home": -10.5 if temp < 0 else 28.0, "temp": temp, "feels": feels, "wind": wind, "hum": 100,
                "chance": chance, "mm": mm, "icon": icon, "cond": text,
                "days": [{"date": dt, "dow": pico_card.dow_from_date(dt), "icon": ic, "hi": hi, "lo": lo}
                         for (ic, hi, lo), dt in zip(days, dates)]}

    out.append(("cold", synth(-18, -25, 392, 100, 12.5, 54,
                              [("snow", -12, -21), ("storm", -10, -19), ("fog", -5, -13)],
                              ["2026-12-29", "2026-12-30", "2026-12-31"])))
    out.append(("hot", synth(31, 34, 116, 0, 0.0, 4,
                             [("sun", 33, 21), ("part", 30, 19), ("sleet", 2, -1)],
                             ["2026-09-28", "2026-09-29", "2026-09-30"])))
    out.append(("rain", synth(12, 10, 359, 87, 4.25, 30,
                              [("rain", 14, 8), ("cloud", 11, 6), ("sun", 15, 4)],
                              ["2026-11-23", "2026-11-24", "2026-11-25"])))
    out.append(("long", synth(-7, -12, 311, 64, 0.3, 11,
                                [("sleet", -3, -9), ("snow", -1, -8), ("cloud", 0, -4)],
                                ["2026-02-07", "2026-02-08", "2026-02-09"])))
    return out


def plane_px(c, x, y):
    i, b = y * c.stride + x // 8, 0x80 >> (x % 8)
    return (c.red[i] & b) != 0, (c.black[i] & b) != 0


def to_bwr(c):
    img = Image.new("RGB", (c.w, c.h), (255, 255, 255))
    px = img.load()
    for y in range(c.h):
        for x in range(c.w):
            r, b = plane_px(c, x, y)
            if r:
                px[x, y] = (200, 30, 30)
            elif b:
                px[x, y] = (20, 20, 20)
    return img.resize((c.w * SCALE, c.h * SCALE), Image.NEAREST)


def boxes_overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def inside(inner, outer):
    return (inner[0] >= outer[0] and inner[1] >= outer[1] and
            inner[0] + inner[2] <= outer[0] + outer[2] and inner[1] + inner[3] <= outer[1] + outer[3])


def sector_of(box):
    for name, s in pico_card.SECTORS.items():
        if inside(box, s):
            return name
    return None


def check(c):
    problems = list(c.problems)
    els = c.elements
    # Boxes: in a sector, and no two overlap.
    for i, (n, b) in enumerate(els):
        if sector_of(b) is None:
            problems.append("box %s %r is not inside one sector" % (n, b))
        for n2, b2 in els[i + 1:]:
            if boxes_overlap(b, b2):
                problems.append("boxes overlap: %s %r / %s %r" % (n, b, n2, b2))
    # Every element must draw something.
    drawn = set(c.ids)
    for i, (n, b) in enumerate(els):
        if i + 1 not in drawn:
            problems.append("%s: drew nothing" % n)
    # Pixels: inside own box; clearance to other elements.
    w, h, ids = c.w, c.h, c.ids
    gaps = {}
    for y in range(h):
        for x in range(w):
            e = ids[y * w + x]
            if not e:
                continue
            n, (bx, by, bw, bh) = els[e - 1]
            if not (bx <= x < bx + bw and by <= y < by + bh):
                problems.append("%s: pixel %d,%d outside its box" % (n, x, y))
            for dy in range(-MIN_GAP, MIN_GAP + 1):
                for dx in range(-MIN_GAP, MIN_GAP + 1):
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < w and 0 <= yy < h:
                        e2 = ids[yy * w + xx]
                        if e2 and e2 != e:
                            d = max(abs(dx), abs(dy)) - 1      # empty pixels between
                            key = tuple(sorted((n, els[e2 - 1][0])))
                            gaps[key] = min(gaps.get(key, 99), d)
    for (a, b), d in sorted(gaps.items()):
        if d < MIN_GAP:
            problems.append("gap %s / %s is %d px (min %d)" % (a, b, d, MIN_GAP))
    # One line per distinct problem kind, so the list stays readable.
    seen, out = set(), []
    for p in problems:
        k = p.split(":")[0] if "outside" in p else p
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def to_debug(c):
    img = Image.new("RGB", (c.w, c.h), (255, 255, 255))
    px = img.load()
    for y in range(c.h):
        for x in range(c.w):
            e = c.ids[y * c.w + x]
            if e:
                px[x, y] = PALETTE[(e - 1) % len(PALETTE)]
    img = img.resize((c.w * SCALE, c.h * SCALE), Image.NEAREST)
    d = ImageDraw.Draw(img)
    for e, (n, (x, y, w, h)) in enumerate(c.elements):
        col = PALETTE[e % len(PALETTE)]
        d.rectangle([x * SCALE, y * SCALE, (x + w) * SCALE - 1, (y + h) * SCALE - 1], outline=col)
    for n, (x, y, w, h) in pico_card.SECTORS.items():
        for xx in range(x * SCALE, (x + w) * SCALE, 8):
            d.line([xx, y * SCALE, xx + 3, y * SCALE], fill=(0, 0, 0))
            d.line([xx, (y + h) * SCALE - 1, xx + 3, (y + h) * SCALE - 1], fill=(0, 0, 0))
    return img


def sheet(imgs, labels):
    gap, top = 16, 22
    s = Image.new("RGB", (sum(i.width for i in imgs) + gap * (len(imgs) + 1),
                          imgs[0].height + gap + top), (200, 200, 200))
    d = ImageDraw.Draw(s)
    x = gap
    for im, lab in zip(imgs, labels):
        d.text((x, 4), lab, fill=(0, 0, 0))
        s.paste(im, (x, top))
        x += im.width + gap
    return s


def main():
    debug = "--debug" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = args[0] if args else os.path.join(ROOT, "card-debug.png" if debug else "card-preview.png")
    imgs, labels, failed = [], [], False
    for name, card in cards():
        c = pico_card.render_card(card, debug=debug)
        if debug:
            probs = check(c)
            print("[%s] %s" % (name, "OK" if not probs else "%d problem(s)" % len(probs)))
            for p in probs:
                print("    " + p)
            failed |= bool(probs)
            imgs.append(to_debug(c))
        else:
            imgs.append(to_bwr(c))
        labels.append(name)
    sheet(imgs, labels).save(out)
    print(os.path.abspath(out))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
