# Card model for the SE2266: weather data (wttr.in j1) -> 152x296 planes.
#
# Layout (portrait, 152 x 296):
#   city (Latin, as configured), date and update time, red line
#   big icon + big red temperature, indoor temperature (Home Assistant)
#   condition, feels-like, precipitation, wind, red line
#   three forecast rows: day, icon, max / min
# All text except the city is Russian.

from pico_canvas import Canvas

W = 152
H = 296

DAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
MONTHS = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля",
          "августа", "сентября", "октября", "ноября", "декабря")

# WorldWeatherOnline codes (wttr.in) -> (icon, short Russian text).
_COND = {
    113: ("sun", "Ясно"),
    116: ("part", "Малооблачно"),
    119: ("cloud", "Облачно"),
    122: ("cloud", "Пасмурно"),
    143: ("fog", "Дымка"),
    248: ("fog", "Туман"),
    260: ("fog", "Туман"),
    176: ("rain", "Местами дождь"),
    263: ("rain", "Морось"),
    266: ("rain", "Морось"),
    293: ("rain", "Небольшой дождь"),
    296: ("rain", "Небольшой дождь"),
    353: ("rain", "Небольшой дождь"),
    299: ("rain", "Дождь"),
    302: ("rain", "Дождь"),
    305: ("rain", "Ливень"),
    308: ("rain", "Сильный ливень"),
    356: ("rain", "Ливень"),
    359: ("rain", "Сильный ливень"),
    179: ("snow", "Местами снег"),
    227: ("snow", "Позёмка"),
    230: ("snow", "Метель"),
    323: ("snow", "Небольшой снег"),
    326: ("snow", "Небольшой снег"),
    368: ("snow", "Небольшой снег"),
    329: ("snow", "Снег"),
    332: ("snow", "Снег"),
    335: ("snow", "Снегопад"),
    338: ("snow", "Снегопад"),
    371: ("snow", "Снегопад"),
    182: ("sleet", "Мокрый снег"),
    185: ("sleet", "Изморозь"),
    281: ("sleet", "Изморозь"),
    284: ("sleet", "Изморозь"),
    311: ("sleet", "Ледяной дождь"),
    314: ("sleet", "Ледяной дождь"),
    317: ("sleet", "Мокрый снег"),
    320: ("sleet", "Мокрый снег"),
    350: ("sleet", "Ледяная крупа"),
    362: ("sleet", "Мокрый снег"),
    365: ("sleet", "Мокрый снег"),
    374: ("sleet", "Ледяная крупа"),
    377: ("sleet", "Ледяная крупа"),
    200: ("storm", "Гроза"),
    386: ("storm", "Гроза"),
    389: ("storm", "Гроза"),
    392: ("storm", "Гроза, снег"),
    395: ("storm", "Гроза, снег"),
}


def cond(code):
    return _COND.get(code, ("cloud", "Облачно"))


