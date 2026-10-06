# Drawing for the menu: top status bar (prompt, clock, WiFi, battery) and the
# shared terminal-green palette.

import status

PROMPT = "leonematt@tufty:~$"   # shown top left; change to taste

BAR_H = 22
GREEN = color.rgb(40, 255, 110)
GREEN_DIM = color.rgb(0, 150, 60)
GREEN_FAINT = color.rgb(0, 90, 38)
AMBER = color.rgb(255, 176, 0)
RED = color.rgb(255, 70, 50)
GREY = color.rgb(70, 80, 74)
BAR_BG = color.rgb(0, 0, 0, 215)

TEXT_FONT = font.match


def _wifi_icon(x, y, state):
    # fan of three arcs plus a dot; (x, y) is the bottom centre
    if state == status.ONLINE:
        lit, pen = 3, GREEN
    elif state == status.CONNECTING:
        lit, pen = (badge.ticks // 1000) % 4, GREEN_DIM    # sweeps up while joining
    else:
        lit, pen = 0, GREY
    screen.pen = pen if state in (status.ONLINE, status.CONNECTING) else GREY
    screen.shape(shape.circle(x, y - 1, 1.6))
    for i, (inner, outer) in enumerate(((3.5, 5.5), (7.0, 9.0), (10.5, 12.5))):
        screen.pen = pen if i < lit else GREY
        screen.shape(shape.arc(x, y, inner, outer, -45, 45))
    if state in (status.OFF, status.FAILED):            # slash = disconnected
        screen.pen = color.black
        screen.shape(shape.line(x - 8, y - 12, x + 8, y + 1, 4))
        screen.pen = RED
        screen.shape(shape.line(x - 8, y - 12, x + 8, y + 1, 1.6))


def _battery_icon(x, y):
    # 22x11 outline with a nub; (x, y) is the top left. Returns (label, low).
    level = status.battery
    lvl = 0 if level is None else level
    low = level is not None and level < 20 and not status.usb
    screen.pen = RED if low else GREEN
    screen.rectangle(x, y, 22, 11)
    screen.rectangle(x + 22, y + 3, 2, 5)
    screen.pen = color.black
    screen.rectangle(x + 1, y + 1, 20, 9)
    fill = max(1, 18 * lvl // 100)
    if status.charging:                               # fill sweeps while charging
        fill = max(fill, 18 * ((badge.ticks // 1000) % 5) // 4)
    screen.pen = RED if low else GREEN
    screen.rectangle(x + 2, y + 2, fill, 7)
    if status.usb and not status.charging and level is not None and level >= 99:
        return "USB", low
    return ("--%" if level is None else "{}%".format(level)), low


def draw_status_bar():
    w = screen.width
    screen.pen = BAR_BG
    screen.rectangle(0, 0, w, BAR_H)
    screen.pen = GREEN_FAINT
    screen.rectangle(0, BAR_H, w, 1)

    screen.font = TEXT_FONT
    screen.pen = GREEN
    screen.text(PROMPT, 6, 5)
    if (badge.ticks // 1000) % 2 == 0:                # blinking block cursor
        pw, _ = screen.measure_text(PROMPT)
        screen.rectangle(6 + int(pw) + 3, 7, 6, 9)

    # right side, laid out right to left: battery %, battery, WiFi, clock
    x = w - 6
    label, low = _battery_icon(x - 24, 6)
    lw, _ = screen.measure_text(label)
    x -= 24 + 4 + int(lw)
    screen.pen = RED if low else (GREEN_DIM if status.battery is not None else GREY)
    screen.text(label, x, 5)

    x -= 18
    _wifi_icon(x, 17, status.wifi)

    clock = status.clock()
    if clock:
        cw, _ = screen.measure_text(clock)
        x -= 16 + int(cw)
        screen.pen = GREEN_DIM
        screen.text(clock, x, 5)
