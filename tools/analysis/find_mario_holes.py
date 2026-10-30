#!/usr/bin/env python3
"""Finds the transparent pixels enclosed by Mario's body on the court.

Mario (the umpire) is made of BG tiles, and a few pixels inside him are
colour 0 (they show the grass colour). gen_data.py needs to know which ones
so that his red shirt overlay does not paint over them.

    find_mario_holes.py baserom.gb [OUT.json]

Plays at random and, for every different arrangement of Mario's tiles on the
map, flood-fills from the edge of his 2 x 5 tile block. Pixels of colour 0
that the fill never reaches, in every arrangement, are written as
{"tile": [[row, col], ...]} (default OUT: mario_holes.json). Needs pyboy."""
import json
import random
import sys
from collections import defaultdict

from pyboy import PyBoy

W, H = 16, 40                          # Mario's block: 2 x 5 tiles


def main(rom, out='mario_holes.json'):
    pb = PyBoy(rom, window='null', sound_emulated=False)
    m = pb.memory
    pb.set_emulation_speed(0)
    random.seed(4)

    def pixel(t, y, x):
        a = 0x9000 + ((t ^ 0x80) - 0x80) * 16          # signed tile numbers
        return ((m[a + 2 * y] >> (7 - x)) & 1) | (((m[a + 2 * y + 1] >> (7 - x)) & 1) << 1)

    inside = defaultdict(int)
    total = defaultdict(int)
    combos = set()
    for f in range(150000):
        if f % 40 == 0:
            if f < 2000 or random.random() < 0.02:
                pb.button('start', 3)
            else:
                pb.button(random.choice(['a', 'a', 'b', 'left', 'right', 'up', 'down']), random.randint(2, 15))
        pb.tick(1, render=False)
        if f % 30 or m[0x9800] != 0x82 or not m[0xFF40] & 0x80:
            continue
        for col in (3, 22):                          # the chair stands on either side
            block = [[m[0x9800 + r * 32 + col + c] for c in range(2)] for r in range(11, 16)]
            if block[0][0] == 0x80 and block[1][0] == 0x80:
                continue                             # nobody there
            key = tuple(map(tuple, block))
            if key in combos:
                continue
            combos.add(key)
            colour = [[pixel(block[r // 8][c // 8], r % 8, c % 8) for c in range(W)] for r in range(H)]
            outside = [[False] * W for _ in range(H)]
            stack = ([(r, c) for r in range(H) for c in (0, W - 1)]
                     + [(r, c) for c in range(W) for r in (0, H - 1)])
            while stack:
                r, c = stack.pop()
                if not (0 <= r < H and 0 <= c < W) or outside[r][c] or colour[r][c] != 0:
                    continue
                outside[r][c] = True
                stack += [(r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)]
            for r in range(8, 24):                   # map rows 12-13
                for c in range(W):
                    if colour[r][c] == 0:
                        t = block[r // 8][c // 8]
                        total[(t, r % 8, c % 8)] += 1
                        if not outside[r][c]:
                            inside[(t, r % 8, c % 8)] += 1
    print(len(combos), 'arrangements')
    holes = defaultdict(list)
    for k, v in inside.items():
        if v == total[k]:                            # enclosed in every arrangement
            holes['%02x' % k[0]].append((k[1], k[2]))
    with open(out, 'w') as fh:
        json.dump(holes, fh)
    for t in sorted(holes):
        print(t, sorted(holes[t]))
    pb.stop(False)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], *sys.argv[2:3])
