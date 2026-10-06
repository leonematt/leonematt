"""Render the Conf Badge screens at the Tufty's 320x240.

    pip install pillow qrcode
    python make_screens.py                # writes 1_name.png and 2_qr.png here
    python make_screens.py -o drive/apps/conf_badge/assets

Edit the CARD dict to change the text. Fonts: Inter + JetBrains Mono
(on Debian/Ubuntu: apt install fonts-inter fonts-jetbrains-mono), or point the
FONT_* paths at your own copies.
"""
import argparse
import os

import qrcode
from PIL import Image, ImageDraw, ImageFont

W, H = 320, 240
BG = (14, 16, 20)
WHITE = (240, 242, 245)
GREY = (138, 145, 158)
ACCENT = (238, 76, 44)

CARD = {
    "name": ("MATT", "LEON"),          # one line each, centred, as big as fits
    "role": "Founding Engineer ML Systems/Performance",
    "company": "Kernelize AI",
    "url": "leonematt.com",
    "qr": "HTTPS://LEONEMATT.COM",   # upper case keeps the QR small (alphanumeric mode)
}

FONT_NAME = "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf"
FONT_ROLE = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
FONT_COMPANY = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
FONT_MONO = "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf"

MARGIN = 14


def ink_box(draw, text, font):
    return draw.textbbox((0, 0), text, font=font, anchor="ls")   # relative to the baseline


def fit(draw, text, path, max_size, width):
    """Biggest font (<= max_size) that keeps text within width."""
    for size in range(max_size, 6, -1):
        f = ImageFont.truetype(path, size)
        if draw.textlength(text, font=f) <= width:
            return f
    return f


def cap_height(draw, font):
    return -ink_box(draw, "H", font)[1]


def ink_x(ch, font):
    """(left, right) of the actual ink of some text, relative to its origin."""
    size = font.size * (len(ch) + 2)
    im = Image.new("L", (size, font.size * 3), 0)
    ImageDraw.Draw(im).text((font.size, font.size * 2), ch, font=font, fill=255, anchor="ls")
    box = im.getbbox()
    return box[0] - font.size, box[2] - font.size


def draw_centered(d, line, font, base):
    """Draw a line with its normal spacing, its ink centred on the screen."""
    left, right = ink_x(line, font)
    d.text(((W - (right - left)) / 2 - left, base), line, font=font, fill=WHITE, anchor="ls")


def name_screen(path):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    span = W - 2 * MARGIN

    # details, laid out from the bottom up
    url = ImageFont.truetype(FONT_MONO, 13)
    company = ImageFont.truetype(FONT_COMPANY, 19)
    role = fit(d, CARD["role"], FONT_ROLE, 16, span)
    url_base = H - 10
    company_base = url_base - cap_height(d, url) - 10
    role_base = company_base - cap_height(d, company) - 8
    bar_y = role_base - cap_height(d, role) - 9
    name_bottom = bar_y - 8

    # name: the biggest size whose widest line fits the screen and whose two
    # lines fit above the details; each line is centred
    top = 11
    for size in range(160, 20, -1):
        f = ImageFont.truetype(FONT_NAME, size)
        boxes = [ink_box(d, line, f) for line in CARD["name"]]
        widest = max(b[2] - b[0] for b in boxes)
        cap = cap_height(d, f)
        gap = round(cap * 0.14)
        if widest <= span and len(boxes) * cap + (len(boxes) - 1) * gap <= name_bottom - top:
            break
    base = top + cap
    for line, b in zip(CARD["name"], boxes):
        draw_centered(d, line, f, base)
        base += cap + gap

    d.rectangle([MARGIN, bar_y, MARGIN + 32, bar_y + 3], fill=ACCENT)
    d.text((MARGIN, role_base), CARD["role"], font=role, fill=WHITE, anchor="ls")
    d.text((MARGIN, company_base), CARD["company"], font=company, fill=ACCENT, anchor="ls")
    d.text((MARGIN, url_base), CARD["url"], font=url, fill=GREY, anchor="ls")
    im.save(path, optimize=True)
    print(f"name {f.size}px (cap {cap}px), role {role.size}px")
    return im


def qr_screen(path):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q, border=0, box_size=1)
    qr.add_data(CARD["qr"])
    qr.make(fit=True)
    m = qr.get_matrix()
    n = len(m)
    scale = (H - 2 * 2 * 8) // n          # biggest whole-pixel module size leaving ~2 modules of quiet zone
    size = n * scale
    im = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    ox, oy = (W - size) // 2, (H - size) // 2
    for r, row in enumerate(m):
        for c, on in enumerate(row):
            if on:
                d.rectangle([ox + c * scale, oy + r * scale, ox + (c + 1) * scale - 1, oy + (r + 1) * scale - 1], fill=(0, 0, 0))
    im.save(path, optimize=True)
    return im, n, scale


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("-o", "--out", default=".")
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)
    name_screen(os.path.join(a.out, "1_name.png"))
    _, n, s = qr_screen(os.path.join(a.out, "2_qr.png"))
    print(f"wrote 1_name.png and 2_qr.png ({n}x{n} modules at {s}px) to {a.out}")
