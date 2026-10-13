# Matrix rain of hex bytes (00-FF) for the menu background.
#
# Each step washes the whole layer with translucent black, so everything
# already drawn fades a little, then each column whose drop is due moves its
# bright head one row down and leaves a green byte where it was. The fading is
# what draws the trails, so a step costs one fill plus a few dozen glyphs.

import random

FONT = font.match           # 7px-tall bitmap font on a 12px line
COL_W = 18                  # column pitch in pixels (17 columns at 320 wide)
STEP_MS = 33                # one simulation step (~30 a second)
FADE = 22                   # black wash per step, 0-255: higher = shorter trails
SPEEDS = (2, 2, 3, 3, 3, 4, 5)   # steps per row, picked at random for each drop
GAP = (4, 30)               # steps a column rests between drops (min, max)
GLITCH = 2                  # trail bytes that flip to a new value each step
HEAD = (205, 255, 215)      # leading byte, nearly white
TRAIL = (20, 235, 80)       # the trail it leaves behind


class Rain:
    def __init__(self, width, height):
        layer = image(width, height)
        layer.font = FONT
        layer.pen = color.black
        layer.clear()
        self.layer = layer
        self.w, self.h = width, height
        self.cell_h = FONT.height
        self.cols = width // COL_W
        self.rows = (height + self.cell_h - 1) // self.cell_h
        self.x0 = (width - self.cols * COL_W) // 2
        self.wash = color.rgb(0, 0, 0, FADE)
        self.black = color.black
        self.head = color.rgb(*HEAD)

        # trail pen after n washes, using the same integer blend as the
        # renderer, so a byte that flips mid-trail matches its neighbours
        keep = 255 - FADE
        rgb = list(TRAIL)
        self.aged = []
        for _ in range(48):
            self.aged.append(color.rgb(*rgb))
            rgb = [(v * keep + 128) >> 8 for v in rgb]

        # all 256 bytes as text, each centred in its column; measure_text
        # counts 1px of spacing after every digit, so a pair is one px narrower
        digits = "0123456789ABCDEF"
        width = [int(layer.measure_text(d)[0]) for d in digits]
        self.text = []
        self.dx = []
        for b in range(256):
            hi, lo = b >> 4, b & 15
            self.text.append(digits[hi] + digits[lo])
            self.dx.append(max(0, (COL_W - (width[hi] + width[lo] - 1)) // 2))

        n = self.cols
        self.row = [-1] * n       # row of the head, -1 while waiting to start
        self.speed = [3] * n      # steps per row for the current drop
        self.wait = [0] * n       # steps until the column next moves
        self.glyph = [0] * n      # byte under the head
        for i in range(n):
            self.spawn(i, random.randint(0, self.rows * 2))

        for _ in range(90):       # pre-roll so the first frame is already raining
            self.step()
        self.last = badge.ticks

    def spawn(self, i, delay):
        self.row[i] = -1
        self.speed[i] = SPEEDS[random.randint(0, len(SPEEDS) - 1)]
        self.wait[i] = delay

    def cell(self, i, r, b, pen):
        layer = self.layer
        x = self.x0 + i * COL_W
        y = r * self.cell_h
        layer.pen = self.black                      # wipe whatever faded byte was here
        layer.rectangle(x, y, COL_W, self.cell_h)
        layer.pen = pen
        layer.text(self.text[b], x + self.dx[b], y)

    def step(self):
        layer = self.layer
        layer.pen = self.wash
        layer.rectangle(0, 0, self.w, self.h)
        rows = self.rows
        for i in range(self.cols):
            if self.wait[i]:
                self.wait[i] -= 1
                continue
            r = self.row[i]
            if r >= 0:
                self.cell(i, r, self.glyph[i], self.aged[0])   # old head joins the trail
            r += 1
            if r >= rows:
                self.spawn(i, random.randint(GAP[0], GAP[1]))
                continue
            b = random.getrandbits(8)
            self.cell(i, r, b, self.head)
            self.glyph[i] = b
            self.row[i] = r
            self.wait[i] = self.speed[i] - 1

        # a few bytes a little way up the trails flip to a new value
        for _ in range(GLITCH):
            i = random.randint(0, self.cols - 1)
            k = random.randint(2, 6)                  # rows above the head
            r = self.row[i] - k
            if r < 0:
                continue
            age = (k - 1) * self.speed[i] + self.speed[i] - 1 - self.wait[i]
            if age < len(self.aged):
                self.cell(i, r, random.getrandbits(8), self.aged[age])

    def advance(self):
        """Run however many steps are due; True if the layer changed."""
        now = badge.ticks
        steps = 0
        while now - self.last >= STEP_MS and steps < 3:
            self.step()
            self.last += STEP_MS
            steps += 1
        if now - self.last >= STEP_MS:          # fell behind: don't try to catch up
            self.last = now
        return steps > 0
