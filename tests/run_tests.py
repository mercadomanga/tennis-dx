#!/usr/bin/env python3
"""Regression tests for Tennis DX (needs: pip install pyboy pillow).

run_tests.py PATCHED.gbc ORIGINAL.gb [--shots DIR]

1. DMG: with the same button presses, the patched ROM must draw the same
   frames as the original on a monochrome Game Boy, but for the CPU's eyes
   and shoes, now white: any pixel that differs must be white.
2. GBC: a bot plays through every screen (title, level select, score
   board, court, changing ends, end of match); checks that each screen is
   recognised and coloured, and that Mario's overlay sprites line up.
3. GBC: the FAULT card (light blue window, Mario's face, bib and brown
   shoulders drawn with sprites) matches, pixel by pixel, what gen_data.py says it should be.
4. GBC, 2-player mode: the second console of a linked game XORs every
   sprite's DMG palette bit ($FFEB = $10). Forcing that, the screens must
   stay pixel for pixel the same: each player keeps its colours.
5. GBC, surfaces: for each LEVEL, the score board and the court show the
   floor of its surface (palettes.LEVELS), and every pixel has a colour of
   that surface's palettes (no grass left on clay, and so on).
6. GBC, VRAM timing (needs build/audit.gbc, `make audit`): a match full of
   faults, FAULT cards and changes of ends; the audit build counts every
   VRAM / palette write of ours made outside VBlank (the PPU would drop it
   on hardware) and every screen left uncoloured. Also: whenever Mario is on
   screen his overlay sprites are there, and none is beyond the 10 sprites a
   line the hardware draws.
"""
import argparse
import os
import random
import sys

from pyboy import PyBoy

ap = argparse.ArgumentParser()
ap.add_argument('rom')
ap.add_argument('base')
ap.add_argument('--shots', default='build/shots')
ap.add_argument('--frames', type=int, default=60000)
args = ap.parse_args()
failures = []


def check(cond, msg):
    print(('  ok   ' if cond else '  FAIL ') + msg)
    if not cond:
        failures.append(msg)


def emu(rom, cgb):
    pb = PyBoy(rom, window='null', sound_emulated=False, cgb=cgb)
    pb.set_emulation_speed(0)
    return pb


class Bot:
    """Deterministic player: starts the game, then chases the ball."""

    def __init__(self, pb, seed, render=False):
        self.pb, self.m, self.rng, self.f = pb, pb.memory, random.Random(seed), 0
        self.render = render

    def step(self):
        m, pb, f = self.m, self.pb, self.f
        if f < 3000:
            if f % 150 == 0:
                pb.button('start', 3)
        elif f % 4 == 0:
            spr = [(m[0xFE00 + i], m[0xFE01 + i], m[0xFE02 + i], m[0xFE03 + i])
                   for i in range(0, 160, 4) if m[0xFE00 + i]]
            ball = [s for s in spr if s[2] in (0x31, 0x37, 0x38)]
            # (palette 5 = the sprites of Mario's portrait while the FAULT card shows)
            me = [s for s in spr if not s[3] & 0x10 and s[3] & 7 != 5 and s[2] not in (0x31, 0x37, 0x38, 0x22, 0x2F)]
            if ball and me and self.rng.random() < 0.9:
                bx, by = ball[0][1], ball[0][0]
                px = sum(s[1] for s in me) / len(me)
                py = max(s[0] for s in me)
                if bx < px - 6:
                    pb.button('left', 3)
                elif bx > px + 6:
                    pb.button('right', 3)
                if abs(by - py) < 20:
                    pb.button('a', 2)
            elif f % 300 == 0:
                pb.button(self.rng.choice(['a', 'start']), 2)
        pb.tick(1, render=self.render)
        self.f += 1


# ------------------------------------------------------------------ 1. DMG
# The hooks cost a few CPU cycles, and the game draws its random numbers
# from the timer, so a long rally plays out differently. What must not
# change is the picture: every screen the game builds (title, level
# select, score board, court) is captured shortly after it appears.
print('DMG: every screen must look like the original (the CPU\'s eyes and shoes now white)')


def dmg_screens(rom):
    pb = emu(rom, False)
    m = pb.memory
    shots, last_on, f = [], 0, 0
    while len(shots) < 6 and f < 20000:
        if f % 150 == 0 and len(shots) < 4:
            pb.button('start', 3)       # title -> level -> board -> court
        pb.tick(1, render=False)
        f += 1
        on = m[0xFF40] >> 7
        if on and not last_on:
            pb.tick(40, True)
            f += 40
            shots.append(pb.screen.ndarray[:, :, :3].copy())
        last_on = on
    pb.stop(False)
    return shots


orig, patched = dmg_screens(args.base), dmg_screens(args.rom)
white = orig[0][0, 0]                   # the title's top left corner is paper


