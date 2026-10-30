#!/usr/bin/env python3
"""Collects every pose of the two players and draws them as a sheet.

    poses.py ROM.gbc OUT.png [FRAMES] [SEEDS]      (e.g. 30000 1,2,3,4)

A bot plays (chasing the ball, hitting with A and B, moving at random) and,
every few frames, takes each player's sprites from OAM and draws them from
VRAM itself, so neither the court nor other sprites get in the way. Each
pixel is kept as the palette slot that draws it (OBJ palette, colour), so
the sheet shows each pose in the colours of tools/palettes.py.

The sheet shows the game's own graphics: it is written to build/ and is
not part of the repository. Needs pyboy and pillow."""
import random
import sys

BALL = (0x31, 0x37, 0x38)    # court tiles; on the score board these numbers are parts of the players
SHADOW = (0x22, 0x2F)       # the ball's shadow
NOT_PLAYER_PALS = {'court': (5,), 'board': (5, 6)}   # court: a hit's gold sparkles; board: Mario's overlay
BOARD_RIVAL_PALS = (1, 4)   # score board: the opponent's palettes
MAX_WIDTH = 34              # one player: up to 33 pixels (lying on the floor)


def screen_of(m):
    if not m[0xFF40] & 0x80:
        return None
    if m[0x9800] == 0x82:
        return 'court'
    if m[0x9800] < 0x80:
        return 'board'
    return None


def clusters(sprites):
    """Groups sprites that touch (8x8 boxes no more than 1 pixel apart)."""
    groups = []
    for s in sprites:
        near = [g for g in groups if any(abs(s[0] - t[0]) <= 9 and abs(s[1] - t[1]) <= 9 for t in g)]
        merged = [s]
        for g in near:
            merged += g
            groups.remove(g)
        groups.append(merged)
    return groups


def draw(m, group):
    """Pixel grid of a sprite group: None or (OBJ palette, colour index)."""
    y0 = min(s[0] for s in group)
    x0 = min(s[1] for s in group)
    h = max(s[0] for s in group) - y0 + 8
    w = max(s[1] for s in group) - x0 + 8
    grid = [[None] * w for _ in range(h)]
    for y, x, t, a, _ in sorted(group, key=lambda s: -s[4]):     # lower OAM index on top
        bank = (a >> 3) & 1
        base = 0x8000 + t * 16
        for py in range(8):
            ty = 7 - py if a & 0x40 else py
            lo, hi = m[bank, base + 2 * ty], m[bank, base + 2 * ty + 1]
            for px in range(8):
                tx = 7 - px if a & 0x20 else px
                c = ((lo >> (7 - tx)) & 1) | (((hi >> (7 - tx)) & 1) << 1)
                if c:
                    grid[y - y0 + py][x - x0 + px] = (a & 7, c)
    return tuple(tuple(r) for r in grid)


def overlay_tiles():
    """{screen: bank-1 tiles of Mario's overlay and the FAULT card} (from gen_data)."""
    import gen_data
    court = {slot for _, slot, _, _ in gen_data.court.overlays} | {s for s, _ in gen_data.card_sprites.values()}
    board = {slot for _, slot, _, _ in gen_data.board.overlays}
    return {'court': court, 'board': board}


