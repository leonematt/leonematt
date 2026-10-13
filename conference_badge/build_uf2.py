#!/usr/bin/env python3
"""Build a flashable Tufty 2350 UF2 from drive/.

Starts from Pimoroni's stock v3.1.1 "with-filesystem" UF2 (downloaded on first
run and checked against a pinned SHA-256), keeps its firmware and ROMFS blocks
byte for byte, and replaces the filesystem with a fresh FAT image built from
drive/. The FAT keeps the stock boot sector, so the geometry is exactly what
the firmware expects.

    python3 build_uf2.py                 # -> build/tufty-badge.uf2
    python3 build_uf2.py --flash         # build, then copy onto the RP2350 drive
    python3 build_uf2.py --flash /path/to/RP2350

If secrets.local.py exists next to this script, it goes on the badge as
secrets.py instead of drive/secrets.py, so WiFi details stay out of git.

Needs Python 3.8+ and mtools (mcopy). If dosfstools (fsck.fat) is installed
the image is checked too.
"""
import argparse
import glob
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))

BASE_NAME = "tufty-v3.1.1-micropython-with-filesystem.uf2"
BASE_URL = "https://github.com/pimoroni/tufty2350/releases/download/v3.1.1/" + BASE_NAME
BASE_SHA256 = "2ea56534250abc1bb7b484f92ccd4fbfebe428f161daa00169a48b45da2fe74a"

UF2_MAGIC0, UF2_MAGIC1, UF2_MAGIC_END = 0x0A324655, 0x9E5D5157, 0x0AB16F30
RP2350_ARM_S = 0xE48BFF59      # UF2 family of the firmware/ROMFS/filesystem blocks
FS_BASE = 0x10300000           # where the FAT filesystem lives in flash
PAYLOAD = 256                  # bytes of flash per UF2 block

SKIP_NAMES = {"__pycache__", ".DS_Store", ".git", ".gitkeep", "Thumbs.db"}


def die(msg):
    sys.exit("error: " + msg)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------ base firmware

def base_firmware(path):
    """Path to the stock UF2: the one given, or a verified cached download."""
    if path:
        if not os.path.isfile(path):
            die(f"base firmware not found: {path}")
        if sha256(path) != BASE_SHA256:
            print(f"note: {path} is not the stock v3.1.1 image; using it anyway")
        return path

    cache = os.path.join(ROOT, "firmware", BASE_NAME)
    if os.path.isfile(cache) and sha256(cache) == BASE_SHA256:
        return cache

    os.makedirs(os.path.dirname(cache), exist_ok=True)
    print(f"downloading {BASE_URL}")
    tmp = cache + ".part"
    try:
        urllib.request.urlretrieve(BASE_URL, tmp)
    except OSError as e:
        die(f"download failed ({e}). Fetch {BASE_NAME} from "
            "https://github.com/pimoroni/tufty2350/releases/tag/v3.1.1 and pass --base")
    if sha256(tmp) != BASE_SHA256:
        os.remove(tmp)
        die("downloaded firmware does not match the pinned SHA-256")
    os.replace(tmp, cache)
    return cache


def read_uf2(path):
    """-> (blocks of other families, {addr: data} for the RP2350 family, flags)."""
    data = open(path, "rb").read()
    if len(data) % 512:
        die(f"{path} is not a UF2 file")
    other, payload, flags = [], {}, None
    for i in range(0, len(data), 512):
        b = data[i:i + 512]
        m0, m1, fl, addr, size, _, _, family = struct.unpack("<8I", b[:32])
        if m0 != UF2_MAGIC0 or m1 != UF2_MAGIC1 or struct.unpack("<I", b[508:])[0] != UF2_MAGIC_END:
            die(f"bad UF2 block {i // 512} in {path}")
        if family != RP2350_ARM_S:
            other.append(b)              # e.g. the RP2350-E10 workaround block; kept as is
            continue
        if size != PAYLOAD:
            die(f"unexpected {size}-byte block in {path}")
        payload[addr] = b[32:32 + size]
        flags = fl
    return other, payload, flags


