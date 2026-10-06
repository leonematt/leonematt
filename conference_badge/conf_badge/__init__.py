# Conf Badge: a wearable name badge for the Tufty 2350.
#
# Shows every .png / .jpg in this app's assets/ folder, in filename order,
# so number the files to set the order (1_badge.png, 2_card.png, 3_qr.png).
# Images that aren't 320x240 are scaled to fit and centred.
#
#   C or DOWN   next screen
#   A or UP     previous screen
#   B           jump to the QR screen (any file with "qr" in its name)
#   HOME        back to the menu
#
# The last screen shown is remembered, so after a reset or sleep the badge
# comes back to the same picture.

import os

APP = "conf_badge"
EXTS = ("png", "jpg", "jpeg")
OVERLAY_MS = 1500  # how long the page dots + battery show after a button press

BG = color.rgb(14, 16, 20)
ACCENT = color.rgb(238, 76, 44)
DIM = color.rgb(70, 74, 84)
GREY = color.rgb(138, 145, 158)

badge.mode(HIRES)            # Tufty apps start in 160x120; use the full 320x240
badge.default_clear = None   # keep the frame between updates, redraw only on change
try:
    badge.caselights(0)      # rear LEDs off to save battery
except Exception:
    pass

W, H = screen.width, screen.height


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

state = {"index": 0}
try:
    loaded = State.load(APP, state)
    if isinstance(loaded, dict):
        state = loaded
except Exception:
    pass

try:
    idx = int(state.get("index", 0)) % len(names) if names else 0
except Exception:                         # corrupted save file: start from the first screen
    idx = 0
dirty = True
overlay_until = 0


def get(i):
    if i not in cache:
        try:
            cache[i] = load(folder + "/" + names[i])
        except Exception as e:
            cache[i] = str(e)            # remember the failure, show it on screen
    return cache[i]


def go(i):
    global idx, dirty, overlay_until
    idx = i % len(names)
    dirty = True
    overlay_until = badge.ticks + OVERLAY_MS
    state["index"] = idx
    try:
        State.save(APP, state)
    except Exception:
        pass


# ------------------------------------------------------------------ drawing

def message(title, detail):
    screen.pen = color.white
    screen.text(title, rect(10, 70, W - 20, 30), align=(image.CENTER, image.MIDDLE))
    screen.pen = GREY
    screen.text(detail, rect(10, 105, W - 20, 80), align=(image.CENTER, image.TOP))


def overlay():
    screen.pen = BG                         # dark strip so it reads on any image
    screen.rectangle(0, H - 20, W, 20)
    n = len(names)
    if n > 1:
        gap = 10
        x0 = W // 2 - (n - 1) * gap // 2
        for i in range(n):
            screen.pen = ACCENT if i == idx else DIM
            screen.circle(x0 + i * gap, H - 10, 3)
    try:
        level = badge.battery_level()
    except Exception:
        return
    bx, by = W - 32, H - 15                 # small battery gauge, bottom right
    screen.pen = GREY
    screen.rectangle(bx, by, 22, 10)
    screen.rectangle(bx + 22, by + 3, 2, 4)
    screen.pen = BG
    screen.rectangle(bx + 1, by + 1, 20, 8)
    screen.pen = ACCENT if level < 20 else color.rgb(240, 242, 245)
    screen.rectangle(bx + 2, by + 2, max(1, 18 * level // 100), 6)


def draw(with_overlay):
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
    if with_overlay:
        overlay()


def update():
    global dirty, overlay_until
    if names:
        if badge.pressed(BUTTON_C) or badge.pressed(BUTTON_DOWN):
            go(idx + 1)
        elif badge.pressed(BUTTON_A) or badge.pressed(BUTTON_UP):
            go(idx - 1)
        elif badge.pressed(BUTTON_B):
            for i in range(len(names)):
                if "qr" in names[i].lower():
                    go(i)
                    break

    showing = badge.ticks < overlay_until
    if dirty or (overlay_until and not showing):
        draw(showing)
        dirty = False
        if not showing:
            overlay_until = 0


run(update)
