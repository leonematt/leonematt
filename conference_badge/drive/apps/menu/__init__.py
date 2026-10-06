import os
import sys
import time

sys.path.insert(0, "/system/apps/menu")
sys.path.insert(0, "/")
if "/system/lib" not in sys.path:
    sys.path.append("/system/lib")
os.chdir("/system/apps/menu")

import power

# The menu runs at the full 320x240 so the rain is crisp. Apps expect the
# badge's default 160x120, so that's restored just before one is launched.
badge.mode(HIRES)
screen.antialias = image.X2

# ---- power
# The power mode (set in the Settings app, see /system/lib/power.py) decides
# how fast the rain steps, the brightness, and the CPU speed between frames.
# The menu draws only when the rain steps or a button is pressed; the display
# holds the last frame by itself in between.
POLL_MS = 20                     # button check interval between frames
MODE = power.apply()             # panel refresh + backlight for the saved mode
IDLE_HZ = MODE["idle_hz"]
cpu = power.cpu

import ui
import status
from app import Apps

# Hold A while the badge starts (until the menu appears) to skip WiFi this boot.
status.disabled = badge.held(BUTTON_A)
from rain import Rain

# find installed apps and create apps (at full speed: this decodes the icons)
apps = Apps("/system/apps")
rain = Rain(screen.width, screen.height, **MODE["rain"])

active = 0


def launch_app(path):
    status.wifi_off()                # save battery; apps that need WiFi connect themselves
    cpu(None)                        # apps get the badge's normal speed...
    badge.mode(LORES | VSYNC)        # ...and its default screen mode
    return path


def handle_input():
    """-> (app path to launch or None, whether anything was pressed)."""
    global active
    n = len(apps)
    if not n:
        return None, False
    pressed = badge.pressed()
    if pressed:
        if badge.pressed(BUTTON_C):
            if (active % 3) < 2 and active < n - 1:
                active += 1
        if badge.pressed(BUTTON_A):
            if (active % 3) > 0 and active > 0:
                active -= 1
        if badge.pressed(BUTTON_UP) and active >= 3:
            active -= 3
        if badge.pressed(BUTTON_DOWN):
            active += 3
            if active >= n:
                active = n - 1
        apps.activate(active)
        if badge.pressed(BUTTON_B):
            return apps.active.path, True
    return None, bool(pressed)


def render():
    screen.pen = color.black
    screen.clear()
    screen.blit(rain.layer, vec2(0, 0))      # background: the rain covers the whole screen
    apps.draw_icons()
    apps.draw_label()
    apps.draw_pagination()
    ui.draw_status_bar()


def main():
    apps.activate(active)
    first = True
    while True:
        badge.poll()
        path, pressed = handle_input()
        if path:
            return launch_app(path)
        status.update()
        stepped = rain.advance()     # True when the rain has stepped
        if first or stepped or pressed:
            cpu(None)
            render()
            display.update()
            cpu(IDLE_HZ)
            first = False
        else:
            time.sleep_ms(POLL_MS)


# returned verbatim by `launch`: the path of the app to open next
on_exit = main()
