# Conf Badge: a wearable name badge for the Tufty 2350.
#
# Full-screen pictures from this app's assets/ folder: your name card first,
# and a QR code that B flips to and back.
#
#   B           flip between the name card and the QR code
#   A           cycle screen brightness (starts at the power mode's level)
#   UP / DOWN   step through every picture in assets/ (if you add more)
#   C           back to the menu
#   HOME        back to the menu
#
# Every .png / .jpg in assets/ is a screen, in filename order (1_name.png,
# 2_qr.png, ...). The app opens on the first one; B jumps to the file with
# "qr" in its name and back to where you were. Images that aren't 320x240
# are scaled to fit and centred.
#
# Battery: the display keeps showing the last frame it was sent, so this app
# only sends one when the picture changes and otherwise just sleeps between
# button checks, instead of redrawing flat out like the standard app loop.
# The power mode (Settings app) sets the brightness, and the CPU speed it
# idles at between button checks; it boosts to full speed only while drawing.

import os
import sys
import time

if "/system/lib" not in sys.path:
    sys.path.append("/system/lib")
import power

APP = "conf_badge"
EXTS = ("png", "jpg", "jpeg")

BG = color.rgb(14, 16, 20)
GREY = color.rgb(138, 145, 158)

POLL_MS = 20                     # button check interval while the picture is still
BRIGHTNESS = (0.9, 0.7, 0.45, 0.25)   # A steps through these

badge.mode(HIRES)            # Tufty apps start in 160x120; use the full 320x240
badge.default_clear = None   # keep the frame between updates, redraw only on change
try:
    badge.caselights(0)      # rear LEDs off to save battery
except Exception:
    pass

W, H = screen.width, screen.height

MODE = power.apply()             # panel refresh + backlight for the saved power mode
IDLE_HZ = MODE["idle_hz"]
cpu = power.cpu


# ------------------------------------------------------------------ files

def assets_dir():
    candidates = []
    try:
        if __file__.endswith("__init__.py"):
            candidates.append(__file__.rsplit("/", 1)[0])
    except NameError:
        pass
    candidates += ["/system/apps/" + APP, "/apps/" + APP, "apps/" + APP]
    for d in candidates:
        if d and file_exists(d + "/assets"):
            return d + "/assets"
    return None


def list_images(folder):
    names = []
    for n in os.listdir(folder):
        if n.startswith("."):            # skip macOS "._" files on the FAT drive
            continue
        if n.rsplit(".", 1)[-1].lower() in EXTS:
            names.append(n)
    names.sort()
    return names


def image_size(path):
    """Read width/height from a PNG or JPEG header without decoding it."""
    with open(path, "rb") as f:
        head = f.read(24)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
        if head[:2] != b"\xff\xd8":
            return None
        f.seek(2)
        while True:
            b = f.read(1)
            while b and b != b"\xff":
                b = f.read(1)
            while b == b"\xff":
                b = f.read(1)
            if not b:
                return None
            m = b[0]
            if m == 0x01 or 0xD0 <= m <= 0xD8:      # markers with no length field
                continue
            seg = f.read(2)
            if len(seg) < 2:
                return None
            length = (seg[0] << 8) | seg[1]
            if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):   # start of frame
                d = f.read(5)
                return (d[3] << 8) | d[4], (d[1] << 8) | d[2]
            f.seek(length - 2, 1)


def load(path):
    size = image_size(path)
    if size is None or size == (W, H):
        return image.load(path)
    w, h = size
    s = min(W / w, H / h)                # fit inside the screen, keep aspect ratio
    return image.load(path, max(1, int(w * s)), max(1, int(h * s)))


# ------------------------------------------------------------------ state

folder = assets_dir()
names = list_images(folder) if folder else []
cache = {}

qr = None                                # index of the QR screen, if there is one
for i in range(len(names)):
    if "qr" in names[i].lower():
        qr = i
        break

idx = 0                                  # open on the first picture (the name card)
back = 0                                 # where B returns to from the QR code
dirty = True

# start at whichever brightness step is closest to the power mode's
level = 0
for i in range(len(BRIGHTNESS)):
    if abs(BRIGHTNESS[i] - MODE["backlight"]) < abs(BRIGHTNESS[level] - MODE["backlight"]):
        level = i


def set_brightness(i):
    global level
    level = i % len(BRIGHTNESS)
    try:
        display.backlight(BRIGHTNESS[level])
    except Exception:
        pass


def get(i):
    if i not in cache:
        try:
            cache[i] = load(folder + "/" + names[i])
        except Exception as e:
            cache[i] = str(e)            # remember the failure, show it on screen
    return cache[i]


def show(i):
    global idx, dirty
    idx = i % len(names)
    dirty = True


# ------------------------------------------------------------------ drawing

def message(title, detail):
    screen.pen = color.white
    screen.text(title, rect(10, 70, W - 20, 30), align=(image.CENTER, image.MIDDLE))
    screen.pen = GREY
    screen.text(detail, rect(10, 105, W - 20, 80), align=(image.CENTER, image.TOP))


def draw():
    screen.pen = BG
    screen.clear()
    if not names:
        message("No images found", "Copy PNGs into apps/" + APP + "/assets")
        return
    img = get(idx)
    if isinstance(img, str):
        message("Can't load " + names[idx], img)
    else:
        screen.blit(img, vec2((W - img.width) // 2, (H - img.height) // 2))


def handle_input():
    """Act on button presses; True means leave the app."""
    global back, level

    if badge.pressed(BUTTON_C):
        return True                      # the badge resets back into the menu

    if badge.pressed(BUTTON_A):
        set_brightness(level + 1)

    if names:
        if badge.pressed(BUTTON_B) and qr is not None:
            if idx == qr:
                show(back)
            else:
                back = idx
                show(qr)
        elif badge.pressed(BUTTON_DOWN):
            show(idx + 1)
        elif badge.pressed(BUTTON_UP):
            show(idx - 1)
    return False


def main():
    global dirty
    set_brightness(level)
    for i in range(len(names)):          # decode every picture now, at full speed
        get(i)
    while True:
        badge.poll()
        if handle_input():
            return
        if dirty:
            cpu(None)
            draw()
            display.update()             # only push a frame when it changed
            dirty = False
            cpu(IDLE_HZ)
        else:
            time.sleep_ms(POLL_MS)


main()
