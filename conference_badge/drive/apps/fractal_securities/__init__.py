# Fractal Securities: portfolio performance vs the S&P 500 (VOO), read live
# from the table on fractal-securities.com.
#
#   B           refresh (join WiFi, download the page, read the table)
#   C           back to the menu
#   HOME        back to the menu
#
# Opening the app shows the last table it saved, then refreshes once if WiFi
# is set up (Settings app, or WIFI_SSID / WIFI_PASSWORD in secrets.py). WiFi is
# switched off again as soon as the page is in. Like Conf Badge, it only draws
# when something changes; brightness and idle CPU speed follow the power mode.
#
# The page is downloaded with the firmware's own non-blocking `fetch` module
# (what Pimoroni uses for HTTPS on this badge), one small step at a time, and
# each stage is shown on screen and printed over USB, so a stall is visible.

import gc
import sys
import time

import fractal_table

if "/system/lib" not in sys.path:
    sys.path.append("/system/lib")
import power

APP = "fractal_securities"
URL = "https://fractal-securities.com/"

WIFI_TIMEOUT_MS = 20000
STALL_TIMEOUT_S = 15             # give up if no data moves for this long...
TOTAL_TIMEOUT_MS = 60000         # ...or if the whole download takes longer than this
MAX_BYTES = 1024 * 1024          # largest page it will hold in memory
POLL_MS = 20

BG = color.rgb(14, 16, 20)
STRIPE = color.rgb(22, 25, 31)
RULE = color.rgb(44, 48, 56)
WHITE = color.rgb(240, 242, 245)
GREY = color.rgb(138, 145, 158)
DIM = color.rgb(90, 96, 108)
UP = color.rgb(60, 220, 120)
DOWN = color.rgb(255, 92, 80)

BODY = font.compass        # 13x16 cell, digits on rows 4-14
SMALL = font.match         # 10x12 cell, ink on rows 3-10

badge.mode(HIRES)
badge.default_clear = None
try:
    badge.caselights(0)
except Exception:
    pass
MODE = power.apply()             # panel refresh + backlight for the saved power mode
IDLE_HZ = MODE["idle_hz"]
cpu = power.cpu

W, H = screen.width, screen.height

# column layout
X_PERIOD = 10
X_PORT = 206               # right edges of the number columns
X_VOO = 308
ROW_Y = 54                 # first row; rows share the space down to the footer
ROW_H_MAX = 22

try:
    import secrets
    SSID = getattr(secrets, "WIFI_SSID", "") or ""
    PSK = getattr(secrets, "WIFI_PASSWORD", "") or ""
except Exception:
    SSID = PSK = ""

state = {"as_of": None, "rows": [], "updated": None}
try:
    State.load(APP, state)
except Exception:
    pass

status = ""
dirty = True


# ------------------------------------------------------------------ drawing

def text_right(s, right, y):
    w, _ = screen.measure_text(s)
    screen.text(s, right - int(w), y)


def value_pen(v):
    if v.startswith("-"):
        return DOWN
    if v[:1] == "+" or v[:1].isdigit():
        return UP
    return GREY


