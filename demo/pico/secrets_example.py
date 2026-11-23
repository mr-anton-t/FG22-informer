# Template for secrets.py. Copy it to secrets.py next to this file and
# fill it in. secrets.py is in .gitignore and is not committed.

SSID = "your-ssid"
PASSWORD = "your-password"

# Home Assistant: tried in order (mDNS name, then its IP).
HA_HOSTS = ("homeassistant.local", "192.168.1.2")
HA_PORT = 80
# Long-lived access token (HA -> profile -> Security). Empty = no home
# temperature on the card.
HA_TOKEN = ""
