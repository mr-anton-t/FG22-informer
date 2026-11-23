# pico_json.py — streaming fetch of the wttr.in j1 JSON for MicroPython.
#
# The j1 answer is tens of KB; reading it whole and json.loads() runs the
# Pico W out of heap. Here the body is parsed as it arrives (1 KB recv
# chunks) and only the dozen fields the card needs are kept. The result has
# the same shape as the j1 dict, so pico_card.parse_j1() reads it unchanged.
#
# Runs on CPython too (for tests): only socket and bytes are used.

import socket


class _Stream:
    def __init__(self, sock):
        self.sock = sock
        self.buf = b""
        self.i = 0

    def get(self):
        if self.i >= len(self.buf):
            self.buf = self.sock.recv(1024)
            self.i = 0
            if not self.buf:
                raise ValueError("JSON ended early")
        b = self.buf[self.i]
        self.i += 1
        return b

    def back(self):
        # Only right after get(): i >= 1 then.
        self.i -= 1

    def ws(self):
        b = self.get()
        while b in (32, 9, 10, 13):
            b = self.get()
        return b

    def string(self, keep):
        """Read a JSON string body (the opening quote is already read)."""
        out = bytearray() if keep else None
        while True:
            b = self.get()
            if b == 34:                     # "
                return out
            if b == 92:                     # backslash
                b = self.get()
                if b == 117:                # \uXXXX
                    h = bytearray()
                    for _ in range(4):
                        h.append(self.get())
                    if keep:
                        out.extend(chr(int(bytes(h), 16)).encode())
                    continue
                b = {110: 10, 116: 9, 114: 13, 98: 8, 102: 12}.get(b, b)
            if keep:
                out.append(b)


def _wanted(p):
    """Paths of the j1 fields that pico_card.parse_j1 uses."""
    n = len(p)
    if n == 3 and p[0] == "current_condition" and p[1] == 0:
        return p[2] in ("temp_C", "weatherCode", "humidity", "FeelsLikeC", "windspeedKmph")
    if n == 5 and p[0] == "nearest_area":
        return p[1] == 0 and p[2] == "areaName" and p[3] == 0 and p[4] == "value"
    if n >= 3 and p[0] == "weather" and p[1] < 3:
        if n == 3:
            return p[2] in ("date", "maxtempC", "mintempC")
        if n == 5 and p[2] == "hourly":
            if p[4] == "weatherCode":
                return p[3] == 4
            # Today's precipitation, every 3-hour slot.
            return p[1] == 0 and p[4] in ("chanceofrain", "chanceofsnow", "precipMM")
    return False


def _value(st, path, out):
    b = st.ws()
    if b == 123:                            # {
        b = st.ws()
        if b == 125:
            return
        while True:
            if b != 34:
                raise ValueError("bad JSON: object key expected")
            key = bytes(st.string(True)).decode()
            if st.ws() != 58:               # :
                raise ValueError("bad JSON: ':' expected")
            path.append(key)
            _value(st, path, out)
            path.pop()
            b = st.ws()
            if b == 125:
                return
            if b != 44:
                raise ValueError("bad JSON: ',' or '}' expected")
            b = st.ws()
    elif b == 91:                           # [
        b = st.ws()
        if b == 93:
            return
        st.back()
        i = 0
        while True:
            path.append(i)
            _value(st, path, out)
            path.pop()
            i += 1
            b = st.ws()
            if b == 93:
                return
            if b != 44:
                raise ValueError("bad JSON: ',' or ']' expected")
    elif b == 34:                           # string
        keep = _wanted(path)
        s = st.string(keep)
        if keep:
            out[tuple(path)] = bytes(s).decode()
    else:                                   # number, true, false, null
        tok = bytearray([b])
        while True:
            b = st.get()
            if b in (44, 125, 93, 32, 9, 10, 13):
                st.back()
                break
            tok.append(b)
        if _wanted(path):
            out[tuple(path)] = bytes(tok).decode()


def _shape(out):
    """Build a minimal j1-shaped dict from the collected fields."""
    def need(*k):
        v = out.get(k)
        if v is None:
            raise ValueError("j1 field missing: " + "/".join(str(x) for x in k))
        return v

    weather = []
    for i in range(3):
        if ("weather", i, "date") not in out:
            break
        hourly = []
        for k in range(8):
            h = {}
            for f in ("weatherCode", "chanceofrain", "chanceofsnow", "precipMM"):
                v = out.get(("weather", i, "hourly", k, f))
                if v is not None:
                    h[f] = v
            hourly.append(h)
        need("weather", i, "hourly", 4, "weatherCode")
        weather.append({
            "date": need("weather", i, "date"),
            "maxtempC": need("weather", i, "maxtempC"),
            "mintempC": need("weather", i, "mintempC"),
            "hourly": hourly,
        })
    if not weather:
        raise ValueError("j1 has no forecast days")
    return {
        "current_condition": [{
            "temp_C": need("current_condition", 0, "temp_C"),
            "weatherCode": need("current_condition", 0, "weatherCode"),
            "humidity": need("current_condition", 0, "humidity"),
            "FeelsLikeC": need("current_condition", 0, "FeelsLikeC"),
            "windspeedKmph": need("current_condition", 0, "windspeedKmph"),
        }],
        "nearest_area": [{"areaName": [{"value": need("nearest_area", 0, "areaName", 0, "value")}]}],
        "weather": weather,
    }


# UTC time from the last answer's "Date:" header, (y, mon, d, h, m, s) or None.
# Used to set the clock when NTP does not answer.
http_date = None

_MON = (b"Jan", b"Feb", b"Mar", b"Apr", b"May", b"Jun",
        b"Jul", b"Aug", b"Sep", b"Oct", b"Nov", b"Dec")


def _parse_http_date(v):
    """b"Mon, 23 Nov 2026 19:05:12 GMT" -> (2026, 11, 23, 19, 5, 12)."""
    try:
        p = v.split()
        hh, mm, ss = (int(x) for x in p[4].split(b":"))
        return (int(p[3]), _MON.index(p[2]) + 1, int(p[1]), hh, mm, ss)
    except Exception:
        return None


def parse_stream(sock):
    """Read an HTTP/1.0 response from `sock` and return the minimal j1 dict."""
    st = _Stream(sock)
    hdr = bytearray()
    while hdr[-4:] != b"\r\n\r\n":
        hdr.append(st.get())
        if len(hdr) > 8192:
            raise ValueError("HTTP header too long")
    lines = bytes(hdr).split(b"\r\n")
    status = lines[0]
    if b" 200" not in status:
        raise ValueError("HTTP " + status.decode())
    global http_date
    http_date = None
    for ln in lines:
        if ln[:5].lower() == b"date:":
            http_date = _parse_http_date(ln[5:].strip())
    out = {}
    _value(st, [], out)
    return _shape(out)


def fetch_j1(host, path, timeout=30):
    """GET http://host/path and return the minimal j1 dict."""
    addr = socket.getaddrinfo(host, 80)[0][-1]
    s = socket.socket()
    try:
        s.settimeout(timeout)
        s.connect(addr)
        req = (b"GET " + path + b" HTTP/1.0\r\nHost: " + host.encode()
               + b"\r\nUser-Agent: curl/8\r\nAccept: application/json\r\n\r\n")
        while req:
            n = s.send(req)
            if n <= 0:
                raise OSError("send failed")
            req = req[n:]
        return parse_stream(s)
    finally:
        s.close()
