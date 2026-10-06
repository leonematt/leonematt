# Matrix rain of hex bytes (00-FF) for the menu background.
#
# Each step washes the whole layer with translucent black, so everything
# already drawn fades a little, then each drop moves its bright head down and
# leaves green bytes where it was. The fading is what draws the trails, so a
# step costs one fill plus a few dozen glyphs.
#
# Timing comes from the power mode (lib/power.py): how long a step is, how many
# rows a drop falls per step (fractions are fine), how much it fades per step,
# and how often a new drop starts.

import random

FONT = font.match           # 7px-tall bitmap font on a 12px line
COL_W = 18                  # column pitch in pixels (17 columns at 320 wide)
GLITCH_EVERY_MS = 500       # how often a trail byte flips to a new value
HEAD = (205, 255, 215)      # leading byte, nearly white
TRAIL = (20, 235, 80)       # the trail it leaves behind


class Rain:
    def __init__(self, width, height, step_ms=1000, speeds=(1, 2, 2), fade=90, spawn_ms=2000):
        layer = image(width, height)
        layer.font = FONT
        layer.pen = color.black
        layer.clear()
        self.layer = layer
        self.w, self.h = width, height
        self.step_ms = step_ms
        self.speeds = speeds
        self.cell_h = FONT.height
        self.cols = width // COL_W
        self.rows = (height + self.cell_h - 1) // self.cell_h
        self.x0 = (width - self.cols * COL_W) // 2
        self.wash = color.rgb(0, 0, 0, fade)
        self.black = color.black
        self.head = color.rgb(*HEAD)

        # trail pen after n washes, using the same integer blend as the
        # renderer, so a byte that flips mid-trail matches its neighbours
        keep = 255 - fade
        rgb = list(TRAIL)
        self.aged = []
        for _ in range(64):
            self.aged.append(color.rgb(*rgb))
            rgb = [(v * keep + 128) >> 8 for v in rgb]

        # The integer fade never quite reaches black: it stalls a few levels
        # above it. Count the steps until it stalls; that long after a drop
        # ends, its column is wiped so faint ghosts don't build up.
        rgb, prev, self.fade_steps = list(HEAD), None, 0
        while rgb != prev:
            prev, rgb = rgb, [(v * keep + 128) >> 8 for v in rgb]
            self.fade_steps += 1

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
        self.row = [None] * n     # row of the head; None = no drop in this column
        self.speed = [1] * n      # rows per step for the current drop
        self.fall = [0.0] * n     # fractional rows waiting to be fallen
        self.glyph = [0] * n      # byte under the head
        self.wipe_in = [0] * n    # steps until an empty column is wiped (0 = nothing to wipe)
        self.spawn_every = max(1, spawn_ms // step_ms)
        self.spawn_in = 0
        self.glitch_every = max(1, GLITCH_EVERY_MS // step_ms)
        self.glitch_in = 0

        # pre-roll about 40 rows' worth of falling so the first frame has rain
        for _ in range(int(40 / (sum(speeds) / len(speeds)))):
            self.step()
        self.last = badge.ticks

    def spawn(self):
        """Start a drop at the top of a random empty column."""
        free = [i for i in range(self.cols) if self.row[i] is None]
        if free:
            i = free[random.randint(0, len(free) - 1)]
            self.row[i] = -1
            self.speed[i] = self.speeds[random.randint(0, len(self.speeds) - 1)]
            self.fall[i] = 1.0                    # first row appears straight away
            self.wipe_in[i] = 0                   # the new drop repaints the whole column anyway

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

        self.spawn_in -= 1
        if self.spawn_in <= 0:
            self.spawn()
            self.spawn_in = self.spawn_every

        rows = self.rows
        for i in range(self.cols):
            r = self.row[i]
            if r is None:
                if self.wipe_in[i]:
                    self.wipe_in[i] -= 1
                    if not self.wipe_in[i]:
                        layer.pen = self.black
                        layer.rectangle(self.x0 + i * COL_W, 0, COL_W, self.h)
                continue
            self.fall[i] += self.speed[i]
            moves = int(self.fall[i])
            self.fall[i] -= moves
            for _ in range(moves):
                if r >= 0:
                    self.cell(i, r, self.glyph[i], self.aged[0])   # old head joins the trail
                r += 1
                if r >= rows:
                    break
                b = random.getrandbits(8)
                self.cell(i, r, b, self.head)
                self.glyph[i] = b
            if r >= rows:
                self.row[i] = None                              # drop finished
                self.wipe_in[i] = self.fade_steps + 2
            else:
                self.row[i] = r

        # now and then a byte a little way up a trail flips to a new value
        self.glitch_in -= 1
        if self.glitch_in <= 0:
            self.glitch_in = self.glitch_every
            i = random.randint(0, self.cols - 1)
            if self.row[i] is not None:
                k = random.randint(2, 6)                  # rows above the head
                r = self.row[i] - k
                age = int((k - 1) / self.speed[i])       # steps since that byte was the head
                if r >= 0 and age < len(self.aged):
                    self.cell(i, r, random.getrandbits(8), self.aged[age])

    def advance(self):
        """Run however many steps are due; True if the layer changed."""
        now = badge.ticks
        steps = 0
        while now - self.last >= self.step_ms and steps < 3:
            self.step()
            self.last += self.step_ms
            steps += 1
        if now - self.last >= self.step_ms:          # fell behind: don't try to catch up
            self.last = now
        return steps > 0
