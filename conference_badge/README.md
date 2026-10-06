# tufty-badge

Custom firmware image for a Pimoroni **Tufty 2350**: a green hex "matrix rain"
launcher with a status bar, and a full-screen conference name badge.

`drive/` is exactly what ends up on the badge's drive. `build_uf2.py` wraps it
around Pimoroni's stock v3.1.1 firmware and writes a single `.uf2` you can flash.

```
drive/                      what goes on the badge (mounted at /system)
  main.py                   stock boot script: opens the menu, then the chosen app
  secrets.py                WiFi/region template (see "WiFi" below)
  lib/power.py              power modes, shared by the menu and apps
  apps/menu/                the launcher
    __init__.py               input + frame loop (runs at 320x240)
    app.py                    app discovery and the icon grid
    ui.py                     status bar: prompt, clock, WiFi, battery
    status.py                 battery / USB / WiFi / NTP clock state
    rain.py                   hex-byte matrix rain
    daylightsaving.py         DST rules (from Pimoroni's clock app)
  apps/fractal_securities/  portfolio vs S&P 500 from fractal-securities.com
    __init__.py               WiFi + download + table screen
    fractal_table.py          HTML table parser (also used by tools/check_portfolio.py)
  apps/settings/            WiFi setup + power mode
  apps/conf_badge/          name badge app
    __init__.py
    assets/1_name.png         name card (generated)
    assets/2_qr.png           QR code (generated)
tools/
  make_screens.py           renders the name card + QR
  fit_image.py              fits any photo to 320x240
  check_portfolio.py        runs the portfolio parser against the live site
  wifi_test.py              on-badge WiFi / download check, step by step (mpremote)
build_uf2.py                drive/ -> build/tufty-badge.uf2
Makefile                    make uf2 | flash | screens | check-portfolio | clean
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
- The rain's timing (step rate, which is also how often the menu redraws, fall
  speed, trail fade, how often a drop starts) comes from the power mode, in
  `drive/lib/power.py`; colours and the font are at the top of `rain.py`.
- Every folder in `apps/` with an `__init__.py` is an app. The folder name is
  its label (`my_app` -> "My App"); an optional 24x24 `icon.png` is its icon.
  Apps start in the badge's default 160x120 mode. To follow the power mode in
  your own app: `sys.path.append("/system/lib")`, `import power`,
  `mode = power.apply()` (sets brightness and the panel refresh). Don't call
  `machine.freq()`: changing the CPU clock locks the badge up (see Battery).

## WiFi

WiFi icon: green = connected, sweeping = connecting, grey with a red slash =
disconnected. The menu only joins WiFi if a network is set, turns the radio
off before opening an app, and sets the clock from NTP once connected
(`REGION` + `TIMEZONE`, same rules as Pimoroni's clock app; the RTC keeps it).

**Hold A while the badge starts** (keep holding until the menu appears) to
skip WiFi for that boot. Because a network saved from Settings survives
reflashing, this is the way back in if WiFi ever misbehaves; from a computer,
`mpremote rm :/secrets.py` removes the saved network.

Two ways to set the network:

- **On the badge: Settings > WiFi.** Scan (or type a name), enter the password
  on the on-screen keyboard; the badge tests the connection before saving.
  It's saved as `/secrets.py` in the badge's own 1 MB storage, which the
  firmware reads *instead of* `secrets.py` on the drive, and which reflashing
  doesn't erase. *Use secrets.py from drive* deletes it again.
- **At build time:** copy `secrets.local.py.example` to `secrets.local.py`
  (git-ignored) and fill it in; `build_uf2.py` puts it on the drive as
  `secrets.py`. A network saved from Settings still takes priority.

## Settings

- **WiFi**: scan / type a network name / forget it / go back to the drive's
  `secrets.py`. On the keyboard **A / C** move left/right, **UP / DOWN** change
  row, **B** types; the bottom row has shift (`aA`), symbols (`#+=`), space,
  delete, `OK` and `back`.
