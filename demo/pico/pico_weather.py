# MicroPython firmware for the Pico W weather gateway.
#
#   - connects to Wi-Fi (SSID and password from secrets.py),
#   - updates the card right after power-up, then at every :00 and :30 of
#     the wall clock (Warsaw time; the clock comes from NTP, or from the
#     HTTP Date header of the weather answer when NTP does not answer),
#   - an update: fetch https://wttr.in/Warszawa?format=j1, render the card
#     (pico_card), write it into the tag's RAM over SWD (pico_swd),
#   - serves a small web page (port 80) with the status and an "Обновить"
#     button that runs an update right away. Address: printed on the serial
#     console at boot, and http://eink-weather.local where mDNS works.
#
# Upload to the Pico W (tools\pico_upload.ps1): secrets.py, pico_ha.py, pico_json.py,
# pico_weather.py, pico_canvas.py, pico_card.py, card_assets.py,
# card_assets.bin, pico_swd.py, main.py.

import gc
import time

import asyncio
import machine
import network

from pico_card import parse_j1, render_card
import pico_json
import pico_swd

# Wi-Fi and Home Assistant credentials live in secrets.py (not in git; see
# secrets_example.py).
import secrets
from secrets import SSID, PASSWORD
import pico_ha

# Indoor temperature shown under the big one (Home Assistant entity).
HA_ENTITY = "sensor.home_temperature_sensor_temperature"

# Name printed on the card. wttr.in turns the query into coordinates and its
# nearest_area is the closest district (for Warszawa: "Powisle"), so the
# city name is fixed here instead of taken from the answer.
CITY = "Warszawa"
QUERY = b"/Warszawa?format=j1"
HOSTNAME = "eink-weather"
PERIOD = 30 * 60          # update at :00 and :30
RETRY = 120               # after a failed update, try again this soon
# Power-up: the card is always redrawn once after the Pico boots, whatever
# the clock says. Until that first update succeeds it is retried this often,
# and a Wi-Fi failure at boot no longer stops the program.
BOOT_DELAY = 3            # s: let the tag (powered at the same time) finish its init
BOOT_RETRY = 20
NTP_HOSTS = ("pool.ntp.org", "time.google.com", "time.cloudflare.com")

state = {
    "status": "старт",
    "last_ok": "",        # Warsaw time of the last good update
    "last_error": "",
    "next": "",
    "clock": "нет",       # where the clock came from: ntp / http / нет
    "summary": "",
    "home": "",           # Home Assistant reading or its problem
    "ip": "",
}
_force = asyncio.Event()
_busy = False


# --- clock ------------------------------------------------------------------

def _last_sunday(year, month):
    """UTC timestamp of 01:00 on the last Sunday of the month (EU DST switch)."""
    t = time.mktime((year, month, 31, 1, 0, 0, 0, 0))
    wd = time.gmtime(t)[6]                 # Monday = 0 ... Sunday = 6
    return t - ((wd + 1) % 7) * 86400


def clock_ok():
    return time.gmtime()[0] >= 2025


def warsaw_tuple(t=None):
    if t is None:
        t = time.time()
    y = time.gmtime(t)[0]
    summer = _last_sunday(y, 3) <= t < _last_sunday(y, 10)
    return time.gmtime(t + (7200 if summer else 3600))


def warsaw_hhmm(t=None):
    if not clock_ok():
        return ""
    lt = warsaw_tuple(t)
    return "%02d:%02d" % (lt[3], lt[4])


def _set_rtc_utc(y, mo, d, hh, mm, ss):
    wd = time.gmtime(time.mktime((y, mo, d, hh, mm, ss, 0, 0)))[6]
    machine.RTC().datetime((y, mo, d, wd, hh, mm, ss, 0))


def sync_clock():
    """Set the RTC to UTC: NTP first, then the weather answer's Date header."""
    try:
        import ntptime
        if hasattr(ntptime, "timeout"):
            ntptime.timeout = 3
        for host in NTP_HOSTS:
            try:
                ntptime.host = host
                ntptime.settime()
                state["clock"] = "ntp"
                return True
            except Exception as e:
                print("NTP %s: %r" % (host, e))
    except ImportError:
        pass
    d = pico_json.http_date
    if d:
        _set_rtc_utc(*d)
        state["clock"] = "http"
        return True
    return clock_ok()


