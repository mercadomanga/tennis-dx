#!/usr/bin/env python3
"""Static checks on the built ROM: the original game is untouched outside
the known hook sites, the bank trampolines match, the header is right."""
import sys

rom = open(sys.argv[1], 'rb').read()
base = open(sys.argv[2], 'rb').read()
errors = []

# Allowed differences in the first 32 KiB: hook sites (see src/bank0.asm),
# header flags and checksums.
ALLOWED = [
    (0x0032, 0x0038),   # SprHook2 (unused bytes)
    (0x0096, 0x009F),   # sprite builder 1 call
    (0x00E7, 0x0100),   # SprHook1 (unused bytes)
    (0x0102, 0x0104),   # entry point: power-on hook (Super Game Boy border)
    (0x0143, 0x0147),   # CGB flag, new licensee code, SGB flag
    (0x0147, 0x0149),   # cartridge type, ROM size
    (0x014B, 0x014C),   # old licensee $33: the SGB flag counts
    (0x014D, 0x0150),   # checksums
    (0x01FC, 0x01FF),   # VBlank: OAM DMA call
    (0x0237, 0x023A),   # VBlank: end of the handler
    (0x2F6F, 0x2F72),   # LCD on
    (0x3082, 0x3085),   # sprite builder 2 call
    (0x7FE3, 0x8000),   # trampoline (unused tail of bank 1)
]
for i in range(0x8000):
    if rom[i] != base[i] and not any(a <= i < b for a, b in ALLOWED):
        errors.append(f'unexpected change at ${i:04X}')
        if len(errors) > 10:
            break

if rom[0x7FE3:0x8000] != rom[0xBFE3:0xC000]:
    errors.append('bank 1 and bank 2 trampolines differ')
if rom[0x143] != 0x80:
    errors.append('CGB flag is not $80 (GB + GBC)')
if rom[0x146] != 0x03 or rom[0x14B] != 0x33:
    errors.append('Super Game Boy flags missing ($146 = $03, $14B = $33)')
if rom[0x147] != 0x19 or rom[0x148] != 0x01:
    errors.append('cartridge should be MBC5, 64 KiB')
if len(rom) != 0x10000:
    errors.append(f'ROM size is {len(rom)}')

if errors:
    print('check_rom: ' + '\n  '.join(errors))
    sys.exit(1)
print(f'check_rom: OK ({sum(1 for i in range(0x8000) if rom[i] != base[i])} bytes changed in banks 0-1)')
