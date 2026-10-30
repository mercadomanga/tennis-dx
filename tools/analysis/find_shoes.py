#!/usr/bin/env python3
"""Finds the players' transparent shoe pixels.

The shoes are outlined in black with a transparent inside, so the grass
shows through. Same method as find_eyes.py (play at random, put each
player's sprites together on a canvas, flood-fill from outside), but the
transparent pixels the fill cannot reach that are small and sit in the
lowest rows (the last five) of the figure are the shoes.

    find_shoes.py baserom.gb SEED FRAMES [OUT.json]

Writes {"screen tile obp": [[row, col, hits, seen], ...]} (default OUT:
shoes.json). Results of several seeds were merged into tools/data/shoes.json.
The method also catches the gap between the legs (seen from the front and
from behind); it was removed by hand from tools/data/shoes.json and stays
transparent. The inside of the shoe of the leg in the back, larger than five
rows, was added by hand after checking every pose (tools/poses.py), and so was
the foot of the pose that bounces the ball before serving ($4F, like $63).
Needs pyboy."""
import json
import random
import sys
from collections import defaultdict

from pyboy import PyBoy

W, H = 40, 48                        # canvas for one player
NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))
NOT_PLAYERS = (0x31, 0x37, 0x38, 0x2F, 0x22)    # ball, shadow, ...


def main(rom, seed, frames, out='shoes.json'):
    pb = PyBoy(rom, window='null', sound_emulated=False)
    m = pb.memory
    pb.set_emulation_speed(0)
    random.seed(seed)
    hole = defaultdict(int)
    seen = defaultdict(int)

    def tile_pixels(t):
        a = 0x8000 + t * 16
        return [[((m[a + 2 * y] >> (7 - x)) & 1) | (((m[a + 2 * y + 1] >> (7 - x)) & 1) << 1)
                 for x in range(8)] for y in range(8)]

    def compose(sprites, y0, x0, screen, pal):
        """Colour and owner (screen, tile, palette, row, col) of every canvas pixel."""
        colour = [[-1] * W for _ in range(H)]
        owner = [[None] * W for _ in range(H)]
        for y, x, t, attr in sprites:
            pix = tile_pixels(t)
            for py in range(8):
                for px in range(8):
                    sx = 7 - px if attr & 0x20 else px
                    sy = 7 - py if attr & 0x40 else py
                    cy, cx = y - y0 + py, x - x0 + px
                    if 0 <= cy < H and 0 <= cx < W:
                        c = pix[sy][sx]
                        if c or colour[cy][cx] < 0:
                            colour[cy][cx] = c
                            owner[cy][cx] = (screen, t, pal, sy, sx)
        return colour, owner

    def flood(colour, start, blocked):
        reached = [[False] * W for _ in range(H)]
        stack = list(start)
        while stack:
            cy, cx = stack.pop()
            if not (0 <= cy < H and 0 <= cx < W) or reached[cy][cx] or blocked(cy, cx):
                continue
            reached[cy][cx] = True
            stack += [(cy + dy, cx + dx) for dy, dx in NEIGHBOURS]
        return reached

    for f in range(frames):
        if f % 40 == 0:
            if f < 2000 or random.random() < 0.02:
                pb.button('start', 3)
            else:
                pb.button(random.choice(['a', 'a', 'b', 'left', 'right', 'up', 'down']), random.randint(2, 15))
        pb.tick(1, render=False)
        if f % 6 or not (m[0xFF40] & 0x80):
            continue
        screen = 'court' if m[0x9800] == 0x82 else ('board' if m[0x9800] < 0x80 else None)
        if not screen:
            continue
        oam = [(m[0xFE00 + i], m[0xFE01 + i], m[0xFE02 + i], m[0xFE03 + i]) for i in range(0, 160, 4)
               if m[0xFE00 + i] and m[0xFE02 + i] < 0x80]
        for pal in (0, 0x10):                       # the two players use different palettes
            player = [s for s in oam if (s[3] & 0x10) == pal and s[2] not in NOT_PLAYERS]
            if len(player) < 3:
                continue
            y0 = min(s[0] for s in player) - 1
            x0 = min(s[1] for s in player) - 1
            colour, owner = compose(player, y0, x0, screen, pal)
            outside = flood(colour, [(0, 0)], lambda cy, cx: colour[cy][cx] > 0)
            done = set()
            figure_height = max(s[0] for s in player) - y0 + 8
            for cy in range(H):
                for cx in range(W):
                    if colour[cy][cx] != 0 or outside[cy][cx] or (cy, cx) in done:
                        continue
                    comp, stack = [], [(cy, cx)]
                    while stack:
                        a, b = stack.pop()
                        if (a, b) in done or not (0 <= a < H and 0 <= b < W) or colour[a][b] != 0 or outside[a][b]:
                            continue
                        done.add((a, b))
                        comp.append((a, b))
                        stack += [(a + da, b + db) for da, db in NEIGHBOURS]
                    if len(comp) <= 8 and min(a for a, b in comp) >= figure_height - 5:
                        for a, b in comp:
                            hole[owner[a][b]] += 1
            for cy in range(H):
                for cx in range(W):
                    if colour[cy][cx] == 0 and owner[cy][cx]:
                        seen[owner[cy][cx]] += 1
    shoes = defaultdict(list)
    for k, v in hole.items():
        if v >= 3 and v / seen[k] > 0.8:
            shoes['%s %02x %d' % (k[0], k[1], k[2])].append((k[3], k[4], v, seen[k]))
    for k in sorted(shoes):
        print(k, sorted(shoes[k]))
    with open(out, 'w') as fh:
        json.dump(shoes, fh)
    pb.stop(False)


if __name__ == '__main__':
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), *sys.argv[4:5])
