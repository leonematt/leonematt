# Power modes shared by the menu and the apps.
#
# The Settings app saves the chosen mode (State "settings"); the menu and each
# app read it when they start and call apply(). Import it with:
#
#     import sys
#     if "/system/lib" not in sys.path:
#         sys.path.append("/system/lib")
#     import power
#
# Nothing here keeps running in the background: a mode is just a few numbers
# the apps use for screen refresh, brightness and the menu's rain.

import machine

MODES = ("performance", "balanced", "saver")
DEFAULT = "balanced"

NAMES = {"performance": "Performance", "balanced": "Balanced", "saver": "Power saver"}

PROFILES = {
    # idle_hz:   always None (full speed). Kept for older app code; the clock
    #            is never changed, see FULL_HZ below.
    # panel_hz:  how often the LCD refreshes itself from its own memory
    # backlight: 0-1
    # rain:      the menu background: seconds per step, rows per step for
    #            each drop, fade per step (0-255), how often a new drop starts
    "performance": {
        "idle_hz": None, "panel_hz": 90, "backlight": 0.9,
        "rain": {"step_ms": 50, "speeds": (0.3, 0.4, 0.5), "fade": 22, "spawn_ms": 500},
        "about": "Smooth 20 fps rain, 90 Hz screen, 90% bright",
    },
    "balanced": {
        "idle_hz": None, "panel_hz": 60, "backlight": 0.7,
        "rain": {"step_ms": 250, "speeds": (1, 1, 2), "fade": 50, "spawn_ms": 1000},
        "about": "Rain at 4 fps, 60 Hz screen, 70% bright",
    },
    "saver": {
        "idle_hz": None, "panel_hz": 60, "backlight": 0.45,
        "rain": {"step_ms": 1000, "speeds": (1, 2, 2), "fade": 90, "spawn_ms": 2000},
        "about": "Rain at 1 fps, 60 Hz screen, 45% bright",
    },
}

# The CPU stays at the firmware's own speed (250 MHz). Nothing here calls
# machine.freq(): every clock change re-tunes the flash and PSRAM timing on
# the fly, and doing that between frames is what locked the badge up.
FULL_HZ = machine.freq()


def mode():
    """The saved mode name (DEFAULT if none saved yet)."""
    s = {"power": DEFAULT}
    try:
        State.load("settings", s)
    except Exception:
        pass
    return s["power"] if s.get("power") in PROFILES else DEFAULT


def save(name):
    s = {"power": DEFAULT}
    try:
        State.load("settings", s)
    except Exception:
        pass
    s["power"] = name
    State.save("settings", s)


def profile(name=None):
    return PROFILES[name or mode()]


_radio = False


def radio(on):
    """Apps call radio(True) before turning WiFi on and radio(False) after.

    Only records the state now; kept so apps written against it still work.
    """
    global _radio
    _radio = on


def cpu(hz):
    """Deliberately does nothing: the CPU clock is never changed (see FULL_HZ).

    Kept so apps that call cpu(...) still work.
    """
    return None


def apply(name=None, backlight=True):
    """Set the screen up for a mode; returns its profile."""
    p = profile(name)
    try:
        display.set_framerate(p["panel_hz"])
    except Exception:
        pass
    if backlight:
        try:
            display.backlight(p["backlight"])
        except Exception:
            pass
    return p