def collect(rom, frames=30000, seed=1, poses=None, skip=None):
    """{(screen, player, tiles): {grid: times seen}}; player 0 = you, 1 = the opponent.
    skip: overlay_tiles(), so that Mario's sprites never join a player standing by his chair."""
    skip = skip or {'court': set(), 'board': set()}
    from pyboy import PyBoy
    pb = PyBoy(rom, window='null', sound_emulated=False, cgb=True)
    pb.set_emulation_speed(0)
    m = pb.memory
    rng = random.Random(seed)
    poses = {} if poses is None else poses
    for f in range(frames):
        scr = screen_of(m)
        if scr != 'court':                      # (start on the court would pause the game)
            if f % 150 == 0:
                pb.button('start', 3)
        elif f % 3 == 0:
            spr = [(m[0xFE00 + i], m[0xFE01 + i], m[0xFE02 + i], m[0xFE03 + i]) for i in range(0, 160, 4) if m[0xFE00 + i]]
            ball = [s for s in spr if s[2] in BALL]
            me = [s for s in spr if 0x40 <= s[2] < 0x72]
            r = rng.random()
            if ball and me and r < 0.7:
                bx, by = ball[0][1], ball[0][0]
                px = sum(s[1] for s in me) / len(me)
                py = max(s[0] for s in me)
                if bx < px - rng.randint(2, 14):
                    pb.button('left', 3)
                elif bx > px + rng.randint(2, 14):
                    pb.button('right', 3)
                if rng.random() < 0.3:
                    pb.button(rng.choice(('up', 'down')), rng.randint(2, 10))
                if abs(by - py) < 24 and rng.random() < 0.5:
                    pb.button(rng.choice(('a', 'a', 'b')), 2)
            elif r < 0.85:
                pb.button(rng.choice(('left', 'right', 'up', 'down', 'a', 'b')), rng.randint(2, 12))
        pb.tick(1, False)
        if f % 2 or scr is None or not m[0xFF40] & 0x02:
            continue                            # (sprites switched off: OAM may hold stale entries)
        spr = [(m[0xFE00 + i] - 16, m[0xFE01 + i] - 8, m[0xFE02 + i], m[0xFE03 + i], i // 4)
               for i in range(0, 160, 4)
               if m[0xFE00 + i] and m[0xFE02 + i] < 0x80 and not (scr == 'court' and m[0xFE02 + i] in BALL + SHADOW)
               and m[0xFE03 + i] & 7 not in NOT_PLAYER_PALS[scr]
               and not (m[0xFE03 + i] & 0x08 and m[0xFE02 + i] in skip[scr])]
        if scr == 'court':
            # one group per DMG palette bit (each player's sprites, racket
            # included, carry their own), so players standing together stay apart
            groups = clusters([s for s in spr if not s[3] & 0x10]) + clusters([s for s in spr if s[3] & 0x10])
        else:
            # score board: the opponent's head has your bit; tell them apart by
            # their palettes, and skip the frames where they overlap
            groups = [g for g in clusters(spr)
                      if not (sum(s[3] & 7 in BOARD_RIVAL_PALS for s in g) >= 3
                              and sum(s[3] & 7 not in BOARD_RIVAL_PALS for s in g) >= 3)]
        for g in groups:
            if len(g) < 5 or min(s[0] for s in g) < 0 or max(s[1] for s in g) > 152 or min(s[1] for s in g) < 0:
                continue                        # sparkles, or a player cut by the edge of the screen
            if max(s[1] for s in g) - min(s[1] for s in g) > MAX_WIDTH - 8:
                continue                        # two figures side by side (score board)
            if scr == 'court':
                who = 1 if g[0][3] & 0x10 else 0
            else:
                who = 1 if any(s[3] & 7 in BOARD_RIVAL_PALS for s in g) else 0
            # one entry per set of tiles; the drawing kept is the one seen most
            sig = tuple(sorted((s[2], s[3] & 0x60) for s in g))
            grids = poses.setdefault((scr, who, sig), {})
            grid = draw(m, g)
            grids[grid] = grids.get(grid, 0) + 1
    pb.stop(False)
    return poses


def stable(poses, min_seen=3):
    """[(screen, player, grid)]: the most common drawing of each pose seen at
    least min_seen times (one-frame leftovers while a scene sets up are not poses)."""
    return [(scr, who, max(gr, key=gr.get)) for (scr, who, _), gr in poses.items() if sum(gr.values()) >= min_seen]


def sheet(poses, colour, cols=12, scale=4, pad=6):
    """Pillow image of the poses: one block per (screen, player), each pose numbered."""
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', 22)
        small = ImageFont.truetype('DejaVuSans.ttf', 14)
    except OSError:
        font = small = ImageFont.load_default()
    blocks = []
    for scr in ('court', 'board'):
        for who in (0, 1):
            items = [g for s, w, g in stable(poses) if s == scr and w == who]
            if items:
                items.sort(key=lambda g: (len(g), len(g[0]), str(g)))
                blocks.append((scr, who, items))
    cw = max(len(g[0]) for _, _, items in blocks for g in items) + pad
    ch = max(len(g) for _, _, items in blocks for g in items) + pad + 5      # + room for the number
    title = 12
    height = sum(title + ch * -(-len(items) // cols) for _, _, items in blocks)
    img = Image.new('RGB', (cols * cw * scale, height * scale), '#5C6A70')
    d = ImageDraw.Draw(img)
    y = 0
    names = {('court', 0): 'Pista: tú', ('court', 1): 'Pista: rival',
             ('board', 0): 'Presentación: tú', ('board', 1): 'Presentación: rival'}
    for scr, who, items in blocks:
        d.text((10, y * scale + 12), f'{names[scr, who]} ({len(items)} posturas)', fill='white', font=font)
        y += title
        for n, g in enumerate(items):
            ox = (n % cols) * cw + (cw - len(g[0])) // 2
            base = y + (n // cols) * ch
            oy = base + (ch - 5 - len(g))
            for gy, row in enumerate(g):
                for gx, cell in enumerate(row):
                    if cell:
                        c = colour(scr, *cell)
                        x1, y1 = (ox + gx) * scale, (oy + gy) * scale
                        d.rectangle((x1, y1, x1 + scale - 1, y1 + scale - 1), fill=c)
            label = f'{"T" if who == 0 else "R"}{"p" if scr == "court" else "s"}{n + 1}'
            tx = ((n % cols) * cw + cw / 2) * scale
            d.text((tx, (base + ch - 3) * scale), label, fill='#E8EEF0', font=small, anchor='mm')
        y += ch * -(-len(items) // cols)
    return img


def main(rom, out, frames=30000, seeds='1,2,3,4'):
    sys.path.insert(0, __import__('os').path.dirname(__file__))
    import palettes
    scr = {'court': palettes.court, 'board': palettes.board}
    poses, skip = {}, overlay_tiles()
    for s in seeds.split(','):
        collect(rom, int(frames), int(s), poses, skip)
    print(len(stable(poses)), 'poses')
    sheet(poses, lambda name, pal, idx: str(scr[name].obj_pals[pal][idx])).save(out)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
