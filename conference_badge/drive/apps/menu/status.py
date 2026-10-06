# Status for the menu's top bar: battery, USB/charging, WiFi and the clock.
#
# WiFi: if secrets.py has a WIFI_SSID, the menu joins it in the background
# (never blocking, never throwing an error screen) and the icon shows
# connecting / connected / failed. With no SSID the radio stays off.
# Once online, the clock is set once from NTP using REGION + TIMEZONE from
# secrets.py (same rules as Pimoroni's clock app) and kept in the RTC, so it
# keeps showing on later boots even without WiFi.

import time

import power

OFF, CONNECTING, ONLINE, FAILED = 0, 1, 2, 3

BATTERY_EVERY_MS = 30000    # battery is an averaged ADC read; no need to do it often
WIFI_START_MS = 800         # let the menu draw before waking the radio
WIFI_POLL_MS = 250
WIFI_TIMEOUT_MS = 20000     # give up on an attempt after this long...
WIFI_RETRY_MS = 30000       # ...and try again after this long

# (hemisphere, week, month, weekday, hour) in, same out, minutes clocks change by
REGIONS = {
    "us": (0, 2, 3, 6, 2, 1, 11, 6, 2, 60),
    "cuba": (0, 2, 3, 6, 0, 1, 11, 6, 1, 60),
    "eu": (0, 0, 3, 6, 1, 0, 10, 6, 1, 60),
    "moldova": (0, 0, 3, 6, 2, 0, 10, 6, 3, 60),
    "lebanon": (0, 0, 3, 6, 0, 0, 10, 6, 0, 60),
    "egypt": (0, 0, 4, 4, 0, 0, 10, 3, 24, 60),
    "chile": (1, 1, 9, 5, 24, 1, 4, 5, 24, 60),
    "australia": (1, 1, 10, 6, 2, 1, 4, 6, 3, 60),
    "nz": (1, 0, 9, 6, 2, 1, 4, 6, 3, 60),
}

try:
    import secrets
    SSID = getattr(secrets, "WIFI_SSID", "") or ""
    PSK = getattr(secrets, "WIFI_PASSWORD", "") or ""
    REGION = getattr(secrets, "REGION", "") or ""
    TIMEZONE = getattr(secrets, "TIMEZONE", 0) or 0
except Exception:                      # no or broken secrets.py: treat WiFi as off
    SSID, PSK, REGION, TIMEZONE = "", "", "", 0

disabled = False        # set by the menu if A was held at start-up: no WiFi this boot
battery = None          # 0-100, None until first read
usb = False
charging = False
wifi = OFF

_started = badge.ticks
_battery_at = None
_wlan = None
_wifi_at = 0
_attempt_at = 0
_synced = False


def _read_battery():
    global battery, usb, charging, _battery_at
    _battery_at = badge.ticks
    try:
        usb = badge.usb_connected()
        charging = badge.is_charging()
        battery = badge.battery_level()
    except Exception:
        pass


def _connect():
    global _wlan, wifi, _attempt_at
    _attempt_at = badge.ticks
    try:
        import network
        power.radio(True)                # keeps the CPU at full speed while WiFi is on
        _wlan = network.WLAN(network.STA_IF)
        _wlan.active(True)
        if _wlan.isconnected():
            wifi = ONLINE
            return
        _wlan.connect(SSID, PSK)
        wifi = CONNECTING
    except Exception:
        _give_up()


def _give_up():
    """A failed attempt: radio fully off (so the CPU can slow down again), retry later."""
    global wifi
    _radio_off()
    wifi = FAILED


def _radio_off():
    global _wlan
    if _wlan is not None:
        try:
            _wlan.disconnect()
        except Exception:
            pass
        try:
            _wlan.active(False)
        except Exception:
            pass
        _wlan = None
    power.radio(False)


def _poll_wifi():
    global wifi, _wifi_at
    now = badge.ticks
    if now - _wifi_at < WIFI_POLL_MS:
        return
    _wifi_at = now
    if _wlan is None:
        first = wifi == OFF and now - _started >= WIFI_START_MS
        retry = wifi == FAILED and now - _attempt_at >= WIFI_RETRY_MS
        if first or retry:
            _connect()
        return
    try:
        if _wlan.isconnected():
            wifi = ONLINE
        elif _wlan.status() < 0 or now - _attempt_at > WIFI_TIMEOUT_MS:
            _give_up()
        else:
            wifi = CONNECTING
    except Exception:
        _give_up()


def _sync_clock():
    # Mirrors Pimoroni's clock app: NTP gives UTC, the DST policy for REGION
    # turns it into local time, and that goes into both RTCs.
    global _synced
    _synced = True                     # one try per boot, whatever happens
    try:
        import machine
        import ntptime
        ntptime.settime()
        tz_minutes = int(float(TIMEZONE) * 60)
        utc = time.mktime(time.gmtime())
        region = REGIONS.get(str(REGION).lower())
        if region:
            from daylightsaving import DaylightSavingPolicy, DaylightSaving
            hem, wk_in, mo_in, wd_in, hr_in, wk_out, mo_out, wd_out, hr_out, shift = region
            dst = DaylightSaving(
                DaylightSavingPolicy(hem, wk_in, mo_in, wd_in, hr_in, tz_minutes + shift),
                DaylightSavingPolicy(hem, wk_out, mo_out, wd_out, hr_out, tz_minutes))
            local = dst.localtime(utc)
        else:
            local = utc + tz_minutes * 60
        tm = time.gmtime(local)
        machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0))
        rtc.datetime((tm[0], tm[1], tm[2], tm[3], tm[4], tm[5], tm[6]))
    except Exception:
        pass


def update():
    if _battery_at is None or badge.ticks - _battery_at >= BATTERY_EVERY_MS:
        _read_battery()
    if SSID and not disabled:
        _poll_wifi()
        if wifi == ONLINE and not _synced and time.localtime()[0] < 2025:
            _sync_clock()


def clock():
    """"HH:MM" once the RTC holds a real time, else None."""
    t = time.localtime()
    if t[0] < 2025:
        return None
    return "{:02d}:{:02d}".format(t[3], t[4])


def wifi_off():
    """Power the radio down before an app runs; apps that need WiFi connect themselves."""
    global wifi
    _radio_off()
    wifi = OFF
