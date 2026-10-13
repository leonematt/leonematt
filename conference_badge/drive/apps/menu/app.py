# App discovery and the icon grid. Every folder in /system/apps with an
# __init__.py (except this menu) is an app; the folder name is its label
# (my_app -> "My App") and an optional 24x24 icon.png is its icon.

import os
import math

import ui

DEFAULT_ICON = image.load("default_icon.png")

COLS, ROWS = 3, 2
PER_PAGE = COLS * ROWS
TILE = 64                     # tile size in pixels
PITCH_X, PITCH_Y = 88, 76     # tile centre spacing
GRID_X, GRID_Y = 72, 72       # centre of the top-left tile
ICON = 48                     # 24x24 icons drawn at 2x

TILE_BG = color.rgb(0, 0, 0, 215)
EDGE = color.rgb(0, 110, 45)
GLOW = color.rgb(40, 255, 110, 45)
LABEL_BG = color.rgb(0, 0, 0, 225)

LABEL_FONT = font.absolute


class App:
    def __init__(self, collection, name, path):
        self.index = len(collection)
        slot = self.index % PER_PAGE
        self.cx = GRID_X + (slot % COLS) * PITCH_X
        self.cy = GRID_Y + (slot // COLS) * PITCH_Y
        x, y = self.cx - TILE // 2, self.cy - TILE // 2
        # shapes are fixed per slot, so build them once
        self.glow = shape.rounded_rectangle(x - 4, y - 4, TILE + 8, TILE + 8, 14)
        self.body = shape.rounded_rectangle(x, y, TILE, TILE, 10)
        self.edge = shape.rounded_rectangle(x, y, TILE, TILE, 10).stroke(1)
        self.edge_on = shape.rounded_rectangle(x, y, TILE, TILE, 10).stroke(2)
        self.icon = image.load(f"{path}/icon.png") if file_exists(f"{path}/icon.png") else DEFAULT_ICON
        self.name = name
        self.path = path
        self.active = False
        collection.append(self)

    def draw(self):
        if self.active:
            screen.pen = GLOW
            screen.shape(self.glow)
        screen.pen = TILE_BG
        screen.shape(self.body)
        screen.pen = ui.GREEN if self.active else EDGE
        screen.shape(self.edge_on if self.active else self.edge)
        self.icon.alpha = 255 if self.active else 110
        screen.blit(self.icon, rect(self.cx - ICON // 2, self.cy - ICON // 2, ICON, ICON))


class Apps:
    def __init__(self, root):
        self.apps = []
        self.active_index = 0

        def capitalize(word):
            if len(word) <= 1:
                return word
            return word[0].upper() + word[1:]

        for path in sorted(os.listdir(root)):
            if path == "menu" or path.startswith("."):
                continue
            full = f"{root}/{path}"
            if is_dir(full) and (file_exists(f"{full}/__init__.py") or file_exists(f"{full}/__init__.mpy")):
                App(self.apps, " ".join([capitalize(w) for w in path.split("_")]), full)

    @property
    def active(self):
        return self.apps[self.active_index]

    def activate(self, index):
        self.active_index = index
        for app in self.apps:
            app.active = app.index == index

    def draw_icons(self):
        offset = (self.active_index // PER_PAGE) * PER_PAGE
        for app in self.apps[offset:offset + PER_PAGE]:
            app.draw()

    def draw_label(self, y=200):
        screen.font = LABEL_FONT
        if self.apps:
            label = "> " + self.active.name
        else:
            label = "> no apps installed"
        w, h = screen.measure_text(label)
        cw = 9                                        # room for the blinking cursor
        bw = int(w) + cw + 16
        x = (screen.width - bw) // 2
        screen.pen = LABEL_BG
        screen.shape(shape.rounded_rectangle(x, y, bw, 24, 6))
        screen.pen = ui.GREEN_FAINT
        screen.shape(shape.rounded_rectangle(x, y, bw, 24, 6).stroke(1))
        screen.pen = ui.GREEN
        screen.text(label, x + 8, y + 4)
        if (badge.ticks // 500) % 2 == 0:
            screen.rectangle(x + 8 + int(w) + 1, y + 5, cw - 2, int(h) - 2)

    def draw_pagination(self, x=306):
        pages = math.ceil(len(self.apps) / PER_PAGE)
        if pages < 2:
            return
        current = self.active_index // PER_PAGE
        y = 110 - pages * 6
        for page in range(pages):
            screen.pen = ui.GREEN if page == current else ui.GREEN_FAINT
            screen.rectangle(x, y + page * 12, 6, 6)

    def __len__(self):
        return len(self.apps)

    def __getitem__(self, i):
        return self.apps[i]