# ------------------------------------------------------------------ FAT image

class Geometry:
    def __init__(self, boot):
        (self.bps, self.spc, self.reserved, self.fats, self.root_entries,
         total16, self.media, self.spf) = struct.unpack_from("<HBHBHHBH", boot, 11)
        total32 = struct.unpack_from("<I", boot, 32)[0]
        self.sectors = total16 or total32
        self.size = self.sectors * self.bps
        self.fat_off = self.reserved * self.bps
        self.fat_len = self.spf * self.bps
        self.root_off = self.fat_off + self.fats * self.fat_len
        self.data_off = self.root_off + self.root_entries * 32
        self.cluster = self.spc * self.bps
        self.clusters = (self.size - self.data_off) // self.cluster
        self.fat12 = self.clusters < 4085


def blank_fat(base_payload):
    """A fresh, empty FAT image that keeps the stock boot sector and volume label."""
    boot = bytearray(base_payload.get(FS_BASE, b"") + base_payload.get(FS_BASE + PAYLOAD, b""))
    if boot[510:512] != b"\x55\xaa":
        die("no FAT boot sector at 0x10300000 in the base firmware")
    geo = Geometry(boot)
    stock = bytearray(geo.size)
    for addr, chunk in base_payload.items():
        if FS_BASE <= addr < FS_BASE + geo.size:
            stock[addr - FS_BASE:addr - FS_BASE + len(chunk)] = chunk

    img = bytearray(geo.size)
    img[:geo.fat_off] = stock[:geo.fat_off]                      # boot sector / reserved
    reserved = bytes([geo.media, 0xFF, 0xFF]) if geo.fat12 else bytes([geo.media, 0xFF, 0xFF, 0xFF])
    for n in range(geo.fats):                                     # empty FAT(s): just entries 0 and 1
        o = geo.fat_off + n * geo.fat_len
        img[o:o + len(reserved)] = reserved
    label = stock[geo.root_off:geo.root_off + 32]
    if label[11] == 0x08:                                         # keep the TUFTY label
        img[geo.root_off:geo.root_off + 32] = label
    return img, geo


def stage(drive, secrets_local):
    """Copy drive/ to a temp dir, minus junk, with secrets.local.py swapped in."""
    tmp = tempfile.mkdtemp(prefix="tufty-")
    dst = os.path.join(tmp, "drive")

    def ignore(_dir, names):
        return [n for n in names if n in SKIP_NAMES or n.startswith("._")]

    shutil.copytree(drive, dst, ignore=ignore)
    if secrets_local:
        shutil.copyfile(secrets_local, os.path.join(dst, "secrets.py"))
    return tmp, dst


def fill_fat(img_path, tree):
    if not shutil.which("mcopy"):
        die("mcopy not found: install mtools (e.g. apt install mtools / pacman -S mtools / dnf install mtools)")
    env = dict(os.environ, MTOOLS_SKIP_CHECK="1")
    for name in sorted(os.listdir(tree)):
        r = subprocess.run(["mcopy", "-s", "-i", img_path, os.path.join(tree, name), "::/"],
                           env=env, capture_output=True, text=True)
        if r.returncode:
            die(f"mcopy failed for {name}: {r.stderr.strip()}")
    if shutil.which("fsck.fat"):
        # The stock image keeps its "TUFTY" label only in the root directory, which
        # fsck.fat reports (and exits non-zero for); anything beyond that is a problem.
        r = subprocess.run(["fsck.fat", "-n", img_path], capture_output=True, text=True)
        benign = ("fsck.fat ", "There is no label in boot sector", "Auto-copying volume label",
                  "Leaving filesystem unchanged", img_path + ":")
        issues = [l for l in (r.stdout + r.stderr).splitlines() if l.strip() and not l.strip().startswith(benign)]
        if issues:
            die("fsck.fat found problems:\n" + "\n".join(issues))