def seconds_to_next_slot():
    if not clock_ok():
        return PERIOD
    t = time.time()
    return PERIOD - (t % PERIOD) + 2      # +2 s: land just after :00 / :30


# --- Wi-Fi ------------------------------------------------------------------

def wlan():
    return network.WLAN(getattr(network, "STA_IF", network.WLAN.IF_STA))


def connect():
    try:
        network.hostname(HOSTNAME)
    except Exception:
        pass
    sta = wlan()
    sta.active(True)
    for _ in range(30):
        if sta.isconnected():
            break
        try:
            sta.connect(SSID, PASSWORD)
        except Exception:
            pass
        time.sleep(2)
    if not sta.isconnected():
        raise RuntimeError("cannot connect to " + SSID)
    state["ip"] = sta.ifconfig()[0]


# --- on-board LED -------------------------------------------------------------
# Pico W: the LED sits on the Wi-Fi chip, Pin("LED"). Power-up: a few quick
# blinks. During an update it blinks from a timer, because update() blocks.

try:
    _led = machine.Pin("LED", machine.Pin.OUT)
except Exception:
    _led = None
_led_timer = None
LED_BOOT_BLINKS = 5
LED_UPDATE_MS = 250          # half-period while updating


def _led_set(v):
    if _led is not None:
        try:
            _led.value(v)
        except Exception:
            pass


def led_boot():
    for _ in range(LED_BOOT_BLINKS):
        _led_set(1)
        time.sleep_ms(120)
        _led_set(0)
        time.sleep_ms(120)


def _led_toggle(_t):
    if _led is not None:
        try:
            _led.toggle()
        except Exception:
            pass


def led_blink_start():
    global _led_timer
    if _led is None:
        return
    try:
        _led_timer = machine.Timer(-1)
        _led_timer.init(period=LED_UPDATE_MS, mode=machine.Timer.PERIODIC,
                        callback=_led_toggle)
    except Exception:
        _led_timer = None


def led_blink_stop():
    global _led_timer
    if _led_timer is not None:
        try:
            _led_timer.deinit()
        except Exception:
            pass
        _led_timer = None
    _led_set(0)


# --- Home Assistant ----------------------------------------------------------

def read_home():
    """Indoor temperature from Home Assistant, or None (no token / HA down)."""
    token = getattr(secrets, "HA_TOKEN", "")
    if not token:
        state["home"] = "нет токена (HA_TOKEN в secrets.py)"
        return None
    try:
        v = pico_ha.get_temperature(getattr(secrets, "HA_HOSTS", ("homeassistant.local",)),
                                    HA_ENTITY, token, getattr(secrets, "HA_PORT", 80))
        state["home"] = "—" if v is None else "%.1f°" % v
        return v
    except Exception as e:
        state["home"] = "ошибка: %r" % (e,)
        print("HA: %r" % (e,))
        return None


# --- one update ---------------------------------------------------------------

def update():
    """Fetch, render and send one card. Raises on failure."""
    global _busy
    _busy = True
    led_blink_start()
    try:
        state["status"] = "обновляю…"
        if not wlan().isconnected():
            connect()
        gc.collect()
        card = parse_j1(pico_json.fetch_j1("wttr.in", QUERY))
        sync_clock()                       # uses the answer's Date if NTP fails
        card["city"] = CITY
        card["time"] = warsaw_hhmm()
        card["home"] = read_home()
        gc.collect()
        c = render_card(card)
        state["status"] = "отправляю на экран…"
        pico_swd.send_card(c.black, c.red)
        del c
        gc.collect()
        state["last_ok"] = card["time"] or "?"
        state["last_error"] = ""
        state["summary"] = "%d°, %s" % (card["temp"], card["cond"])
        state["status"] = "готово"
        print("send_card: ok", card["time"])
    finally:
        led_blink_stop()
        _busy = False


async def updater():
    booted = False                     # first update after power-up done?
    await asyncio.sleep(BOOT_DELAY)
    while True:
        try:
            update()
            if not booted:
                print("boot update: ok")
            booted = True
            wait = seconds_to_next_slot()
        except Exception as e:
            state["last_error"] = "%s: %r" % (warsaw_hhmm() or "?", e)
            state["status"] = "ошибка" if booted else "ошибка, повтор (старт)"
            print("ERROR: %r" % (e,))
            wait = RETRY if booted else BOOT_RETRY
        state["next"] = warsaw_hhmm(time.time() + wait) if clock_ok() else ""
        _force.clear()
        try:
            await asyncio.wait_for(_force.wait(), wait)
            # Button pressed: let the web server answer the redirect and the
            # "обновляю…" page first; the update itself blocks for a while.
            await asyncio.sleep_ms(1500)
        except asyncio.TimeoutError:
            pass


