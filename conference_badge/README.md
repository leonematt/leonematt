# tufty-badge

Custom firmware image for a Pimoroni **Tufty 2350**: a green hex "matrix rain"
launcher with a status bar, and a full-screen conference name badge.

`drive/` is exactly what ends up on the badge's drive. `build_uf2.py` wraps it
around Pimoroni's stock v3.1.1 firmware and writes a single `.uf2` you can flash.

```
drive/                      what goes on the badge (mounted at /system)
  main.py                   stock boot script: opens the menu, then the chosen app
  secrets.py                WiFi/region template (see "WiFi" below)
  apps/menu/                the launcher
    __init__.py               input + frame loop (runs at 320x240)
    app.py                    app discovery and the icon grid
    ui.py                     status bar: prompt, clock, WiFi, battery
    status.py                 battery / USB / WiFi / NTP clock state
    rain.py                   hex-byte matrix rain
    daylightsaving.py         DST rules (from Pimoroni's clock app)
  apps/conf_badge/          name badge app
    __init__.py
    assets/1_name.png         name card (generated)
    assets/2_qr.png           QR code (generated)
tools/
  make_screens.py           renders the name card + QR
  fit_image.py              fits any photo to 320x240
build_uf2.py                drive/ -> build/tufty-badge.uf2
Makefile                    make uf2 | flash | screens | clean
```

## Build and flash

Needs Python 3.8+ and **mtools** (`mcopy`); **dosfstools** (`fsck.fat`) is used
to check the image if it's installed.

```bash
make uf2        # -> build/tufty-badge.uf2
make flash      # build, then copy it onto the badge
```

Before `make flash`, put the badge in bootloader mode: on the back, hold
**BOOT** and tap **RESET**. A drive called `RP2350` mounts; the script finds
it under `/run/media/$USER`, `/media/$USER` or `/Volumes`, or pass the mount
point: `python3 build_uf2.py --flash /path/to/RP2350`.

The first build downloads `tufty-v3.1.1-micropython-with-filesystem.uf2` from
Pimoroni's GitHub release into `firmware/` and checks its SHA-256. Offline,
download it yourself and pass `--base path/to/it.uf2`. The firmware and ROMFS
blocks are copied byte for byte; only the filesystem is replaced, using the
stock FAT boot sector so the layout is what the firmware expects.

Flashing replaces **everything** on the badge's drive with `drive/`.

## Quick edits without reflashing

Double-tap **RESET**: the badge's filesystem mounts as a drive called `TUFTY`.
Edit or copy files there, eject, press RESET. Copy the changes back into
`drive/` if you want them in the next build.

## Menu

- **A / C** left/right, **UP / DOWN** rows, **B** opens the app.
- Status bar: `leonematt@tufty:~$` prompt (`PROMPT` in `ui.py`), clock, WiFi,
  battery % and gauge (red under 20%, animated while charging).
- Rain settings (speed, trail length, density, colours) are at the top of `rain.py`.
- Every folder in `apps/` with an `__init__.py` is an app. The folder name is
  its label (`my_app` -> "My App"); an optional 24x24 `icon.png` is its icon.
  Apps start in the badge's default 160x120 mode.

## WiFi

WiFi icon: green = connected, sweeping = connecting, grey with a red slash =
disconnected. The menu only joins WiFi if `WIFI_SSID` is set, turns the radio
off before opening an app, and sets the clock from NTP once connected
(`REGION` + `TIMEZONE`, same rules as Pimoroni's clock app; the RTC keeps it).

Keep credentials out of git: copy `secrets.local.py.example` to
`secrets.local.py` (git-ignored) and fill it in. `build_uf2.py` puts it on the
badge as `secrets.py` in place of the blank `drive/secrets.py`.

## Conf Badge

- Opens on the name card. **B** flips to the QR code and back, **C** (or
  HOME) returns to the menu, **UP / DOWN** step through any extra pictures.
- Screens are the PNG/JPGs in `assets/` in filename order; the one with "qr"
  in its name is what B flips to.
- Change the text or QR link in `CARD` at the top of `tools/make_screens.py`,
  then `make screens` (needs `pip install pillow qrcode` and the Inter and
  JetBrains Mono fonts, e.g. `apt install fonts-inter fonts-jetbrains-mono`).
- Add a photo as another screen:
  `python3 tools/fit_image.py photo.jpg -o drive/apps/conf_badge/assets/3_photo.png`

## Credits

Built on Pimoroni's [tufty2350](https://github.com/pimoroni/tufty2350) firmware
(MIT). `main.py`, `apps/menu/default_icon.png` and `apps/menu/daylightsaving.py`
come from it; the app discovery and input handling in the menu follow its stock
launcher.
