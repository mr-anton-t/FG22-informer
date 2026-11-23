# pico_ha.py — read one sensor from Home Assistant's REST API.
#
#   GET /api/states/<entity_id>   with  Authorization: Bearer <token>
#
# The token is a long-lived access token (HA: profile -> Security ->
# Long-lived access tokens), kept in secrets.py. Runs on CPython too.

import json
import socket


def get_state(hosts, entity, token, port=80, timeout=5):
    """Return (state, unit) of `entity`. `hosts` are tried in order (e.g. the
    mDNS name, then the IP). Raises on failure."""
    req = ("GET /api/states/%s HTTP/1.0\r\nHost: %%s\r\nAuthorization: Bearer %s\r\n"
           "Accept: application/json\r\n\r\n" % (entity, token))
    last = None
    for host in hosts:
        try:
            addr = socket.getaddrinfo(host, port)[0][-1]
            s = socket.socket()
            try:
                s.settimeout(timeout)
                s.connect(addr)
                data = (req % host).encode()
                while data:
                    n = s.send(data)
                    data = data[n:]
                resp = b""
                while len(resp) < 8192:
                    chunk = s.recv(1024)
                    if not chunk:
                        break
                    resp += chunk
            finally:
                s.close()
            head, _, body = resp.partition(b"\r\n\r\n")
            status = head.split(b"\r\n", 1)[0]
            if b" 200" not in status:
                raise OSError("HA %s: %s" % (host, status.decode()))
            j = json.loads(body)
            return j["state"], j.get("attributes", {}).get("unit_of_measurement", "")
        except Exception as e:
            last = e
    raise last or OSError("no Home Assistant host")


def get_temperature(hosts, entity, token, port=80):
    """Sensor value as float, or None when HA says unknown/unavailable."""
    state, _unit = get_state(hosts, entity, token, port)
    try:
        return float(state)
    except ValueError:
        return None
