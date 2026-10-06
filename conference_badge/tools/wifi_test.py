# WiFi check for the Tufty badge: steps through the battery reads, drawing,
# joining WiFi, DNS, NTP and an HTTPS download of fractal-securities.com,
# printing each step over USB. Runs on the badge:
#
#   pip install mpremote
#   mpremote run tools/wifi_test.py      (hold A while the badge starts to keep
#                                         the menu off WiFi while you test)
#
# Each step prints "STEP n ..." before it starts and "  ok" when it's done. If
# the badge ever locks up, the last STEP line printed shows where. Unplug a
# frozen badge from the computer before doing anything else, or Linux's USB
# handling can get stuck waiting on it. Nothing is written to flash.

import gc
import os
import sys
import time

import machine
import network

T0 = time.ticks_ms()


def say(*a):
    print("[{:6d} ms]".format(time.ticks_diff(time.ticks_ms(), T0)), *a)


def step(n, what):
    say("STEP", n, what)
    time.sleep_ms(150)      # let the line reach the computer before anything risky


def ok(extra=""):
    say("  ok", extra)


def frames(n, label):
    for i in range(n):
        screen.pen = color.rgb(0, 80 + (i % 2) * 120, 40)
        screen.clear()
        screen.pen = color.white
        screen.text("{} {}/{}".format(label, i + 1, n), 6, 6)
        display.update()
        time.sleep_ms(30)


say("firmware", os.uname().release, os.uname().machine)
say("cpu", machine.freq(), "Hz, free mem", gc.mem_free())
try:
    import secrets
    SSID, PSK = secrets.WIFI_SSID, secrets.WIFI_PASSWORD
except Exception as e:
    SSID = PSK = ""
    say("no secrets:", e)
say("network set:", bool(SSID), repr(SSID))
if not SSID:
    sys.exit("set a network in Settings first")

step(1, "battery / USB / charging (charging is read through the WiFi chip)")
say("  usb", badge.usb_connected(), "level", badge.battery_level())
say("  charging", badge.is_charging())
ok()

step(2, "display, WiFi off, low-res (like Pimoroni's apps)")
badge.mode(LORES | VSYNC)
frames(20, "lores")
ok()

step(3, "display, WiFi off, full-res (like these apps)")
badge.mode(HIRES)
frames(20, "hires")
ok()

step(4, "WiFi on + connect, no drawing (like Settings, which works)")
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PSK)
start = time.ticks_ms()
while not wlan.isconnected():
    if wlan.status() < 0 or time.ticks_diff(time.ticks_ms(), start) > 20000:
        sys.exit("could not connect, status {}".format(wlan.status()))
    time.sleep_ms(100)
ok(wlan.ifconfig()[0])

step(5, "display while connected, low-res (like Pimoroni's apps)")
badge.mode(LORES | VSYNC)
frames(30, "lores+wifi")
ok()

step(6, "display while connected, full-res (like the menu / Fractal app)")
badge.mode(HIRES)
frames(30, "hires+wifi")
ok()

step(7, "idle while connected: 3 s of sleep_ms(20) loops")
for _ in range(150):
    badge.poll()
    time.sleep_ms(20)
ok()

step(8, "DNS lookup")
import socket
say("  ", socket.getaddrinfo("fractal-securities.com", 443)[0][-1])
ok()

step(9, "NTP time sync (the menu does this once connected)")
import ntptime
ntptime.settime()
ok(time.localtime())

step(10, "HTTPS download with the firmware's fetch module")
import fetch
f = fetch.AsyncFetch("fractal-securities.com", 443, use_tls=True, max_bytes=1024 * 1024, timeout=15)
f.fetch("/")
last = None
while True:
    s = f.update()
    phase = getattr(f, "_phase", None)
    if phase != last:
        say("   phase", phase)
        last = phase
    if s == fetch.AsyncFetch.DONE:
        break
    time.sleep_ms(2)
html = bytes(f.body).decode("utf-8")
f.reset()
ok("{} bytes, HTTP {}".format(len(html), f.http_status))

step(11, "parse the table")
sys.path.insert(0, "/system/apps/fractal_securities")
import fractal_table
d = fractal_table.parse(html)
ok("as of {}, {} rows, first {}".format(d["as_of"], len(d["rows"]), d["rows"][:1]))

step(12, "full-res drawing again after the download")
frames(20, "after https")
ok()

step(13, "WiFi off")
wlan.disconnect()
wlan.active(False)
ok()

say("ALL STEPS PASSED")