def same_or_white(a, b):
    diff = (a != b).any(axis=2)
    return (b[diff] == white).all()


check(len(orig) >= 5 and len(orig) == len(patched) and all(same_or_white(a, b) for a, b in zip(orig, patched)),
      f'DMG screens: the same but for white pixels ({sum((a == b).all() for a, b in zip(orig, patched))}/{len(orig)} identical)')

# ------------------------------------------------------------------ 2. GBC
print('GBC: play through every screen')
os.makedirs(args.shots, exist_ok=True)
pb = emu(args.rom, True)
m = pb.memory
bot = Bot(pb, 1)
seen, last_on = {}, 0
overlay_ok = overlay_checked = 0
for f in range(args.frames):
    bot.step()
    on = m[0xFF40] >> 7
    if on and not last_on:
        pb.tick(30, True)
        bot.f += 30
        first = m[0x9800]
        screen = 'court' if first == 0x82 else ('board' if first < 0x80 else 'menu')
        key = (screen, m[0xFF8A])
        if key not in seen:
            seen[key] = f
            pb.screen.image.convert('RGB').save(f'{args.shots}/{len(seen):02d}_{screen}_{m[0xFF8A]}.png')
    last_on = on
    # Mario's overlay: the 4 court sprites must sit exactly on his tiles
    if f % 97 == 0 and on and m[0x9800] == 0x82 and m[0xD2FF] == 1 and not m[0xFF40] & 0x20:
        col = 22 if m[0x9800 + 11 * 32 + 22] not in (0x80, m[0xD2F4]) else 3
        y = (12 * 8 - m[0xFF42] + 16) & 0xFF
        x = (col * 8 - m[0xFF43] + 8) & 0xFF
        if m[0xDEA0] <= 0x90:
            overlay_checked += 1
            overlay_ok += (m[0xDE9C], m[0xDE9D]) == (y, x) or m[0xDE9C] == 0
    if len({k[0] for k in seen}) == 3 and any(k[1] == 6 for k in seen) and f > 30000:
        break

names = {k[0] for k in seen}
check(names == {'menu', 'board', 'court'}, f'screens reached: {sorted(names)}')
check(any(s == 'board' and st == 6 for s, st in seen), 'end of match reached')
check(overlay_checked > 20 and overlay_ok == overlay_checked,
      f'Mario overlay aligned ({overlay_ok}/{overlay_checked} samples)')
# palettes loaded: BG palette 0 colour 0 of the court is grass, not white
pb.memory[0xFF68] = 0
check((pb.memory[0xFF69], ) != (0xFF, ), 'CGB palette RAM written')
pb.stop(False)
print(f'screenshots: {args.shots}/')

# ------------------------------------------------------------ 3. FAULT card
print('GBC: FAULT card')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import gen_data as gd                                  # noqa: E402
from palettes import court as court_pal, CARD_BLUE, CARD_OBJ_PAL      # noqa: E402


def rgb(hex_colour):
    return tuple((int(hex_colour.lstrip('#')[i:i + 2], 16) >> 3) << 3 for i in (0, 2, 4))


WHITE, SKIN, RED, BLACK = (rgb(c) for c in court_pal.bg_pals[6][0:1] + CARD_OBJ_PAL[1:2]
                           + court_pal.bg_pals[6][2:4])
BLUE, TAN, LIGHT = rgb(CARD_OBJ_PAL[2]), rgb(CARD_OBJ_PAL[3]), rgb(CARD_BLUE)
expect = {}
for r in range(40):
    for c in range(43):
        v = gd.card_grid[r][c] if c < 40 else 1
        if c >= 40:
            colour = LIGHT                              # the strip right of the card
        elif (r, c) in gd.white:
            colour = rgb(court_pal.obj_pals[1][2])      # one pixel of the cap's emblem
        elif (r, c) in gd.brown:
            colour = TAN                                # beside his shoulders: the chair's brown
        elif (r, c) in gd.edge:
            colour = BLACK
        elif v == 0:
            colour = BLUE if (r, c) in gd.bib else WHITE
        elif v == 1:
            colour = SKIN if (r, c) in gd.skin else LIGHT
        else:
            colour = RED if v == 2 else BLACK
        expect[(r, c)] = colour
