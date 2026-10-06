# Settings: WiFi network and power mode.
#
#   UP / DOWN   move          B   choose          A   back          C   menu
#   On the keyboard: A / C move left / right, UP / DOWN change row, B types.
#
# WiFi: scan for networks (or type a name), enter the password on the
# on-screen keyboard, and the badge tests the connection before saving it.
# It is saved to /secrets.py on the badge's own writable storage, which the
# firmware reads in place of secrets.py on the drive, and which reflashing
# doesn't erase. "Use secrets.py from the drive" removes it again.
#
# Power mode: Performance / Balanced / Power saver (see /system/lib/power.py).
# The new brightness shows straight away; everything else applies from the
# next screen you open.

import os
import sys
import time

if "/system/lib" not in sys.path:
    sys.path.append("/system/lib")
import power

SECRETS = "/secrets.py"
WIFI_TIMEOUT_MS = 20000
POLL_MS = 20
REPEAT_AFTER_MS = 450            # hold a direction this long and it repeats...
REPEAT_EVERY_MS = 110            # ...this often

badge.mode(HIRES)
badge.default_clear = None
screen.antialias = image.X2
try:
    badge.caselights(0)
except Exception:
    pass

W, H = screen.width, screen.height
MODE = power.apply()
cpu = power.cpu

BLACK = color.black
GREEN = color.rgb(40, 255, 110)
GREEN_DIM = color.rgb(0, 150, 60)
FAINT = color.rgb(0, 90, 38)
SEL = color.rgb(0, 70, 30)
KEY = color.rgb(16, 22, 18)
WHITE = color.rgb(230, 240, 232)
GREY = color.rgb(110, 125, 115)
RED = color.rgb(255, 90, 70)

BODY = font.compass          # 13x16 cell, ink on rows 4-14
SMALL = font.match           # 10x12 cell, ink on rows 3-10


# ------------------------------------------------------------------ secrets

def current_secrets():
    v = {"WIFI_SSID": "", "WIFI_PASSWORD": "", "REGION": "us", "TIMEZONE": 0}
    try:
        import secrets
        for k in v:
            x = getattr(secrets, k, None)
            if x is not None:
                v[k] = x
    except Exception:
        pass
    return v


def has_override():
    try:
        os.stat(SECRETS)
        return True
    except OSError:
        return False


def save_wifi(ssid, psk):
    keep = current_secrets()
    text = ("# Written by the badge's Settings app. The firmware reads this file instead\n"
            "# of secrets.py on the drive. Settings > WiFi > 'Use secrets.py from the\n"
            "# drive' deletes it.\n"
            "WIFI_SSID = " + repr(ssid) + "\n"
            "WIFI_PASSWORD = " + repr(psk) + "\n"
            "REGION = " + repr(keep["REGION"]) + "\n"
            "TIMEZONE = " + repr(keep["TIMEZONE"]) + "\n")
    with open(SECRETS, "w") as f:
        f.write(text)
    wifi["ssid"], wifi["psk"], wifi["override"] = ssid, psk, True


def drop_override():
    try:
        os.remove(SECRETS)
    except OSError:
        pass
    # what the drive's secrets.py says, now that ours is gone
    ssid = psk = ""
    try:
        ns = {}
        exec(open("/system/secrets.py").read(), ns)
        ssid, psk = ns.get("WIFI_SSID", "") or "", ns.get("WIFI_PASSWORD", "") or ""
    except Exception:
        pass
    wifi["ssid"], wifi["psk"], wifi["override"] = ssid, psk, False


_s = current_secrets()
wifi = {"ssid": _s["WIFI_SSID"] or "", "psk": _s["WIFI_PASSWORD"] or "", "override": has_override()}
del _s


# ------------------------------------------------------------------ radio

def radio():
    import network
    power.radio(True)                    # keeps the CPU at full speed while WiFi is on
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    return network, wlan


