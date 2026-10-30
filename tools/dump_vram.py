#!/usr/bin/env python3
"""Snapshots the VRAM tile data of the original game for gen_data.py.

    dump_vram.py baserom.gb OUTDIR
        -> spr_board.bin, bg_board.bin, spr_court.bin, bg_court.bin
           (and map_*.bin: the BG map, for the court's surfaces)

The game keeps its graphics compressed, so they are read from an emulator
(needs pyboy) after the title screen and after the first serve. They come
from your own copy of the game and are never stored in this repository.
Tiles $2E/$2F of the score board animate, so their snapshot depends on the
frame; gen_data.py does not use them."""
import os
import sys

from pyboy import PyBoy

pb = PyBoy(sys.argv[1], window='null', sound_emulated=False)
m = pb.memory
out = sys.argv[2]
os.makedirs(out, exist_ok=True)


def run(n):
    for _ in range(n):
        pb.tick()


def save(screen):
    for kind, lo, hi in (('spr', 0x8000, 0x8800), ('bg', 0x8800, 0x9800), ('map', 0x9800, 0x9C00)):
        with open(f'{out}/{kind}_{screen}.bin', 'wb') as f:
            f.write(bytes(m[lo:hi]))


run(600)
pb.button('start')
run(150)
pb.button('start')
run(250)
save('board')
pb.button('start')
run(300)
save('court')
pb.stop(False)