# --- web --------------------------------------------------------------------

_PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
%s<title>Погода на ценнике</title>
<style>body{font-family:sans-serif;max-width:420px;margin:24px auto;padding:0 16px}
td{padding:4px 12px 4px 0}.e{color:#c62828}
button{font-size:20px;padding:14px 28px;margin-top:16px;background:#c62828;color:#fff;
border:0;border-radius:10px;cursor:pointer;box-shadow:0 3px 0 #8e1b1b;
transition:background .15s,transform .05s,box-shadow .05s;-webkit-tap-highlight-color:transparent}
button:hover{background:#b71c1c}
button:active{transform:translateY(3px);box-shadow:0 0 0 #8e1b1b}
button:focus-visible{outline:3px solid #1565c0;outline-offset:3px}
button:disabled{background:#9e9e9e;box-shadow:0 3px 0 #757575;cursor:wait}</style>
</head><body><h2>%s</h2><table>
<tr><td>Статус</td><td>%s</td></tr>
<tr><td>Сейчас на экране</td><td>%s</td></tr>
<tr><td>Последнее обновление</td><td>%s</td></tr>
<tr><td>Следующее</td><td>%s</td></tr>
<tr><td>Часы</td><td>%s (%s)</td></tr>
<tr><td>Дома (HA)</td><td>%s</td></tr>
%s</table>
<form method="post" action="/update" onsubmit="var b=this.querySelector('button');b.disabled=true;b.textContent='Обновляю…'">
<button type="submit" %s>%s</button></form>
<p><small>Экран обновляется около 40 секунд.</small></p></body></html>"""


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def page():
    busy = _busy or _force.is_set()
    err = ('<tr><td>Ошибка</td><td class="e">%s</td></tr>' % _esc(state["last_error"])
           if state["last_error"] else "")
    return _PAGE % (
        '<meta http-equiv="refresh" content="5">' if busy else "",
        _esc(CITY),
        _esc("обновляю…" if busy and state["status"] == "готово" else state["status"]),
        _esc(state["summary"] or "—"),
        _esc(state["last_ok"] or "—"),
        _esc(state["next"] or "—"),
        _esc(warsaw_hhmm() or "не установлены"), _esc(state["clock"]),
        _esc(state["home"] or "—"),
        err,
        "disabled" if busy else "",
        "Обновляю…" if busy else "Обновить")


async def handle(reader, writer):
    try:
        line = await reader.readline()
        while True:
            h = await reader.readline()
            if not h or h == b"\r\n":
                break
        parts = line.split()
        path = parts[1] if len(parts) > 1 else b"/"
        if path == b"/update":
            _force.set()
            writer.write(b"HTTP/1.0 303 See Other\r\nLocation: /\r\n\r\n")
        elif path == b"/":
            body = page().encode()
            writer.write(b"HTTP/1.0 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
                         b"Cache-Control: no-store\r\nContent-Length: %d\r\n\r\n" % len(body))
            writer.write(body)
        else:
            writer.write(b"HTTP/1.0 404 Not Found\r\n\r\n")
        await writer.drain()
    except Exception as e:
        print("web: %r" % (e,))
    finally:
        writer.close()
        await writer.wait_closed()


async def run():
    await asyncio.start_server(handle, "0.0.0.0", 80)
    print("Web: http://%s/  (http://%s.local/)" % (state["ip"] or "?", HOSTNAME))
    await updater()


def main():
    print("Pico Weather Gateway: boot")
    led_boot()                         # power-up sign: a few quick blinks
    # Wi-Fi may still be coming up when power is applied to everything at
    # once. A failure here must not stop the program: update() connects again
    # and the boot update is retried every BOOT_RETRY seconds.
    try:
        connect()
        print("WiFi: connected, IP " + state["ip"])
    except Exception as e:
        state["last_error"] = "Wi-Fi: %r" % (e,)
        print("WiFi: %r (will retry)" % (e,))
    asyncio.run(run())


main()