FAULT_ROW0 = [0xB9, 0xBA, 0xBB, 0xBC, 0xBD]
pb = emu(args.rom, True)
m = pb.memory
bot = Bot(pb, 4, render=True)       # every frame rendered: that is how the window is placed on hardware
steady = checked = bad = leaks = 0
score_run = score_frames = score_bad = 0
win_frames = half = 0
card_tiles = {slot for slot, _ in gd.card_sprites.values()}
for f in range(60000):
    bot.step()
    if m[0xFF40] & 0x80 and m[0x9800] == 0x82 and m[0xFFA6] & 0x20:
        # the score box is drawn whole, not a few tiles per frame: header and divider come together
        win_frames += 1
        divider = all(m[0x9C00 + 2 * 32 + c] == 0xF7 for c in range(5))
        half += (m[0x9C00 + 3 * 32 + 1] == 0xE9) != divider or (divider and m[0x9C00 + 32 + 2] != 0xF4)
    if m[0xFF40] & 0x80 and m[0x9800] == 0x82 and m[0xFFA6] & 0x20 and m[0x9C00 + 3 * 32 + 1] == 0xE9:
        score_run += 1                  # score box: the cap of the last card must not show in its middle row
        if score_run > 2:
            score_frames += 1
            score_bad += (any(m[0x9C00 + 2 * 32 + c] not in (0x80, 0xF7) for c in range(5)) or m[0x9C00 + 32 + 4] in (0xC2, 0xB7))
    else:
        score_run = 0
    if m[0xFF40] & 0x80 and m[0x9800] == 0x82 and m[0xD2FA] == 0:      # no card: none of its sprites may show
        leaks += any(m[0xFE00 + j] and m[0xFE02 + j] in card_tiles and m[0xFE03 + j] == 0x0D
                     for j in range(0, 160, 4))
    card = (m[0xFF40] & 0x80 and m[0x9800] == 0x82 and m[0xFF40] & 0x20 and m[0xFF4A] == 0
            and [m[0x9C00 + c] for c in range(5)] == FAULT_ROW0
            and m[0x9C00 + 2 * 32 + 1] == 0xAD and m[0x9C00 + 4 * 32 + 1] == 0xB3)
    steady = steady + 1 if card else 0
    if steady > 6:                  # the card slides in during the first frames
        im = pb.screen.image.convert('RGB')
        if checked < 40:
            checked += 1
            bad += any(im.getpixel((117 + c, r)) != col for (r, c), col in expect.items())
    if checked >= 40 and f > 20000:     # keep playing: the leak check needs several cards and score boxes
        break
check(checked >= 40 and bad == 0, f'FAULT card pixel-perfect ({checked - bad}/{checked} frames)')
check(score_frames > 50 and score_bad == 0, f'score box without card leftovers ({score_frames - score_bad}/{score_frames} frames)')
check(win_frames > 500 and half == 0, f'score box never half drawn ({win_frames - half}/{win_frames} window frames)')
check(leaks == 0, f'no card sprite left behind ({leaks} frames)')
pb.stop(False)

# ------------------------------------------------------------ 4. 2 players
# The game stores its sprite XOR at $006F ("ldh [$FFEB], a"): $10 on the
# second console of a linked game, 0 otherwise. Setting it to $10 there
# draws every frame as the second console would.
print('GBC: second console of a 2-player game')
SPR_XOR_STORE = 0x006F


