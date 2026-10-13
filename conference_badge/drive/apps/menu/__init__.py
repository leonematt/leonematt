import os
import sys

sys.path.insert(0, "/system/apps/menu")
sys.path.insert(0, "/")
os.chdir("/system/apps/menu")

# The menu runs at the full 320x240 so the rain is crisp. Apps expect the
# badge's default 160x120, so that's restored just before one is launched.
badge.mode(HIRES)
screen.antialias = image.X2

import ui
import status
from app import Apps
from rain import Rain

# find installed apps and create apps
apps = Apps("/system/apps")
rain = Rain(screen.width, screen.height)

active = 0

MAX_ALPHA = 255
alpha = 30


def launch_app(path):
    status.wifi_off()                # save battery; apps that need WiFi connect themselves
    badge.mode(LORES | VSYNC)        # hand apps the badge's default screen mode
    return path


def update():
    global active, alpha

    n = len(apps)
    if n:
        # process button inputs to switch between apps
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
            return launch_app(apps.active.path)

    status.update()

    # background: the rain layer covers the whole screen
    rain.advance()
    screen.blit(rain.layer, vec2(0, 0))

    apps.draw_icons()
    apps.draw_label()
    apps.draw_pagination()
    ui.draw_status_bar()

    if alpha <= MAX_ALPHA:
        screen.pen = color.rgb(0, 0, 0, 255 - alpha)
        screen.rectangle(screen.clip)
        alpha += 30

    return None


# "on_exit" will be called if callable, else returned verbatim by `launch`
on_exit = run(update).result
