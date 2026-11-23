# PC-side smoke test: renders a synthetic wttr.in j1 payload with pico_card
# and prints the two planes as ASCII, plus plane-size checks.
import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pico"))
from pico_card import dow_from_date, parse_j1, render_card  # noqa: E402
from pico_canvas import Canvas  # noqa: E402

# --- sanity: dow_from_date vs python's weekday (Monday=0)
for i in range(7):
    d = datetime.date(2026, 11, 22 + i)
    ours = dow_from_date(d.isoformat())
    assert ours == d.weekday(), (d, ours, d.weekday())
print("dow_from_date: OK")

# --- synthetic wttr.in j1 for 2026-11-23 (Mon), painless 3-day forecast
def hourly(code):
    return [{"weatherCode": str(code)} for _ in range(9)]

j1 = {
    "current_condition": [{
        "temp_C": "3", "weatherCode": "122", "humidity": "86",
        "windspeedKmph": "12", "pressure": "1007", "weatherDesc": [{"value": "пасмурно"}],
    }],
    "nearest_area": [{"areaName": [{"value": "Варшава"}]}],
    "weather": [
        {"date": "2026-11-23", "maxtempC": "2", "mintempC": "1", "hourly": hourly(332)},
        {"date": "2026-11-24", "maxtempC": "3", "mintempC": "1", "hourly": hourly(386)},
        {"date": "2026-11-25", "maxtempC": "2", "mintempC": "-1", "hourly": hourly(116)},
    ],
}

card = parse_j1(j1)
print("city=%s temp=%s icon=%s cond=%s hum=%s days=%s" % (
    card["city"], card["temp_text"], card["icon"], card["cond_text"], card["hum"],
    [(d["name"], d["icon"], d["hi"], d["lo"]) for d in card["days"]]))

c = render_card(card)
assert len(c.black) == 5624 and len(c.red) == 5624

# Print ASCII preview: '#' black, 'R' red, '.' white.
for y in range(296):
    row = []
    for x in range(152):
        idx = y * 19 + x // 8
        bit = 0x80 >> (x % 8)
        r = bool(c.red[idx] & bit)
        k = bool(c.black[idx] & bit)
        row.append("R" if r and not k else ("#" if k else ("r" if r else ".")))
    print("".join(row))
print("render_test: OK")