def dow_from_date(s):
    # ISO date "YYYY-MM-DD" -> weekday, Monday = 0.
    y = int(s[0:4])
    m = int(s[5:7])
    d = int(s[8:10])
    if m < 3:
        m += 12
        y -= 1
    k = y % 100
    j = y // 100
    h = (d + (13 * (m + 1)) // 5 + k + k // 4 + j // 4 + 5 * j) % 7
    # Zeller h: 0=Saturday; map to Monday=0.
    return (h - 2) % 7


def deg(v, minus="–"):
    """Temperature text with a minus sign and no '-0'."""
    v = int(v)
    return (minus if v < 0 else "") + str(abs(v)) + "°"


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def parse_j1(j):
    cc = j["current_condition"][0]
    code = int(cc["weatherCode"])
    icon, text = cond(code)
    days = []
    for w in j["weather"][:3]:
        hourly = w["hourly"]
        days.append({
            "date": w["date"],
            "dow": dow_from_date(w["date"]),
            "icon": cond(int(hourly[4]["weatherCode"]))[0],
            "hi": int(w["maxtempC"]),
            "lo": int(w["mintempC"]),
        })
    # Precipitation today: highest 3-hour chance of rain or snow, and the
    # day's total in mm (sum of the 3-hour amounts).
    h0 = j["weather"][0]["hourly"]
    chance = 0
    mm = 0.0
    for h in h0:
        chance = max(chance, int(_num(h.get("chanceofrain"))), int(_num(h.get("chanceofsnow"))))
        mm += _num(h.get("precipMM"))
    return {
        "city": j["nearest_area"][0]["areaName"][0]["value"],
        "temp": int(cc["temp_C"]),
        "feels": int(cc.get("FeelsLikeC", cc["temp_C"])),
        "wind": int(cc.get("windspeedKmph", 0)),
        "hum": int(cc["humidity"]),
        "chance": chance,
        "mm": mm,
        "icon": icon,
        "cond": text,
        "days": days,
    }


# --- layout ----------------------------------------------------------------
# Three invisible sectors; every element has its own box (x, y, w, h) and the
# boxes do not overlap. tools/preview_card.py --debug draws each element in
# its own colour and checks that nothing leaves its box or touches another.

SECTORS = {
    "city": (0, 0, W, 50),
    "now": (0, 50, W, 136),
    "days": (0, 186, W, 110),
}

BOX = {
    # sector "city"
    "city": (6, 2, 140, 27),
    "date": (6, 31, 100, 15),
    "time": (110, 31, 36, 15),
    "rule1": (6, 48, 140, 2),
    # sector "now"
    "icon": (4, 54, 52, 52),
    "temp": (60, 52, 88, 38),
    "home": (60, 91, 88, 15),
    "cond": (4, 109, 144, 20),
    "feels": (4, 131, 144, 15),
    "precip": (4, 149, 144, 15),
    "wind": (4, 167, 144, 15),
    "rule2": (6, 184, 140, 2),
}

ROW_Y = 188
ROW_H = 36


def row_boxes(i):
    y = ROW_Y + i * ROW_H
    return {
        "day": (6, y, 40, 20),
        "ddate": (6, y + 20, 40, 15),
        "dicon": (52, y + 3, 30, 30),
        "hi": (88, y, 58, 20),
        "lo": (88, y + 20, 58, 15),
    }


def _mm(v):
    if v < 0.05:
        return "0 мм"
    if v < 10:
        s = "%.1f" % v
        return s.replace(".", ",") + " мм"
    return "%d мм" % int(v + 0.5)


def render_card(card, debug=False):
    c = Canvas(W, H, debug=debug)

    # --- sector "city" -------------------------------------------------------
    c.text_box("city", BOX["city"], card["city"], "mid", align="c")
    if card["days"]:
        d0 = card["days"][0]
        date = "%d %s" % (int(d0["date"][8:10]), MONTHS[int(d0["date"][5:7]) - 1])
        c.text_box("date", BOX["date"], date, "small")
    if card.get("time"):
        # Local time of this update (the card is redrawn every hour).
        c.text_box("time", BOX["time"], card["time"], "small", align="r")
    c.rule("rule1", BOX["rule1"], red=True)

    # --- sector "now" --------------------------------------------------------
    c.icon_box("icon", BOX["icon"], card["icon"])
    c.text_box("temp", BOX["temp"], deg(card["temp"]), ("temp", "temp2"),
               align="r", red=True)
    if card.get("home") is not None:
        # Indoor temperature from Home Assistant, one decimal.
        h = card["home"]
        t = ("–" if h < 0 else "") + ("%.1f" % abs(h)).replace(".", ",") + "°"
        # House icon just left of the value, both right-aligned in BOX["home"].
        x, y, w, hh = BOX["home"]
        tw = c.measure(t, "small")
        c.text_box("home", (x + w - tw, y, tw, hh), t, "small", align="r")
        c.icon_box("homeicon", (x + w - tw - 4 - 13, y + 1, 13, 13), "home")
    c.text_box("cond", BOX["cond"], card["cond"], ("mid", "small"), align="c")
    c.text_box("feels", BOX["feels"], "ощущается " + deg(card["feels"]), "small", align="c")
    c.text_box("precip", BOX["precip"],
               "осадки %d%% · %s" % (card["chance"], _mm(card["mm"])), "small", align="c")
    ms = (card["wind"] * 10 + 18) // 36          # km/h -> m/s, rounded
    c.text_box("wind", BOX["wind"], "ветер %d м/с" % ms, "small", align="c")
    c.rule("rule2", BOX["rule2"], red=True)

    # --- sector "days" -------------------------------------------------------
    for i, d in enumerate(card["days"][:3]):
        b = row_boxes(i)
        c.text_box("day%d" % i, b["day"], DAYS[d["dow"]], "mid", valign="b", red=(i == 0))
        c.text_box("ddate%d" % i, b["ddate"], "%d.%s" % (int(d["date"][8:10]), d["date"][5:7]),
                   "small", valign="t")
        c.icon_box("dicon%d" % i, b["dicon"], d["icon"])
        c.text_box("hi%d" % i, b["hi"], deg(d["hi"]), "mid", align="r", valign="b")
        c.text_box("lo%d" % i, b["lo"], deg(d["lo"]), "small", align="r", valign="t")
    return c