def used_bytes(img, geo):
    """Bytes from the start of the image to the end of the last allocated cluster."""
    fat = img[geo.fat_off:geo.fat_off + geo.fat_len]
    last = 1
    for n in range(2, geo.clusters + 2):
        if geo.fat12:
            o = n * 3 // 2
            v = fat[o] | fat[o + 1] << 8
            v = v >> 4 if n & 1 else v & 0xFFF
        else:
            v = fat[n * 2] | fat[n * 2 + 1] << 8
        if v:
            last = n
    end = geo.data_off + (last - 1) * geo.cluster
    return max(end, geo.data_off)


# ------------------------------------------------------------------ UF2 out

def write_uf2(path, other, payload, flags, fs_img, fs_len):
    blocks = sorted((a, d) for a, d in payload.items() if a < FS_BASE)   # firmware + ROMFS
    blocks += [(FS_BASE + o, bytes(fs_img[o:o + PAYLOAD])) for o in range(0, fs_len, PAYLOAD)]
    n = len(blocks)
    with open(path, "wb") as f:
        for b in other:
            f.write(b)
        for i, (addr, data) in enumerate(blocks):
            f.write(struct.pack("<8I", UF2_MAGIC0, UF2_MAGIC1, flags, addr, PAYLOAD, i, n, RP2350_ARM_S))
            f.write(data.ljust(476, b"\0"))
            f.write(struct.pack("<I", UF2_MAGIC_END))
    return n + len(other)


# ------------------------------------------------------------------ flashing

def find_rp2350():
    user = os.environ.get("USER", "")
    candidates = [f"/run/media/{user}/RP2350", f"/media/{user}/RP2350", "/Volumes/RP2350"]
    candidates += glob.glob("/run/media/*/RP2350") + glob.glob("/media/*/RP2350")
    for c in candidates:
        if os.path.isfile(os.path.join(c, "INFO_UF2.TXT")):
            return c
    return None


def flash(uf2, mount):
    mount = mount or find_rp2350()
    if not mount or not os.path.isfile(os.path.join(mount, "INFO_UF2.TXT")):
        die("no RP2350 drive found. On the badge's back hold BOOT and tap RESET, "
            "then run again (or pass its mount point: --flash /path/to/RP2350)")
    print(f"copying to {mount} ...")
    try:
        shutil.copyfile(uf2, os.path.join(mount, os.path.basename(uf2)))
        os.sync()
    except OSError:
        pass                     # the drive vanishes as soon as the badge takes the image
    print("done; the badge reboots on its own")


# ------------------------------------------------------------------ main

def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--drive", default=os.path.join(ROOT, "drive"), help="folder to put on the badge (default: drive/)")
    p.add_argument("--base", help="stock with-filesystem UF2 to build on (default: download v3.1.1)")
    p.add_argument("-o", "--out", default=os.path.join(ROOT, "build", "tufty-badge.uf2"))
    p.add_argument("--flash", nargs="?", const="", metavar="MOUNT", help="copy the result onto the RP2350 drive")
    a = p.parse_args()

    if not os.path.isfile(os.path.join(a.drive, "main.py")):
        die(f"{a.drive} has no main.py; is it the badge's drive folder?")

    other, payload, flags = read_uf2(base_firmware(a.base))
    img, geo = blank_fat(payload)

    secrets_local = os.path.join(ROOT, "secrets.local.py")
    tmp, tree = stage(a.drive, secrets_local if os.path.isfile(secrets_local) else None)
    try:
        img_path = os.path.join(tmp, "fs.img")
        with open(img_path, "wb") as f:
            f.write(img)
        fill_fat(img_path, tree)
        img = open(img_path, "rb").read()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    fs_len = used_bytes(img, geo)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    count = write_uf2(a.out, other, payload, flags, img, fs_len)
    note = " (with secrets.local.py)" if os.path.isfile(secrets_local) else ""
    shown = os.path.relpath(a.out)
    shown = a.out if shown.startswith("..") else shown
    print(f"wrote {shown}: {count} blocks, {fs_len // 1024} KiB of filesystem{note}")

    if a.flash is not None:
        flash(a.out, a.flash or None)


if __name__ == "__main__":
    main()