def frames_seen(second_console):
    pb = emu(args.rom, True)
    if second_console:
        def force(ctx):
            pb.register_file.A = 0x10
        pb.hook_register(0, SPR_XOR_STORE, force, None)
    out = []
    for f in range(5000):
        if f < 3000 and f % 150 == 0:
            pb.button('start', 3)
        if f > 3200 and f % 40 == 0:
            pb.button(('left', 'a', 'right', 'a')[f // 40 % 4], 5)
        pb.tick(1, True)
        if f % 10 == 0:
            out.append(pb.screen.image.tobytes())
    pb.stop(False)
    return out


one, two = frames_seen(False), frames_seen(True)
same = sum(a == b for a, b in zip(one, two))
check(same == len(one), f'same colours on both consoles ({same}/{len(one)} frames)')

# ------------------------------------------------------------- 5. surfaces
print('GBC: one surface per level')
import palettes as P                                   # noqa: E402


def c5(colour):
    return tuple(int(str(colour).lstrip('#')[i:i + 2], 16) >> 3 for i in (0, 2, 4))


def level_colours(sf):
    cols = {c5(c) for c in P.CARD_OBJ_PAL}
    for scr in P.SCREENS:
        bg, obj = list(scr.bg_pals), list(scr.obj_pals)
        if not sf.get('grass') and scr is P.court:
            bg, obj[4], _ = P.surface_palettes(sf)
        if not sf.get('grass') and scr is P.board:
            bg, obj[5:7] = P.surface_board(sf)
        cols |= {c5(c) for pal in bg + obj for c in pal}
    return cols


for lv, name in enumerate(P.LEVELS, 1):
    sf = P.SURFACE[name]
    allowed = level_colours(sf)
    if sf.get('grass'):
        floor = {'board': c5(P.board.bg_pals[7][0]), 'court': c5(P.court.bg_pals[0][0])}
    else:
        floor = {'board': c5(sf['outside']), 'court': c5(sf['outside'])}
    pb = emu(args.rom, True)
    m = pb.memory
    rng = random.Random(lv)
    for _ in range(700):
        pb.tick(1, False)
    pb.button('start', 3)
    for _ in range(150):
        pb.tick(1, False)
    for _ in range(lv - 1):
        pb.button('down', 3)
        for _ in range(20):
            pb.tick(1, False)
    pb.button('start', 3)
    frames = foreign = 0
    floors = {'board': 0, 'court': 0}
    for f in range(8000):
        scr = 'court' if m[0x9800] == 0x82 else 'board' if m[0x9800] < 0x80 else 'menu'
        if scr != 'court' and f % 200 == 199:
            pb.button('start', 3)
        elif scr == 'court' and f % 8 == 0:
            pb.button(rng.choice(('left', 'right', 'a', 'up', 'down')), 4)
        look = f % 10 == 0 and m[0xFF40] & 0x80 and scr != 'menu'
        pb.tick(1, bool(look))
        if look:
            raw = pb.screen.image.convert('RGB').tobytes()
            px = {(raw[i] >> 3, raw[i + 1] >> 3, raw[i + 2] >> 3) for i in range(0, len(raw), 3)}
            frames += 1
            foreign += any(p not in allowed for p in px)
            floors[scr] += floor[scr] in px
    pb.stop(False)
    check(m[0xC0DF] == lv and floors['board'] and floors['court'],
          f'LEVEL {lv}: {name} on the score board and the court')
    check(foreign == 0, f'LEVEL {lv}: only its own colours ({frames - foreign}/{frames} frames)')

# ------------------------------------------------------------ 6. VRAM timing
print('GBC: writes to VRAM only in VBlank, Mario always drawn')
AUDIT = os.path.join(os.path.dirname(args.rom), 'audit.gbc')
pb = emu(AUDIT, True)
m = pb.memory
rng = random.Random(6)
for _ in range(700):
    pb.tick(1, False)
m[0xD2F2] = 0xFF                        # wAuditMinLY
cards = mario = mario_bad = 0
ends = set()
for f in range(40000):
    court = m[0x9800] == 0x82
    if not court and f % 200 == 0:
        pb.button('start', 3)
    elif court and f % 6 == 0:
        spr = [(m[0xFE00 + i], m[0xFE01 + i], m[0xFE02 + i], m[0xFE03 + i]) for i in range(0, 160, 4) if m[0xFE00 + i]]
        ball = [s for s in spr if s[2] in (0x31, 0x37, 0x38)]
        me = [s for s in spr if not s[3] & 0x10 and s[3] & 7 != 5 and s[2] not in (0x31, 0x37, 0x38, 0x22, 0x2F)]
        if ball and me and rng.random() < 0.6:
            bx, px = ball[0][1], sum(s[1] for s in me) / len(me)
            if bx < px - 8:
                pb.button('left', 3)
            elif bx > px + 8:
                pb.button('right', 3)
        if rng.random() < 0.3:
            pb.button('a', 2)           # serves at random moments: many faults
    pb.tick(1, False)
    if not (court and m[0xFF40] & 0x80):
        continue
    win = m[0xFFA6] & 0x20
    cards += bool(win and m[0x9C00 + 4 * 32 + 1] == 0xB3)
    col = 22 if m[0x9800 + 11 * 32 + 22] not in (0x80, m[0xD2F4]) else 3
    ends.add(col)
    mx, my = (col * 8 - m[0xFFA8]) & 0xFF, (12 * 8 - m[0xFFAA]) & 0xFF
    if mx <= 144 and my <= 128 and not (win and m[0xFFAC] < my + 16 and m[0xFFAB] - 7 < mx + 16):
        mario += 1
        ovl = [i for i in range(32, 40) if m[0xFE00 + i * 4]]
        lines = [[i for i in range(40) if m[0xFE00 + i * 4] and m[0xFE00 + i * 4] - 16 <= y < m[0xFE00 + i * 4] - 8]
                 for y in range(my, my + 16)]
        mario_bad += not ovl or any(i in ovl for on in lines for i in on[10:])
pb.stop(False)
check(cards > 100 and len(ends) == 2, f'match played: {cards} frames of FAULT / OUT card, both ends')
check(m[0xD2F0] == 0 and m[0xD2F1] == 0 and m[0xD2F2] >= 144,
      f'no VRAM / palette write outside VBlank ({m[0xD2F0]}), no screen left uncoloured ({m[0xD2F1]})')
check(mario > 1000 and mario_bad == 0, f'Mario drawn whole ({mario - mario_bad}/{mario} frames)')

if failures:
    print(f'\n{len(failures)} test(s) failed')
    sys.exit(1)
print('\nall tests passed')
