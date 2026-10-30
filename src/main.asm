; Tennis DX - Game Boy Color colorization of Tennis (Nintendo, 1989)
;
; Build: make   (needs RGBDS 0.8, Python 3 and the original ROM as baserom.gb)

INCLUDE "hardware.inc"
INCLUDE "defs.inc"

INCLUDE "bank0.asm"
INCLUDE "colorize.asm"
INCLUDE "data.inc"
INCLUDE "vblank.asm"

ASSERT wOvlRAM + (OvlROMEnd - OvlROM) <= $DD00, "VBlank routine runs into the game's WRAM"
ASSERT LOW(BLK_LISTS) == $80 && HIGH(BLK_LISTS) == 3, "screen block layout changed"
