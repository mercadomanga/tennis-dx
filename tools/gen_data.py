#!/usr/bin/env python3
"""Builds src data for Tennis DX: per-screen palettes, tile tables, the
pixel-level fixes (white eyes, Mario's overlays) and the court surfaces.

Usage: gen_data.py OUT.inc [VRAMDIR]

Inputs:
  VRAMDIR (default build/vram), made by dump_vram.py from your own copy of
  the game; the graphics of the original are not kept with the source:
    spr_court.bin, spr_board.bin  VRAM $8000-$87FF (sprite tiles) on each screen
    bg_court.bin,  bg_board.bin   VRAM $8800-$97FF (BG tiles) on each screen
    map_court.bin                 the court's BG map (what is inside or outside the
                                  lines, for the surfaces; where the crowd sits)
  tools/data/ (only coordinates, no graphics):
    eyes.json         transparent "eye" pixels found by analysis/find_eyes.py:
                      "screen tile obp" -> [(row, col), ...]
    shoes.json        the same for the shoes (analysis/find_shoes.py)
    mario_holes.json  transparent pixels inside Mario's body on the court
                      (analysis/find_mario_holes.py)
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from palettes import SCREENS, menu, board, court, CARD_OBJ_PAL, PLAYER_SKIN, SHIRT_RED   # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), '..')
DATA = os.path.join(ROOT, 'tools', 'data')
VRAM = os.path.join(ROOT, 'build', 'vram')
if __name__ == '__main__' and len(sys.argv) > 2:
    VRAM = sys.argv[2]


def load(name, mode='rb'):
    """Coordinates come from tools/data, tile snapshots from the VRAM folder."""
    folder = DATA if name.endswith('.json') else VRAM
    with open(os.path.join(folder, name), mode) as f:
        return f.read() if 'b' in mode else json.load(f)


def rgb555(h):
    r, g, b = (int(h.lstrip('#')[i:i + 2], 16) >> 3 for i in (0, 2, 4))
    v = r | (g << 5) | (b << 10)
    return [v & 0xFF, v >> 8]


class Tiles:
    """2bpp tile data with GB tile numbering (sprites unsigned, BG signed)."""

    def __init__(self, data, signed):
        self.data, self.signed = data, signed

    def offset(self, t):
        if self.signed:                          # data = $8800-$97FF
            return (t - 0x80) * 16 if t >= 0x80 else 0x800 + t * 16
        return t * 16                            # data = $8000-$87FF

    def px(self, t, y, x):
        a = self.offset(t) + 2 * y
        return ((self.data[a] >> (7 - x)) & 1) | (((self.data[a + 1] >> (7 - x)) & 1) << 1)

    def pixels(self, t, colour):
        return {(y, x) for y in range(8) for x in range(8) if self.px(t, y, x) == colour}


def masks(pixels):
    """{(row, col)} -> {row: bitmask}"""
    out = defaultdict(int)
    for y, x in pixels:
        out[y] |= 0x80 >> x
    return out


def flood(grid, seeds, passable):
    h, w = len(grid), len(grid[0])
    seen, stack = set(), list(seeds)
    while stack:
        r, c = stack.pop()
        if (r, c) in seen or not (0 <= r < h and 0 <= c < w) or not passable(r, c):
            continue
        seen.add((r, c))
        stack += [(r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)]
    return seen


def border(h, w):
    return [(r, c) for r in range(h) for c in (0, w - 1)] + [(r, c) for c in range(w) for r in (0, h - 1)]


# Every screen gets:
#   attr tables (bg, obj0, obj1), palettes, rects,
#   spr_patches / bg_patches: {(tile, row): [low mask, high mask]} XORed into sprite tiles
#   (only if the tile holds the drawing they were made for) / ORed into BG tiles,
#   overlays: [(BG tile, sprite slot, OAM attribute, 16 bytes)], ovl_mode
for s in SCREENS:
    s.spr_patches = defaultdict(lambda: [0, 0])
    s.bg_patches = defaultdict(lambda: [0, 0])
    s.overlays, s.ovl_mode = [], 0


# ------------------------------------------------------------- white eyes
# The players' eyes are transparent pixels, so the grass showed through.
# A copy of the sprite tiles in VRAM bank 1 gets those pixels filled, and
# the tables point the tile at bank 1 (attribute bit 3).
eyes = load('eyes.json', 'r')
eyes['board 37 16'] = [(5, 3), (5, 4), (6, 3), (6, 4), (7, 4)]   # CPU walking in profile
eyes['court 6e 0'] = [(0, 3)]                                     # serve, bouncing the ball
HEAD_PAL = {'court': 1, 'board': 3}               # sprite palette whose colour 2 is white
WHITE_C2 = {'court': {0: (1,), 1: (1,)}, 'board': {0: (3,), 1: (1,)}}

for scr in (court, board):
    key = scr.name.lower()
    spr = Tiles(load(f'spr_{key}.bin'), signed=False)
    target = {}                                     # tile -> colour the eye pixels get
    for k, pix in eyes.items():
        name, t, obp = k.split()
        if name != key:
            continue
        t = int(t, 16)
        # colour 2 is the shirt in shirt tiles: the player's is red, so those
        # eye pixels take skin (1); everywhere else colour 2 can be white
        tg = 1 if (obp == '0' and spr.pixels(t, 2)) else 2
        target[t] = min(target.get(t, 2), tg)
        for row, col, *_ in pix:
            scr.spr_patches[(t, row)][0 if target[t] == 1 else 1] |= 0x80 >> col
    # the patched tile is shared by both players: use it wherever colour 2
    # shows as white (or the patch only adds skin)
    for t, tg in target.items():
        for which, table, default in ((0, scr.obj0, scr.obj_default[0]), (1, scr.obj1, scr.obj_default[1])):
            p = table.get(t, default) & 7
            if tg == 1 or p in WHITE_C2[key][which]:
                table[t] = p | 8
            elif not spr.pixels(t, 2) and p in (0, 1):
                table[t] = (HEAD_PAL[key] if which == 0 else 1) | 8


# ------------------------------------------------------------ white shoes
# Shoes are outlined in black with a transparent inside (the grass showed
# through). Their pixels (found by analysis/find_shoes.py) get a white colour:
# colour 2: white on your legs (the colour of your shorts) and blue on the
# opponent's (his shorts: his shoes match them). On the score board both
# players share the tiles of their feet, which colour 2 keeps the same.
shoes = load('shoes.json', 'r')
SHOE_COLOUR = {'court': {0: {1: 2}, 1: {7: 2}}, 'board': {0: {3: 2}, 1: {4: 2}}}   # obp -> palette -> colour

for scr in (court, board):
    key = scr.name.lower()
    for k, pix in shoes.items():
        name, t, obp = k.split()
        if name != key:
            continue
        t, which = int(t, 16), int(obp) // 16
        table, default = (scr.obj0, scr.obj_default[0]) if which == 0 else (scr.obj1, scr.obj_default[1])
        pal = table.get(t, default) & 7
        colour = SHOE_COLOUR[key][which].get(pal)
        if colour is None:
            continue                                # this tile is not drawn in a white-shoe palette
        for row, col, *_ in pix:
            scr.spr_patches[(t, row)][0 if colour == 1 else 1] |= 0x80 >> col
        table[t] = pal | 8

# A lone transparent pixel inside the black of the CPU's sole (found with the same
# play simulation): filled with colour 3 (black) in both bit planes.
for t, row, col in ((0x24, 5, 3),):
    for plane in (0, 1):
        court.spr_patches[(t, row)][plane] |= 0x80 >> col
    court.obj1[t] = (court.obj1.get(t, court.obj_default[1]) & 7) | 8


# Seen from behind, the top rows of your shorts fall in tiles that also hold
# the red shirt and a skin-coloured arm: no room for white there (a sprite
# has three colours), so those rows join the black waistband (colour 2 -> 3).
# (tile: [(row, first col, last col)]); $56 row 6 col 4 is a hole in the band.
WAISTBAND = {0x58: [(6, 5, 7), (7, 4, 7)], 0x59: [(6, 0, 0), (7, 0, 2)],
             0x56: [(7, 5, 7)], 0x57: [(6, 0, 3), (7, 0, 3)]}
for t, runs in WAISTBAND.items():
    for row, c0, c1 in runs:
        for col in range(c0, c1 + 1):
            court.spr_patches[(t, row)][0] |= 0x80 >> col
    court.obj0[t] = (court.obj0.get(t, court.obj_default[0]) & 7) | 8
for plane in (0, 1):
    court.spr_patches[(0x56, 6)][plane] |= 0x80 >> 4

# Your headband is red like your shirt. It is colour 1 (skin) in the original;
# sprite patches are XORed into the bank-1 copy, so they can turn it into
# colour 2 where the palette has the red shirt. The tiles of the face with the
# white of the eye have skin, white and black already: there the band is black
# (profile; it blends into the hair) or stays skin as in the original (the
# face seen from the front on the score board).
BAND_BLACK = {('court', 0x43), ('court', 0x45), ('board', 0x0B)}
headband = load('headband.json', 'r')
for k, pix in headband.items():
    name, t, obp = k.split()
    scr = court if name == 'court' else board
    t, which = int(t, 16), int(obp) // 16
    table, default = (scr.obj0, scr.obj_default[0]) if which == 0 else (scr.obj1, scr.obj_default[1])
    pal = table.get(t, default) & 7
    if scr.obj_pals[pal][1:3] == (PLAYER_SKIN, SHIRT_RED):     # a palette with your shirt
        target = 2
    elif (name, t) in BAND_BLACK:
        target = 3
    else:
        continue
    tiles = Tiles(load(f'spr_{name}.bin'), signed=False)
    for row, col in pix:
        flip = tiles.px(t, row, col) ^ target
        if flip & 1:
            scr.spr_patches[(t, row)][0] ^= 0x80 >> col
        if flip & 2:
            scr.spr_patches[(t, row)][1] ^= 0x80 >> col
    table[t] = pal | 8

# Score board, face seen from the front: the mouth (colour 2, the shirt's
# shade in the original) would be red; it is black.
board.spr_patches[(0x3F, 0)][0] |= 0x80 >> 7
board.obj0[0x3F] = (board.obj0.get(0x3F, board.obj_default[0]) & 7) | 8

# Score board: the red marks of an angry player (tile $09) are black.
for row, col in Tiles(load('spr_board.bin'), signed=False).pixels(0x09, 2):
    board.spr_patches[(0x09, row)][0] |= 0x80 >> col     # colour 2 -> 3
board.obj0[0x09] = (board.obj0.get(0x09, board.obj_default[0]) & 7) | 8

# Score board, sitting on the floor: your shorts and legs (tiles $27-$28) get
# the legs palette; the last row of the shirt above the black waistband in
# $28 has no red there and becomes part of the waistband (colour 2 -> 3).
board.obj0[0x28] = (board.obj0.get(0x28, board.obj_default[0]) & 7) | 8
for col in range(4, 8):
    board.spr_patches[(0x28, 0)][0] |= 0x80 >> col
# ... and the see-through gaps between the spread legs are white (colour 2)
board.obj0[0x27] = (board.obj0.get(0x27, board.obj_default[0]) & 7) | 8
for t, row, col in ((0x27, 1, 6), (0x27, 2, 6), (0x27, 2, 7), (0x27, 3, 7), (0x28, 4, 0), (0x28, 5, 1)):
    board.spr_patches[(t, row)][1] |= 0x80 >> col


def free_sprite_slots(scr):
    """Bank-1 sprite tiles nobody points at (tables without bit 3)."""
    used = {t for table in (scr.obj0, scr.obj1) for t, v in table.items() if v & 8}
    return [t for t in range(0x7F, 0x00, -1) if t not in used]


def tile_bytes(lo_px=(), hi_px=()):
    lo, hi = masks(lo_px), masks(hi_px)
    out = []
    for y in range(8):
        out += [lo[y], hi[y]]
    return out


# ----------------------------------------------------- Mario on the court
# His white shirt is transparent in the original, so grass showed through
# his body. BG: enclosed pixels -> colour 2 (blue overalls, palette 7).
# Sprites on top redraw his original shirt pixels in red.
bgc = Tiles(load('bg_court.bin'), signed=True)
holes = {int(t, 16): [tuple(p) for p in v] for t, v in load('mario_holes.json', 'r').items()}
# Left-side Mario (after changing ends) is a mirror image of the right one.
MIRROR = {0x8F: 0x86, 0x8E: 0x87, 0x93: 0x8A, 0x92: 0x8B, 0x68: 0x35, 0x67: 0x36, 0x66: 0x37, 0x65: 0x38}
for left, right in MIRROR.items():
    holes[left] = [(y, 7 - x) for y, x in holes.get(right, []) if bgc.px(left, y, 7 - x) == 0]
# the one see-through pixel of his eye, by tile (the row of tiles under his head)
EYE = {0x86: (0, 7), 0x35: (0, 5), 0x8F: (0, 0), 0x68: (0, 2)}
SEAT_TILES = (0x37, 0x38, 0x65, 0x66)              # body row resting on the chair seat
SHOULDER_TILES = (0x86, 0x87, 0x8A, 0x8B, 0x35, 0x36, 0x8E, 0x8F, 0x92, 0x93, 0x67, 0x68)
for t, pix in holes.items():
    for y, x in pix:
        if (y, x) == EYE.get(t):
            continue                                    # his eye: white (sprite), not overalls blue
        if y < 7 and not (t in SEAT_TILES and y >= 6) and not (t in SHOULDER_TILES and y >= 5):
            court.bg_patches[(t, y)][1] |= 0x80 >> x
        else:
            # gaps by the seat and between his shoulders and the chair back:
            # black (see-through, they showed the floor, odd off the grass)
            court.bg_patches[(t, y)][0] |= 0x80 >> x
            court.bg_patches[(t, y)][1] |= 0x80 >> x

# Chair-post pixels inside his tiles used colour 2 (now blue) -> outline (3).
POST = {0x36: (6, 7), 0x38: (6, 7), 0x87: (6, 7), 0x8B: (6, 7), 0x67: (0, 1), 0x8E: (0, 1), 0x92: (0, 1), 0x65: (0, 1)}
POST_ALL_ROWS = (0x38, 0x65)
post_px = {t: {(y, x) for y, x in bgc.pixels(t, 2) if x in cols and (y >= 5 or t in POST_ALL_ROWS)}
           for t, cols in POST.items()}
for t in (0x36, 0x38, 0x87, 0x8B, 0x67, 0x8E, 0x92):
    for y, x in post_px[t]:
        court.bg_patches[(t, y)][0] |= 0x80 >> x
for left, right in MIRROR.items():                  # post pixels only the left tiles have
    mirrored = {(y, 7 - x) for y, x in bgc.pixels(right, 2)}
    for y, x in bgc.pixels(left, 2) - mirrored:
        court.bg_patches[(left, y)][0] |= 0x80 >> x


def court_shirt(t):
    if t in MIRROR:
        return {(y, 7 - x) for y, x in court_shirt(MIRROR[t]) if bgc.px(t, y, 7 - x) == 2}
    return bgc.pixels(t, 2) - post_px.get(t, set())


slots = free_sprite_slots(court)
for t in (0x86, 0x87, 0x8A, 0x8B, 0x35, 0x36, 0x37, 0x38, 0x8E, 0x8F, 0x92, 0x93, 0x67, 0x68, 0x65, 0x66):
    eye = [EYE[t]] if t in EYE else []                  # bank 1, OBJ palette 6: colour 1 = white, 2 = red
    court.overlays.append((t, slots.pop(0), 0x08 | 6, tile_bytes(lo_px=eye, hi_px=court_shirt(t))))
court.ovl_mode = 1

# His eyes (head row) were transparent too: show skin instead of grass.
HEADS = [((0x84, 0x85), (0x86, 0x87)), ((0x88, 0x89), (0x8A, 0x8B)), ((0x33, 0x34), (0x35, 0x36)),
         ((0x8C, 0x8D), (0x8E, 0x8F)), ((0x90, 0x91), (0x92, 0x93)), ((0x69, 0x6A), (0x67, 0x68))]
for head, body in HEADS:
    grid = [[bgc.px((head, body)[r // 8][c // 8], r % 8, c % 8) for c in range(16)] for r in range(16)]
    out = flood(grid, border(16, 16), lambda r, c: grid[r][c] == 0)
    for r in range(8):
        for c in range(16):
            if grid[r][c] == 0 and (r, c) not in out:
                court.bg_patches[(head[c // 8], r)][0] |= 0x80 >> (c % 8)


# FAULT / OUT card (window layer). Its background and Mario's skin share
# colour 1 of the original tiles, so the BG palette paints both light blue
# and 8 sprites on top of Mario's face put the skin back; the three
# sprites of the bottom row also paint the white of his bib blue and his
# chair-coloured shoulders (BG tiles have no 5th colour). Sprites use OBJ
# palette 5 (CARD_OBJ_PAL while the card shows): 1 = skin, 2 = blue, 3 = chair.
# vblank.asm places the 3 x 3 block of sprites (window rows 2-4, columns 1-3).
CARD_TILES = [[0xB9, 0xBA, 0xBB, 0xBC, 0xBD], [0xBE, 0xBF, 0xC0, 0xC1, 0xC2], [0xB8, 0xAD, 0xAE, 0xAF, 0x81],
              [0x96, 0xB0, 0xB1, 0xB2, 0x81], [0x96, 0xB3, 0xB4, 0xB5, 0x81]]
CARD_BLOCK = [row[1:4] for row in CARD_TILES[2:]]
CARD_ATTR_WHITE = 0x08 | 1                          # OBJ palette 1: colour 2 = near white
CARD_ATTR = 0x08 | 5                                # VRAM bank 1, OBJ palette 5 (loaded while the card shows)
card_sprites = {}                                   # BG tile -> sprite tile, for vblank.asm
def card_px(r, c):
    return bgc.px(CARD_TILES[r // 8][c // 8], r % 8, c % 8)

card_grid = [[card_px(r, c) for c in range(40)] for r in range(40)]
card_bg = flood(card_grid, border(40, 40), lambda r, c: card_grid[r][c] == 1)   # colour 1 outside Mario
skin = {(r, c) for r in range(40) for c in range(40) if card_grid[r][c] == 1 and (r, c) not in card_bg}

# Chair-coloured shoulders: the pixels at both sides of his shoulders show
# the umpire chair (light brown) with a black outer edge. They are painted
# by the sprites (colour 3 of the card's OBJ palette); the edge is BG colour 3 (black).
BROWN_ROWS = {                                      # card row -> (left columns, right columns)
    34: (range(8, 13), range(26, 32)), 35: (range(8, 14), range(27, 32)), 36: (range(8, 12), range(28, 32)),
    37: (range(8, 11), range(29, 32)), 38: (range(8, 11), range(29, 32)), 39: (range(8, 10), range(30, 32))}
brown = {(r, c) for r, (left, right) in BROWN_ROWS.items() for c in (*left, *right)}
edge = {(r, c) for r, c in brown if c in (8, 31)}   # outermost column of each side
brown -= edge
for r, c in edge:                                   # BG colour 3 = black (ORing both planes)
    court.bg_patches[(CARD_TILES[r // 8][c // 8], r % 8)][0] |= 0x80 >> (c % 8)
    court.bg_patches[(CARD_TILES[r // 8][c // 8], r % 8)][1] |= 0x80 >> (c % 8)

# Bib: the white between the straps -> blue.
bib = {(32 + y, 8 + gx) for y in range(2, 8) for gx in range(3, 20)
       if card_px(32 + y, 8 + gx) == 0 and (32 + y, 8 + gx) not in brown}
skin -= brown | edge
white = {(18, 18)}                                  # a pixel of the cap's emblem: white, not skin
skin -= white

for br, row in enumerate(CARD_BLOCK):
    for bc, t in enumerate(row):
        r0, c0 = (2 + br) * 8, (1 + bc) * 8

        def inside(pts, r0=r0, c0=c0):      # the part of pts that falls in this tile, tile coordinates
            return {(r - r0, c - c0) for r, c in pts if r0 <= r < r0 + 8 and c0 <= c < c0 + 8}

        face, blue, chair, spot = inside(skin), inside(bib), inside(brown), inside(white)
        if face or blue or chair or spot:
            slot = slots.pop(0)
            attr = CARD_ATTR_WHITE if spot else CARD_ATTR    # that sprite needs white: OBJ palette 1 has it
            court.overlays.append((t, slot, attr, tile_bytes(lo_px=face | chair, hi_px=blue | chair | spot)))
            card_sprites[t] = (slot, attr)


# --------------------------------------------------- Mario on the board
# He sits inside the crowd (cols 9-10, rows 10-12, chair top at row 13) and
# his tiles also hold bits of the spectators next to him.
bgb = Tiles(load('bg_board.bin'), signed=True)
BLOCK = [[0x08, 0x11, 0x12, 0x0B], [0x0C, 0x13, 0x14, 0x0F], [0x10, 0x15, 0x16, 0x10]]
H, W = 24, 32
grid = [[bgb.px(BLOCK[r // 8][c // 8], r % 8, c % 8) for c in range(W)] for r in range(H)]
def is_side(c):
    return c < 8 or c >= 24

# outside = background reachable from the edges; the wall (row 12) counts as background
outside = flood(grid, border(H, W), lambda r, c: grid[r][c] == 0 or (r >= 16 and is_side(c)))
# spectators' pixels reaching into Mario's tiles
neighbour = flood(grid, [(r, c) for r in range(16) for c in range(W) if is_side(c)],
                  lambda r, c: grid[r][c] in (1, 2))
# shading on his edges (shoulder, right side, feet, the outer ends of his
# legs against the wall): brown (colour 3 of the overlay palette) instead
# of the shirt or the overalls
MARIO_EDGE_PX = {(10, 12), (10, 22), (11, 22), (12, 22), (22, 15), (23, 14), (23, 22), (18, 8), (18, 23)}
slots = free_sprite_slots(board)
for tr in range(3):
    for tc in (1, 2):
        t = BLOCK[tr][tc]
        lo, hi = set(), set()
        for y in range(8):
            for x in range(8):
                r, c = tr * 8 + y, tc * 8 + x
                v = grid[r][c]
                if (r, c) in MARIO_EDGE_PX:
                    assert v == 2
                    lo.add((y, x))
                    hi.add((y, x))
                elif v == 2 and (r, c) in neighbour:
                    if tr == 0:                     # spectator's hair: colour 3
                        lo.add((y, x))
                        hi.add((y, x))
                elif v == 2 and tr > 0:             # Mario's shirt and shoes: red
                    lo.add((y, x))
                elif v == 0 and (r, c) not in outside and tr > 0:
                    board.bg_patches[(t, y)][1] |= 0x80 >> x    # overalls (BG colour 2 = blue)
                elif v == 0 and (r, c) in outside and tr == 2:
                    hi.add((y, x))                  # wall behind his legs
        if lo or hi:
            pal = 6 if (tr, tc) == (0, 2) else 5    # right neighbour is blond
            board.overlays.append((t, slots.pop(0), 0x08 | pal, tile_bytes(lo, hi)))
for t in (0x17, 0x18):                              # see-through parts of the chair top
    board.overlays.append((t, slots.pop(0), 0x08 | 5, tile_bytes(hi_px=bgb.pixels(t, 0))))
board.ovl_mode = 2


# ------------------------------------------------------------- title "DX"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'art'))
from dx_logo import tiles as dx_tiles                 # noqa: E402
from palettes import DX_POS, DX_PAL                   # noqa: E402
for s in SCREENS:
    s.static_first, s.static = 0, []
menu.static_first = 0x80                              # title screen (level select starts with $B1)
for i, (tx, ty, data) in enumerate(dx_tiles()):
    menu.static.append((DX_POS[1] + ty * 8 + 16, DX_POS[0] + tx * 8 + 8, 0x60 + i, 0x08 | DX_PAL, data))
assert len(menu.static) <= 24, 'too many DX sprites'


# ------------------------------------------------------------- surfaces
# Surfaces with another colour outside the lines (palettes.SURFACES): every
# cell of BG palette 0 with floor (colour 0) outside the court is drawn from
# VRAM bank 1, where a copy of its tile has that floor turned into colour 2.
# "Outside" is the floor reachable from the stands, the walls and Mario's
# chair without crossing a line. A tile used on both sides of the court
# needs two different copies: the extra ones go to tile numbers the court
# never uses, and those cells of the map are pointed at them.
from palettes import SURFACES, SURFACE, LEVELS, FLOOR_DOTS, surface_palettes, surface_board   # noqa: E402


def court_inout():
    """(tiles [(dest, src, 8 row masks)], remaps [(map address, tile)], flagged cells)"""
    tmap = load('map_court.bin')
    tiles = Tiles(load('bg_court.bin'), signed=True)
    pal = [court.bg.get(t, 0) & 7 for t in tmap]
    for addr, width, p in court.rects:
        if SCRN0 <= addr < SCRN0 + 0x400:
            for c in range(width):
                pal[addr - SCRN0 + c] = p & 7

    def floor(y, x):                    # floor pixel of a palette-0 cell
        cell = (y // 8) * 32 + x // 8
        return pal[cell] == 0 and tiles.px(tmap[cell], y % 8, x % 8) == 0

    seeds = [(y, x) for y in range(256) for x in range(256) if floor(y, x)
             and any(0 <= y + dy < 256 and 0 <= x + dx < 256 and pal[((y + dy) // 8) * 32 + (x + dx) // 8]
                     for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    outside = flood([[0] * 256] * 256, seeds, floor)
    # the net posts stand beyond the sidelines and close little boxes of
    # floor: what lies past the court's edge on its row is outside too
    # (the edge of a net row is taken from the nearest row of open court:
    # the big areas of the court, not the holes of the mesh or the posts)
    rest = {(y, x) for y in range(256) for x in range(256) if floor(y, x) and (y, x) not in outside}
    court_px = set()
    while rest:
        part = flood([[0] * 256] * 256, [next(iter(rest))], lambda y, x: (y, x) in rest)
        rest -= part
        if len(part) >= 64:
            court_px |= part
    edge = {}
    for y, x in court_px:
        lo, hi = edge.get(y, (x, x))
        edge[y] = (min(lo, x), max(hi, x))
    for y in range(256):
        if y in edge:
            lo, hi = edge[y]
        else:                           # the wider of the open rows above and below
            near = [max((r for r in edge if r < y), default=None), min((r for r in edge if r > y), default=None)]
            near = [r for r in near if r is not None]
            lo, hi = min(edge[r][0] for r in near), max(edge[r][1] for r in near)
        outside |= {(y, x) for x in range(256) if (x < lo or x > hi) and floor(y, x) and (y, x) not in court_px}
    cells = {}                          # cell -> rows of outside floor
    for cell in range(1024):
        if pal[cell]:
            continue
        y0, x0 = (cell // 32) * 8, (cell % 32) * 8
        rows = tuple(sum(0x80 >> x for x in range(8) if (y0 + y, x0 + x) in outside) for y in range(8))
        if any(rows):
            cells[cell] = rows
    by_tile = defaultdict(lambda: defaultdict(list))
    for cell, rows in cells.items():
        by_tile[tmap[cell]][rows].append(cell)
    spare = [t for t in list(range(0x7F, -1, -1)) + list(range(0xFF, 0x7F, -1)) if t not in tmap]
    out, remaps = [], []
    for t, variants in sorted(by_tile.items()):
        ordered = sorted(variants.items(), key=lambda v: -len(v[1]))
        out.append((t, t, ordered[0][0]))
        for rows, where in ordered[1:]:
            dest = spare.pop(0)
            out.append((dest, t, rows))
            remaps += [(SCRN0 + c, dest) for c in where]
    return out, remaps, sorted(cells)


def court_texture(taken):
    """(tiles [(dest, 16 bytes)], runs [(map address, length, tile)]): a dotted
    copy of each plain floor tile (palette 0, all colour 0) in a spare tile
    number not in `taken`, and the cells that show it."""
    tmap = load('map_court.bin')
    tiles = Tiles(load('bg_court.bin'), signed=True)
    pal = [court.bg.get(t, 0) & 7 for t in tmap]
    for addr, width, p in court.rects:
        if SCRN0 <= addr < SCRN0 + 0x400:
            for c in range(width):
                pal[addr - SCRN0 + c] = p & 7
    plain = sorted({t for cell, t in enumerate(tmap) if pal[cell] == 0
                    and all(tiles.px(t, y, x) == 0 for y in range(8) for x in range(8))})
    # a tile number nothing uses: blank in VRAM, not on the map, not drawn
    # later (Mario's tiles are not on the map yet but have their graphics)
    spare = [t for t in range(0xFF, 0x7F, -1) if t not in tmap and t not in taken
             and not any(tiles.px(t, y, x) for y in range(8) for x in range(8))]
    assert len(spare) >= len(plain) == 1, 'one plain floor tile and a free tile for its dotted copy'
    dest = {t: spare.pop(0) for t in plain}
    data = []
    for t in plain:
        rows = [0] * 8
        for x, y in FLOOR_DOTS:
            rows[y] |= 0x80 >> x
        data.append((dest[t], [b for r in rows for b in (0, r)]))     # colour 2: high plane only
    runs = []
    for cell, t in enumerate(tmap):
        if pal[cell] == 0 and t in dest:
            if runs and runs[-1][0] + runs[-1][1] == SCRN0 + cell and runs[-1][2] == dest[t] and cell % 32:
                runs[-1][1] += 1
            else:
                runs.append([SCRN0 + cell, 1, dest[t]])
    return data, runs


SCRN0 = 0x9800


# Crowd rows in front of and behind the court: hair and clothes share
# colour 2. Hair = colour 2 joined to the top of the head; the rest is
# clothes, drawn from a bank-1 copy with them in colour 0 (BG palette 4).
CROWD_PEOPLE = [((0x7D, 0x7E), (0x7F, 0x70)), ((0x7D, 0x7E), (0x3F, 0x32)),   # front: head over body
                ((0x74,), ())]                                                # back: whole person


def crowd_clothes():
    """([(tile, 8 row masks of clothes)], flagged cells)"""
    tmap = load('map_court.bin')
    tiles = Tiles(load('bg_court.bin'), signed=True)
    masks_by_tile = {}
    for top, bottom in CROWD_PEOPLE:
        rows = [top] + ([bottom] if bottom else [])
        grid = [[tiles.px(row[c // 8], r % 8, c % 8) for c in range(8 * len(top))]
                for i, row in enumerate(rows) for r in range(i * 8, i * 8 + 8)]
        w = len(grid[0])
        top_rows = 6 if bottom else 4               # the head: front, top of the oval; back, all of it
        seeds = [(r, c) for r in range(top_rows) for c in range(w) if grid[r][c] == 2]
        hair = flood(grid, seeds, lambda r, c: grid[r][c] == 2 and (bottom or r < top_rows))
        for i, row in enumerate(rows):
            for k, t in enumerate(row):
                m = [sum(0x80 >> x for x in range(8) if grid[i * 8 + y][k * 8 + x] == 2
                         and (i * 8 + y, k * 8 + x) not in hair) for y in range(8)]
                if any(m):
                    assert masks_by_tile.get(t, m) == m
                    masks_by_tile[t] = m
    cells = sorted(c for c in range(1024) if tmap[c] in masks_by_tile)
    return sorted(masks_by_tile.items()), cells


def emit_runs(f, cells):
    run = []
    for c in cells + [None]:
        if run and (c is None or c != run[-1] + 1 or c // 32 != run[0] // 32):
            f.write(f'    dw ${SCRN0 + run[0]:04X}\n    db {len(run)}\n')
            run = []
        if c is not None:
            run.append(c)
    f.write('    dw 0\n')


def emit_surfaces(f):
    f.write('; Surface of each level (LevelSurfaces -> entry). Entry: kind (SURF_*);\n'
            '; unless grass, the court (64 bytes of BG palettes, OBJ palette 4) and\n'
            '; the score board (SURF_BOARD: 64 bytes of BG palettes, OBJ palettes 5-6).\n'
            '; Grass keeps the palettes of the screen blocks, and its mowing stripes.\n')
    f.write('DEF SURF_PLAIN EQU 0\nDEF SURF_INOUT EQU 1      ; the outside of the court has its own colour (CourtInOut)\n'
            'DEF SURF_GRASS EQU 2\nDEF SURF_BOARD EQU 1 + 72\n')
    f.write(f'DEF SURF_FALLBACK EQU {LEVELS.index("Hierba")}      ; not a level: grass\n')
    f.write('SECTION "Surfaces", ROMX, BANK[2]\nLevelSurfaces:\n')
    names = list(SURFACE)
    for lv, name in enumerate(LEVELS):
        f.write(f'    dw Surface{names.index(name)}      ; LEVEL {lv + 1}: {name}\n')
    for i, sf in enumerate(SURFACES):
        f.write(f'Surface{i}:      ; {sf["name"]}\n')
        if sf.get('grass'):
            f.write('    db SURF_GRASS\n')
            continue
        bg, obj4, inout = surface_palettes(sf)
        f.write(f'    db {"SURF_INOUT" if inout else "SURF_PLAIN"}\n')
        db(f, (b for p in bg for c in p for b in rgb555(c)))
        db(f, (b for c in obj4 for b in rgb555(c)))
        bbg, bobj = surface_board(sf)
        db(f, (b for p in bbg + bobj for c in p for b in rgb555(c)))
    tiles, remaps, cells = court_inout()
    f.write('CourtInOut:\n    ; bank-1 tiles: count, then (destination, source, rows of floor to turn into colour 2)\n')
    f.write(f'    db {len(tiles)}\n')
    for dest, src, rows in tiles:
        db(f, [dest, src] + list(rows))
    f.write(f'    ; map cells pointed at a second copy: count, then (address, tile)\n    db {len(remaps)}\n')
    for addr, t in remaps:
        f.write(f'    dw ${addr:04X}\n    db ${t:02X}\n')
    f.write('    ; cells drawn from bank 1: runs of (address, length), 0 ends\n')
    emit_runs(f, cells)
    f.write('LevelTexture:      ; LEVEL 1-4: dotted floor (palettes.py, FLOOR_DOTS)\n')
    db(f, [SURFACE[name].get('texture', 0) for name in LEVELS])
    data, runs = court_texture({dest for dest, _, _ in tiles})
    f.write('FloorDots:\n    ; tiles: count, then (tile, 16 bytes)\n')
    f.write(f'    db {len(data)}\n')
    for t, b in data:
        db(f, [t] + b)
    f.write('    ; cells: runs of (address, length, tile), 0 ends\n')
    for addr, n, t in runs:
        f.write(f'    dw ${addr:04X}\n    db {n}, ${t:02X}\n')
    f.write('    dw 0\n')
    tiles, cells = crowd_clothes()
    f.write('CrowdClothes:\n    ; bank-1 tiles: count, then (tile, rows of clothes to turn into colour 0)\n')
    f.write(f'    db {len(tiles)}\n')
    for t, rows in tiles:
        db(f, [t] + rows)
    f.write('    ; cells drawn from bank 1\n')
    emit_runs(f, cells)
    f.write('\n')


# ------------------------------------------------------------------- emit
def db(f, values):
    values = list(values)
    for i in range(0, len(values), 16):
        f.write('    db ' + ', '.join(f'${v:02X}' for v in values[i:i + 16]) + '\n')


def emit(f, s):
    f.write(f'SECTION "Block{s.name}", ROMX, BANK[2], ALIGN[10]\nBlock{s.name}:\n')
    db(f, (s.bg.get(t, 0) for t in range(256)))
    db(f, (s.obj0.get(t, s.obj_default[0]) for t in range(256)))
    db(f, (s.obj1.get(t, s.obj_default[1]) for t in range(256)))
    for pals in (s.bg_pals, s.obj_pals):
        db(f, (b for p in pals for c in p for b in rgb555(c)))
    f.write('    ; rectangles\n')
    for addr, width, pal in s.rects:
        f.write(f'    dw ${addr:04X}\n    db {width}, {pal}\n')
    f.write('    dw 0\n    ; sprite tile patches (VRAM bank 1): per tile, the sum of its 16\n'
            '    ; original bytes (the patches only apply to that drawing), then the rows\n')
    tiles = Tiles(load(f'spr_{s.name.lower()}.bin'), signed=False) if s.spr_patches else None
    by_tile = defaultdict(list)
    for (t, r), (lo, hi) in sorted(s.spr_patches.items()):
        if lo or hi:
            by_tile[t].append((r, lo, hi))
    for t, rows in sorted(by_tile.items()):
        o = tiles.offset(t)
        chk = sum(tiles.data[o:o + 16]) & 0xFFFF
        f.write(f'    db ${t:02X}, ${chk & 0xFF:02X}, ${chk >> 8:02X}, {len(rows)}\n')
        for r, lo, hi in rows:
            f.write(f'    db {r}, ${lo:02X}, ${hi:02X}\n')
    f.write('    db $FF\n    ; BG tile patches\n')
    for (t, r), (lo, hi) in sorted(s.bg_patches.items()):
        f.write(f'    db ${t:02X}, {r}, ${lo:02X}, ${hi:02X}\n')
    f.write(f'    db $FF\n    ; overlays\n    db {s.ovl_mode}, {len(s.overlays)}\n')
    for t, slot, attr, data in s.overlays:
        f.write(f'    db ${t:02X}, ${slot:02X}, ${attr:02X}\n')
        db(f, data)
    f.write(f'    ; static sprites\n    db ${s.static_first:02X}, {len(s.static)}\n')
    for y, x, slot, attr, data in s.static:
        f.write(f'    db {y}, {x}, ${slot:02X}, ${attr:02X}\n')
        db(f, data)
    f.write('\n')


def emit_sgb(f):
    """Super Game Boy: a PAL01 packet per level (palette 0 = palette 1)."""
    from palettes import SGB_WHITE, SGB_STAND, SGB_SHADOW, SGB_SURFACE
    f.write('\n; Super Game Boy: PAL01 packet of each level (16 bytes)\n')
    f.write('SECTION "SgbPackets", ROMX, BANK[2]\nSgbPalPackets:\n')
    for name in LEVELS:
        cols = [SGB_WHITE, SGB_SURFACE[name], SGB_STAND, SGB_SHADOW]
        pkt = [0x01] + [b for c in cols for b in rgb555(c)] + [b for c in cols[1:] for b in rgb555(c)] + [0]
        assert len(pkt) == 16
        f.write(f'    ; {name}\n')
        db(f, pkt)


def emit_sgb_border(f):
    """Super Game Boy border from tools/data/sgb_border.png (256 x 224, at most
    15 colours plus magenta for the game's window)."""
    path = os.path.join(DATA, 'sgb_border.png')
    from PIL import Image
    im = Image.open(path).convert('RGB')
    assert im.size == (256, 224), 'the border must be 256 x 224'
    px = im.load()
    clear = (255, 0, 255)
    colours = sorted({px[x, y] for x in range(256) for y in range(224)} - {clear})
    assert len(colours) <= 15, f'the border has {len(colours)} colours (15 at most)'
    index = {c: i + 1 for i, c in enumerate(colours)}
    index[clear] = 0
    blank = tuple((0,) * 8 for _ in range(8))
    tiles = [blank]
    where = {blank: (0, 0)}
    entries = []
    for ty in range(28):
        for tx in range(32):
            t = tuple(tuple(index[px[tx * 8 + x, ty * 8 + y]] for x in range(8)) for y in range(8))
            for flips, v in ((0, t), (0x40, tuple(r[::-1] for r in t)), (0x80, t[::-1]),
                             (0xC0, tuple(r[::-1] for r in t[::-1]))):
                if v in where:
                    n, fl = where[v][0], flips
                    break
            else:
                n, fl = len(tiles), 0
                tiles.append(t)
                where[t] = (n, 0)
            entries.append((n, fl))
    assert len(tiles) <= 128, f'{len(tiles)} tiles: one CHR_TRN holds 128'

    def snes(t):
        lo = []
        hi = []
        for row in t:
            b = [sum(((p >> plane) & 1) << (7 - x) for x, p in enumerate(row)) for plane in range(4)]
            lo += b[0:2]
            hi += b[2:4]
        return lo + hi
    f.write(f'\n; Super Game Boy border: {len(tiles)} tiles, {len(colours)} colours (palette 4)\n')
    f.write(f'DEF SGB_BORDER_TILES EQU {len(tiles)}\n')
    f.write('SECTION "SgbBorder", ROMX, BANK[3]      ; read through FarCopy (colorize.asm)\nSgbBorderTiles:\n')
    for t in tiles:
        db(f, snes(t))
    f.write('SgbBorderTilesEnd:\nSgbBorderMap:              ; 32 x 28 entries: tile, palette 4 and flips\n')
    for n, fl in entries:
        db(f, [n, 0x10 | fl])
    f.write('SgbBorderMapEnd:\nSgbBorderPal:\n')
    db(f, [0, 0] + [b for c in colours for b in rgb555('#%02X%02X%02X' % c)] + [0, 0] * (15 - len(colours)))
    f.write('SgbBorderPalEnd:\n')


def write(path):
    """Writes the include file the assembler reads."""
    with open(path, 'w') as f:
        f.write('; Generated by tools/gen_data.py from tools/palettes.py - do not edit\n\n')
        f.write('; FAULT / OUT card: sprite tile of each BG tile of Mario\'s face and bib\n')
        for t, (slot, attr) in sorted(card_sprites.items()):
            f.write(f'DEF CARD_SPR_{t:02X} EQU ${slot:02X}\n')
            if attr != CARD_ATTR:
                f.write(f'DEF CARD_ATTR_{t:02X} EQU ${attr:02X}\n')
        f.write(f'DEF CARD_ATTR EQU ${CARD_ATTR:02X}\n')
        f.write('; colours 1-3 of OBJ palette 5: loaded while the card shows / normal\n')
        for name, pal in (('CARD_PAL', CARD_OBJ_PAL), ('PAL5_NORMAL', court.obj_pals[5])):
            for i, b in enumerate(b for c in pal[1:] for b in rgb555(c)):
                f.write(f'DEF {name}_{i} EQU ${b:02X}\n')
        f.write('\n')
        for s in SCREENS:
            emit(f, s)
        emit_surfaces(f)
        emit_sgb(f)
        emit_sgb_border(f)


if __name__ == '__main__':
    write(sys.argv[1])