- **Power mode**: Performance / Balanced / Power saver, saved in the badge's
  storage (`/state/settings.json`). Brightness changes straight away; the rest
  applies from the next screen.

| | Performance | Balanced (default) | Power saver |
|---|---|---|---|
| Menu rain | 20 fps | 4 fps | 1 fps |
| LCD self-refresh | 90 Hz | 60 Hz | 60 Hz |
| Brightness | 90% | 70% | 45% |

All of it lives in `drive/lib/power.py` (`PROFILES`); the menu and every app
read it through `power.apply()`.

## Conf Badge

- Opens on the name card. **B** flips to the QR code and back, **C** (or
  HOME) returns to the menu, **UP / DOWN** step through any extra pictures.
- **A** steps the screen brightness (90 / 70 / 45 / 25%), starting from the
  power mode's level.
- Screens are the PNG/JPGs in `assets/` in filename order; the one with "qr"
  in its name is what B flips to.
- Change the text or QR link in `CARD` at the top of `tools/make_screens.py`,
  then `make screens` (needs `pip install pillow qrcode` and the Inter and
  JetBrains Mono fonts, e.g. `apt install fonts-inter fonts-jetbrains-mono`).
- Add a photo as another screen:
  `python3 tools/fit_image.py photo.jpg -o drive/apps/conf_badge/assets/3_photo.png`

## Fractal Securities

Shows the performance table from <https://fractal-securities.com/>, just the
Portfolio and S&P 500 (VOO) columns, with the page's as-of date.

- Opens on the last table it saved, then joins WiFi (the network from
  Settings, or `secrets.py`), downloads the page, reads the table and saves it.
  WiFi is turned off again straight after. **B** refreshes, **C** (or HOME)
  goes back to the menu.
- The download uses the firmware's own non-blocking `fetch` module, a small
  step at a time with a 15 s no-data timeout and a 60 s overall limit, and
  follows redirects. Each stage (looking up the site, connecting, secure
  handshake, waiting for reply, downloading N KB, reading table) is shown in
  the footer and printed over USB (`mpremote` / Thonny), so if it ever stalls
  you can see exactly where.
- Negative returns are red, positive green. The footer shows when it last
  updated, or why an update failed (no WiFi set, can't reach the site, ...).
- The parser finds the table by its header row (a "Portfolio" column and an
  "S&P 500"/"VOO" column), not by markup or class names, so cosmetic changes
  to the site shouldn't break it. To check against the live site from your
  computer: `make check-portfolio`.

## Battery

Pimoroni's firmware runs the CPU overclocked at 250 MHz and its standard app
loop redraws and re-sends the whole screen as fast as it can, even when nothing
changes. The apps here avoid that:

- **The display holds the last frame by itself**, so frames are only sent when
  something changes: Conf Badge and Fractal Securities when you press a
  button, the menu when the rain steps (rate set by the power mode).
- **Between frames the loop sleeps**, checking the buttons every 20 ms, so the
  CPU spends most of its time idle.
- **The CPU clock is never changed.** Earlier builds dropped it to 48 MHz
  between frames, which locked the badge up: each change re-tunes the flash
  and PSRAM timing while the system is running from them. `power.cpu()` is
  now a no-op and nothing calls `machine.freq()`.
- **Brightness** is the biggest remaining draw: pick Power saver, or press A
  in Conf Badge.
- **WiFi** stays off unless a network is set, and is switched off whenever an
  app opens; the Fractal app turns it on only while it downloads. The battery
  is read every 30 s.

## Credits

Built on Pimoroni's [tufty2350](https://github.com/pimoroni/tufty2350) firmware
(MIT). `main.py`, `apps/menu/default_icon.png` and `apps/menu/daylightsaving.py`
come from it; the app discovery and input handling in the menu follow its stock
launcher.
