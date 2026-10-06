"""Turn any image into a 320x240 PNG for the Tufty badge.

    pip install pillow
    python fit_image.py pytorch_badge.jpg            # fit inside, dark bars around it
    python fit_image.py pytorch_badge.jpg --fill     # crop to fill the whole screen
    python fit_image.py pytorch_badge.jpg -o 1_badge.png

Copy the result into apps/conf_badge/assets/ on the TUFTY drive. The number
prefix sets its position in the rotation (1_ = first screen).
"""
import argparse
from pathlib import Path

from PIL import Image, ImageOps

W, H = 320, 240
BG = (14, 16, 20)

p = argparse.ArgumentParser()
p.add_argument("src")
p.add_argument("-o", "--out", default="1_badge.png")
p.add_argument("--fill", action="store_true", help="crop to fill instead of letterboxing")
a = p.parse_args()

im = ImageOps.exif_transpose(Image.open(a.src)).convert("RGB")   # respect phone rotation
if a.fill:
    out = ImageOps.fit(im, (W, H), Image.LANCZOS)
else:
    im.thumbnail((W, H), Image.LANCZOS)
    out = Image.new("RGB", (W, H), BG)
    out.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
out.save(a.out, optimize=True)
print(f"wrote {Path(a.out).resolve()} ({W}x{H})")