def draw():
    screen.pen = BG
    screen.clear()

    # title and as-of date
    screen.font = BODY
    screen.pen = WHITE
    screen.text("Fractal Securities", X_PERIOD, 6)
    if state["as_of"]:
        screen.font = SMALL
        screen.pen = GREY
        text_right("as of " + state["as_of"], X_VOO, 9)

    # column headings
    screen.font = SMALL
    screen.pen = GREY
    screen.text("PERIOD", X_PERIOD, 35)
    text_right("PORTFOLIO", X_PORT, 35)
    text_right("S&P 500 (VOO)", X_VOO, 35)
    screen.pen = RULE
    screen.rectangle(X_PERIOD, 49, X_VOO - X_PERIOD, 1)

    # rows
    screen.font = BODY
    rows = state["rows"][:9]
    if not rows:
        screen.pen = GREY
        screen.text("No data yet", X_PERIOD, ROW_Y + 30)
    row_h = min(ROW_H_MAX, (H - 26 - ROW_Y) // max(1, len(rows)))
    for i, (period, port, voo) in enumerate(rows):
        y = ROW_Y + i * row_h
        if i % 2 == 0:
            screen.pen = STRIPE
            screen.rectangle(X_PERIOD - 6, y, X_VOO - X_PERIOD + 10, row_h)
        ty = y + (row_h - 11) // 2 - 4          # centre the 11px-tall ink in the row
        screen.pen = WHITE
        screen.text(period, X_PERIOD, ty)
        screen.pen = value_pen(port)
        text_right(port, X_PORT, ty)
        screen.pen = value_pen(voo)
        text_right(voo, X_VOO, ty)

    # footer: status on the left, keys on the right
    screen.font = SMALL
    screen.pen = RULE
    screen.rectangle(X_PERIOD, H - 24, X_VOO - X_PERIOD, 1)
    screen.pen = GREY
    line = status
    if not line and state["updated"]:
        line = "Updated " + state["updated"]
    screen.text(line, X_PERIOD, H - 19)
    hint = "B refresh  C menu"
    lw, _ = screen.measure_text(line)
    hw, _ = screen.measure_text(hint)
    if X_PERIOD + lw + 12 + hw <= X_VOO:     # only if it fits next to the status
        screen.pen = DIM
        text_right(hint, X_VOO, H - 19)


def show(msg):
    """Set the status line and put it on screen right away (before slow work)."""
    global status, dirty
    status = msg
    draw()
    display.update()
    dirty = False


# ------------------------------------------------------------------ fetching

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def now_text():
    t = time.localtime()
    if t[0] < 2025:                  # clock not set (it's set over WiFi from the menu)
        return "just now"
    return "{} {} {:02d}:{:02d}".format(MONTHS[t[1] - 1], t[2], t[3], t[4])


def reason(e):
    """A few words on why an update failed."""
    if e.args and isinstance(e.args[0], str):
        return e.args[0][:30]                  # our own messages
    code = e.args[0] if e.args else None
    if code in (-2, -202, -3):
        return "can't reach the site"           # DNS / no route
    if code in (110, 116, -110):
        return "timed out"
    if isinstance(e, OSError):
        return "network error {}".format(code)
    return e.__class__.__name__


def wifi_up():
    import network
    power.radio(True)                    # keeps the CPU at full speed while WiFi is on
    wlan = network.WLAN(network.STA_IF)
    try:
        wlan.active(True)
        if not wlan.isconnected():
            wlan.connect(SSID, PSK)
            start = time.ticks_ms()
            while not wlan.isconnected():
                if wlan.status() < 0:
                    raise OSError("WiFi refused, check secrets.py")
                if time.ticks_diff(time.ticks_ms(), start) > WIFI_TIMEOUT_MS:
                    raise OSError("WiFi timed out")
                time.sleep_ms(100)
    except Exception:
        wifi_down(wlan)                  # never leave the radio on behind a failure
        raise
    return wlan


def wifi_down(wlan):
    if wlan is not None:
        try:
            wlan.disconnect()
            wlan.active(False)
        except Exception:
            pass
    power.radio(False)


STAGES = {"dns": "Looking up site", "connect": "Connecting", "send": "Secure handshake",
          "headers": "Waiting for reply", "body": "Downloading"}


def stage(label):
    """Show and log a step, so if anything stalls you can see where."""
    print("fractal_securities:", label)
    show(label + "...")


def split_url(url):
    tls = url.startswith("https://")
    rest = url.split("://", 1)[1]
    host_port, _, path = rest.partition("/")
    host, _, port = host_port.partition(":")
    return tls, host, int(port) if port else (443 if tls else 80), "/" + path


def download(url):
    """The page at url as text, following up to two redirects."""
    import fetch
    for _ in range(3):
        tls, host, port, path = split_url(url)
        stage(STAGES["dns"])
        f = fetch.AsyncFetch(host, port, use_tls=tls, max_bytes=MAX_BYTES, timeout=STALL_TIMEOUT_S)
        f.on_error(lambda _f: True)          # non-200: handled below instead of raising
        f.fetch(path)
        start = time.ticks_ms()
        shown, shown_at = STAGES["dns"], time.ticks_ms()
        try:
            while True:
                result = f.update()          # one short, non-blocking step
                if result == fetch.AsyncFetch.DONE:
                    return bytes(f.body).decode("utf-8")
                if result == fetch.AsyncFetch.ERROR:
                    break
                now = time.ticks_ms()
                if time.ticks_diff(now, start) > TOTAL_TIMEOUT_MS:
                    raise OSError("download timed out")
                phase = getattr(f, "_phase", None)
                label = STAGES.get(phase, "Downloading")
                if phase == "body":
                    label += " {} KB".format(getattr(f, "_buffer_len", 0) // 1024)
                if label != shown and time.ticks_diff(now, shown_at) > 250:
                    stage(label)
                    shown, shown_at = label, now
                time.sleep_ms(2)
        finally:
            f.reset()                        # close the socket
        code = f.http_status
        where = None
        for k, v in (f.http_response_headers or {}).items():
            if k.lower() == "location":
                where = v
        if code in (301, 302, 303, 307, 308) and where:
            url = where if "://" in where else ("https://" if tls else "http://") + host + where
            print("fractal_securities: redirected to", url)
            continue
        raise OSError("HTTP {}".format(code))
    raise OSError("too many redirects")


def refresh():
    global status, dirty
    if not SSID:
        status = "No WiFi set (Settings app)"
        dirty = True
        return
    cpu(None)
    wlan = None
    try:
        stage("Connecting to WiFi")
        wlan = wifi_up()
        html = download(URL)
        stage("Reading table")
        data = fractal_table.parse(html)
        del html
        gc.collect()
        if not data["rows"]:
            raise ValueError("table not found on page")
        state["as_of"] = data["as_of"]
        state["rows"] = data["rows"]
        state["updated"] = now_text()
        try:
            State.save(APP, state)
        except Exception:
            pass
        status = ""
    except Exception as e:
        status = "Update failed: " + reason(e)
    finally:
        wifi_down(wlan)
        gc.collect()
        dirty = True


# ------------------------------------------------------------------ main loop

def main():
    global dirty
    cpu(None)
    draw()
    display.update()                 # saved table first, so there's something to read
    dirty = False
    refresh()
    cpu(IDLE_HZ)
    while True:
        badge.poll()
        if badge.pressed(BUTTON_C):
            return
        if badge.pressed(BUTTON_B):
            refresh()
        if dirty:
            cpu(None)
            draw()
            display.update()
            dirty = False
            cpu(IDLE_HZ)
        time.sleep_ms(POLL_MS)


main()