def radio_off(wlan):
    try:
        wlan.disconnect()
    except Exception:
        pass
    try:
        wlan.active(False)
    except Exception:
        pass
    power.radio(False)


def scan():
    """-> [(ssid, rssi, secured)], strongest first, one entry per name."""
    network, wlan = radio()
    try:
        found = wlan.scan()
    finally:
        radio_off(wlan)
    best = {}
    for entry in found:
        try:
            name = entry[0].decode()
        except Exception:
            continue
        if not name:
            continue
        rssi, secured = entry[3], entry[4] != 0
        if name not in best or rssi > best[name][0]:
            best[name] = (rssi, secured)
    nets = [(n, best[n][0], best[n][1]) for n in best]
    nets.sort(key=lambda n: -n[1])
    return nets


def test_wifi(ssid, psk):
    """-> (ok, message). Leaves the radio off."""
    network, wlan = radio()
    try:
        try:
            wlan.disconnect()
        except Exception:
            pass
        wlan.connect(ssid, psk)
        start = time.ticks_ms()
        wrong = getattr(network, "STAT_WRONG_PASSWORD", -3)
        missing = getattr(network, "STAT_NO_AP_FOUND", -2)
        while not wlan.isconnected():
            st = wlan.status()
            if st == wrong:
                return False, "Wrong password"
            if st == missing:
                return False, "Network not found"
            if st < 0:
                return False, "Connection failed"
            if time.ticks_diff(time.ticks_ms(), start) > WIFI_TIMEOUT_MS:
                return False, "Timed out"
            time.sleep_ms(100)
        return True, "Connected"
    finally:
        radio_off(wlan)


# ------------------------------------------------------------------ drawing helpers

def text_right(s, right, y):
    w, _ = screen.measure_text(s)
    screen.text(s, right - int(w), y)


def fit(s, width):
    """s, shortened with '..' if it's wider than width in the current font."""
    if screen.measure_text(s)[0] <= width:
        return s
    while s and screen.measure_text(s + "..")[0] > width:
        s = s[:-1]
    return s + ".."


def header(title, right=None):
    screen.pen = BLACK
    screen.clear()
    screen.font = BODY
    screen.pen = GREEN
    screen.text(title, 10, 6)
    if right:
        screen.font = SMALL
        screen.pen = GREY
        text_right(right, 310, 9)
    screen.pen = FAINT
    screen.rectangle(10, 28, 300, 1)


def footer(hint, note=None):
    screen.font = SMALL
    screen.pen = FAINT
    screen.rectangle(10, H - 24, 300, 1)
    if note:
        screen.pen = GREY
        screen.text(fit(note, 300), 10, H - 19)
    else:
        screen.pen = GREY
        text_right(hint, 310, H - 19)


def menu_rows(items, sel, y0=36, row_h=30, show=6, first=0):
    """items: [(label, value, value_pen)]; draws a selectable list."""
    for k in range(first, min(len(items), first + show)):
        label, value, vpen = items[k]
        y = y0 + (k - first) * row_h
        if k == sel:
            screen.pen = SEL
            screen.shape(shape.rounded_rectangle(6, y, 308, row_h - 4, 5))
            screen.pen = GREEN
            screen.shape(shape.rounded_rectangle(6, y, 308, row_h - 4, 5).stroke(1))
        screen.font = BODY
        screen.pen = GREEN if k == sel else WHITE
        screen.text(("> " if k == sel else "  ") + label, 10, y + (row_h - 4 - 11) // 2 - 4)
        if value:
            screen.font = SMALL
            screen.pen = vpen or GREY
            text_right(fit(value, 150), 306, y + (row_h - 4 - 8) // 2 - 3)


# ------------------------------------------------------------------ screens

class Screen:
    def press(self, b):          # b in "A B C UP DOWN"; return a new Screen, None, or "exit"
        return None

    def draw(self):
        pass


class Main(Screen):
    def __init__(self):
        self.sel = 0

    def items(self):
        ssid = wifi["ssid"] or "Not set"
        return [("WiFi", ssid, GREEN_DIM if wifi["ssid"] else GREY),
                ("Power mode", power.NAMES[power.mode()], GREEN_DIM)]

    def press(self, b):
        if b == "UP":
            self.sel = max(0, self.sel - 1)
        elif b == "DOWN":
            self.sel = min(1, self.sel + 1)
        elif b == "B":
            return WifiMenu() if self.sel == 0 else PowerMenu()
        elif b == "C":
            return "exit"

    def draw(self):
        header("Settings")
        menu_rows(self.items(), self.sel)
        screen.font = SMALL
        screen.pen = GREY
        if self.sel == 0:
            where = "saved on the badge" if wifi["override"] else "from secrets.py on the drive"
            screen.text(("Network " + where) if wifi["ssid"] else "No network set: the menu keeps WiFi off", 10, 112)
        else:
            screen.text(power.profile()["about"], 10, 112)
        footer("UP/DOWN  B open  C menu")


class PowerMenu(Screen):
    def __init__(self):
        self.sel = power.MODES.index(power.mode())

    def press(self, b):
        if b == "UP":
            self.sel = max(0, self.sel - 1)
        elif b == "DOWN":
            self.sel = min(len(power.MODES) - 1, self.sel + 1)
        elif b == "B":
            name = power.MODES[self.sel]
            power.save(name)
            power.apply(name)                     # brightness changes right away
        elif b == "A":
            return Main()
        elif b == "C":
            return "exit"

    def draw(self):
        header("Power mode")
        current = power.mode()
        items = [(power.NAMES[m], "current" if m == current else "", GREEN_DIM) for m in power.MODES]
        menu_rows(items, self.sel)
        screen.font = SMALL
        screen.pen = GREY
        screen.text(power.PROFILES[power.MODES[self.sel]]["about"], 10, 132)
        screen.text("Rain speed and CPU apply from the next screen.", 10, 150)
        footer("B use  A back  C menu")


class WifiMenu(Screen):
    def __init__(self, note=None):
        self.sel = 0
        self.note = note

    def options(self):
        opts = [("Scan for networks", "scan"), ("Type a network name", "type")]
        if wifi["ssid"]:
            opts.append(("Forget network", "forget"))
        if wifi["override"]:
            opts.append(("Use secrets.py from drive", "drive"))
        return opts

    def press(self, b):
        opts = self.options()
        self.sel = min(self.sel, len(opts) - 1)
        if b == "UP":
            self.sel = max(0, self.sel - 1)
        elif b == "DOWN":
            self.sel = min(len(opts) - 1, self.sel + 1)
        elif b == "A":
            return Main()
        elif b == "C":
            return "exit"
        elif b == "B":
            what = opts[self.sel][1]
            if what == "scan":
                busy("WiFi", "Scanning...")
                try:
                    return NetworkList(scan())
                except Exception as e:
                    return WifiMenu("Scan failed: " + str(e)[:30])
            if what == "type":
                return Keyboard("Network name", "", self.after_name)
            if what == "forget":
                save_wifi("", "")
                return WifiMenu("Forgotten: WiFi stays off")
            if what == "drive":
                drop_override()
                return WifiMenu("Now using secrets.py from the drive")

    @staticmethod
    def after_name(name):
        if not name:
            return WifiMenu()
        return Keyboard("Password for " + name, "", lambda pw: Connect(name, pw), secret=True)

    def draw(self):
        header("WiFi", fit(wifi["ssid"], 150) if wifi["ssid"] else "no network")
        menu_rows([(o[0], "", None) for o in self.options()], self.sel)
        footer("B choose  A back  C menu", self.note)


class NetworkList(Screen):
    SHOW = 5

    def __init__(self, nets):
        self.nets = nets
        self.sel = 0
        self.first = 0

    def press(self, b):
        n = len(self.nets)
        if b == "A":
            return WifiMenu()
        if b == "C":
            return "exit"
        if not n:
            return None
        if b == "UP":
            self.sel = max(0, self.sel - 1)
        elif b == "DOWN":
            self.sel = min(n - 1, self.sel + 1)
        elif b == "B":
            name, _, secured = self.nets[self.sel]
            if not secured:
                return Connect(name, "")
            return Keyboard("Password for " + name, "", lambda pw: Connect(name, pw), secret=True)
        if self.sel < self.first:
            self.first = self.sel
        if self.sel >= self.first + self.SHOW:
            self.first = self.sel - self.SHOW + 1

    def draw(self):
        header("Networks", "{} found".format(len(self.nets)))
        if not self.nets:
            screen.font = BODY
            screen.pen = GREY
            screen.text("No networks found", 10, 60)
            footer("A back  C menu")
            return
        items = []
        for name, rssi, secured in self.nets:
            items.append((fit(name, 200), ("locked " if secured else "open ") + bars(rssi), GREEN_DIM))
        menu_rows(items, self.sel, show=self.SHOW, first=self.first)
        footer("B choose  A back  C menu")


def bars(rssi):
    n = 4 if rssi > -60 else 3 if rssi > -70 else 2 if rssi > -80 else 1
    return "|" * n + "." * (4 - n)


class Connect(Screen):
    def __init__(self, ssid, psk):
        self.ssid, self.psk = ssid, psk
        busy("WiFi", "Connecting to " + ssid + "...")
        try:
            self.ok, self.msg = test_wifi(ssid, psk)
        except Exception as e:
            self.ok, self.msg = False, "Error: " + str(e)[:30]
        if self.ok:
            save_wifi(ssid, psk)
            self.options = [("Done", "done")]
        else:
            self.options = [("Edit password", "edit"), ("Save anyway", "save"), ("Cancel", "cancel")]
        self.sel = 0

    def press(self, b):
        if b == "UP":
            self.sel = max(0, self.sel - 1)
        elif b == "DOWN":
            self.sel = min(len(self.options) - 1, self.sel + 1)
        elif b == "A":
            return WifiMenu()
        elif b == "C":
            return "exit"
        elif b == "B":
            what = self.options[self.sel][1]
            if what == "done":
                return Main()
            if what == "edit":
                return Keyboard("Password for " + self.ssid, self.psk,
                                lambda pw: Connect(self.ssid, pw), secret=True)
            if what == "save":
                save_wifi(self.ssid, self.psk)
                return WifiMenu("Saved " + self.ssid + " (not tested)")
            return WifiMenu()

    def draw(self):
        header("WiFi", fit(self.ssid, 150))
        screen.font = BODY
        screen.pen = GREEN if self.ok else RED
        screen.text(("Connected - saved" if self.ok else self.msg), 10, 40)
        if self.ok:
            screen.font = SMALL
            screen.pen = GREY
            screen.text("The menu joins it from now on.", 10, 62)
        menu_rows([(o[0], "", None) for o in self.options], self.sel, y0=84)
        footer("B choose  A back  C menu")


class Keyboard(Screen):
    PAGES = {
        "abc": ("1234567890", "qwertyuiop", "asdfghjkl-", "zxcvbnm_.@"),
        "ABC": ("1234567890", "QWERTYUIOP", "ASDFGHJKL-", "ZXCVBNM_.@"),
        "#+=": ("1234567890", "!#$%&*()+=", "[]{}<>/\\|~", "'\"`^?:;,-_"),
    }
    KEYS = ("aA", "#+=", "space", "del", "OK", "back")
    KX, KY, KW, KH = 10, 64, 30, 28

    def __init__(self, title, text, done, secret=False):
        self.title, self.buf, self.done, self.secret = title, text, done, secret
        self.page = "abc"
        self.r, self.c = 1, 0

    def row_len(self, r):
        return len(self.KEYS) if r == 4 else 10

    def press(self, b):
        if b == "UP":
            self.r = (self.r - 1) % 5
        elif b == "DOWN":
            self.r = (self.r + 1) % 5
        elif b == "A":
            self.c = (self.c - 1) % self.row_len(self.r)
        elif b == "C":
            self.c = (self.c + 1) % self.row_len(self.r)
        elif b == "B":
            if self.r < 4:
                self.buf += self.PAGES[self.page][self.r][self.c]
                return None
            key = self.KEYS[self.c]
            if key == "aA":
                self.page = "ABC" if self.page == "abc" else "abc"
            elif key == "#+=":
                self.page = "abc" if self.page == "#+=" else "#+="
            elif key == "space":
                self.buf += " "
            elif key == "del":
                self.buf = self.buf[:-1]
            elif key == "OK":
                return self.done(self.buf)
            elif key == "back":
                return WifiMenu()
        self.c = min(self.c, self.row_len(self.r) - 1)

    def draw(self):
        header(fit(self.title, 300))
        # text field
        screen.pen = KEY
        screen.shape(shape.rounded_rectangle(8, 33, 304, 25, 4))
        screen.pen = FAINT
        screen.shape(shape.rounded_rectangle(8, 33, 304, 25, 4).stroke(1))
        screen.font = BODY
        screen.pen = WHITE
        shown = self.buf
        while shown and screen.measure_text(shown)[0] > 280:
            shown = shown[1:]                      # keep the end (where you type) in view
        screen.text(shown, 14, 35)
        cw, _ = screen.measure_text(shown)
        screen.pen = GREEN
        screen.rectangle(14 + int(cw) + 1, 39, 7, 13)
        # keys
        for r in range(5):
            y = self.KY + r * self.KH
            if r < 4:
                keys = self.PAGES[self.page][r]
                widths = [self.KW] * 10
            else:
                keys = self.KEYS
                widths = [45, 45, 60, 50, 50, 50]
            x = self.KX
            for c in range(len(keys)):
                w = widths[c]
                on = r == self.r and c == self.c
                screen.pen = GREEN if on else KEY
                screen.shape(shape.rounded_rectangle(x + 1, y + 1, w - 2, self.KH - 3, 4))
                screen.pen = BLACK if on else (WHITE if r < 4 else GREEN_DIM)
                label = keys[c]
                screen.font = BODY if r < 4 else SMALL
                lw, _ = screen.measure_text(label)
                ty = y + 4 if r < 4 else y + 7
                screen.text(label, x + (w - int(lw)) // 2, ty)
                x += w
        footer("A/C left/right  UP/DOWN rows  B type")


def busy(title, msg):
    """Put a 'working...' screen up before something slow."""
    cpu(None)
    header(title)
    screen.font = BODY
    screen.pen = GREEN_DIM
    screen.text(msg, 10, 60)
    display.update()


# ------------------------------------------------------------------ main loop

BUTTONS = (("A", BUTTON_A), ("B", BUTTON_B), ("C", BUTTON_C), ("UP", BUTTON_UP), ("DOWN", BUTTON_DOWN))
REPEATS = ("A", "C", "UP", "DOWN")


def main():
    current = Main()
    dirty = True
    held_since = {}
    next_repeat = {}
    while True:
        badge.poll()
        now = badge.ticks
        pressed = []
        for name, pin in BUTTONS:
            if badge.pressed(pin):
                pressed.append(name)
                held_since[name] = now
                next_repeat[name] = now + REPEAT_AFTER_MS
            elif name in REPEATS and name in held_since and badge.held(pin):
                if now >= next_repeat[name]:          # key repeat while held
                    pressed.append(name)
                    next_repeat[name] = now + REPEAT_EVERY_MS
            else:
                held_since.pop(name, None)
        for b in pressed:
            result = current.press(b)
            if result == "exit":
                return
            if result is not None:
                current = result
            dirty = True
        if dirty:
            cpu(None)
            current.draw()
            display.update()
            dirty = False
            cpu(MODE["idle_hz"])
        else:
            time.sleep_ms(POLL_MS)


main()
