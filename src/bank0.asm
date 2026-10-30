; Tennis DX - original ROM with small hooks patched in.
;
; Banks 0 and 1 are the original game byte for byte, except for the
; sections below. Every hook is safe on a DMG: the tables it reads are
; kept at zero there, and DMG ignores the CGB-only attribute bits anyway.

; Same code at $7FE3 in banks 1 and 2: switching the ROM bank in the
; middle of it keeps executing the same instructions.
MACRO BANK_TRAMPOLINE
LCDOnHook\1:
    ldh a, [rIE]            ; nothing may interrupt while bank 2 is mapped
    push af
    xor a
    ldh [rIE], a
    ld a, BANK(ColorizeScreen)
    ld [$2000], a
    call ColorizeScreen
    ld a, 1
    ld [$2000], a
    pop af
    ldh [rIE], a
    ldh a, [hShadowLCDC]    ; original first two instructions
    set 7, a
    jp LCDOn_Resume
ENDM

; ---------------------------------------------------------------- bank 0
SECTION "rom0_0000", ROM0[$0000]
    INCBIN "baserom.gb", $0000, $0032

SECTION "rom0_SprHook2", ROM0[$0032]   ; unused bytes before RST $38
; Sprite builder 2 copies the attribute byte as is (nothing to XOR).
SprHook2:
    push bc
    ld c, a                 ; tile
    xor a
    jp SprAttr

SECTION "rom0_0038", ROM0[$0038]
    INCBIN "baserom.gb", $0038, SprBuild1_Tile - $0038

SECTION "rom0_SprBuild1", ROM0[SprBuild1_Tile]
    ld a, [hl+]             ; tile
    ld [de], a
    inc e
    call SprHook1
    jr @+3                  ; continue at $009F
    nop

SECTION "rom0_009F", ROM0[$009F]
    INCBIN "baserom.gb", $009F, $00E7 - $009F

SECTION "rom0_SprHook1", ROM0[$00E7]   ; unused bytes before the header
; Sprite builder 1: attribute = [hSprXorAttr] ^ data. Adds the CGB palette
; (and VRAM bank) bits for this tile from wObjPal0/1.
; The table is picked by the OBP bit of the sprite data, not of the result:
; the second console of a 2-player game sets hSprXorAttr to $10 and so
; swaps every sprite's DMG palette, but each player keeps its colours.
; In: a = tile, hl -> attribute in data, de -> attribute in shadow OAM.
SprHook1:
    push bc
    ld c, a
    ldh a, [hSprXorAttr]
; In: a = value to XOR, c = tile, hl -> attribute in data.
SprAttr:
    xor [hl]
    bit OAMB_PAL1, [hl]     ; DMG palette OBP1 in the data -> second table
    inc hl
    push hl
    ld l, c
    ld h, HIGH(wObjPal0)
    jr z, .obp0
    inc h
.obp0:
    or [hl]
    pop hl
    pop bc
    ld [de], a
    inc e
    ret

SECTION "rom0_0100", ROM0[$0100]
    nop                     ; power on: through the bank trampoline (ColorizeScreen
    jp LCDOnHook1           ; sees the boot stack), then the game's own start at $0150

SECTION "rom0_0104", ROM0[$0104]
    INCBIN "baserom.gb", $0104, VBlank_DMACall - $0104

SECTION "rom0_VBlankDMA", ROM0[VBlank_DMACall]
    call OvlVBlank          ; Mario's overlay sprites, then the OAM DMA

SECTION "rom0_01FF", ROM0[VBlank_DMACall + 3]
    INCBIN "baserom.gb", VBlank_DMACall + 3, VBlank_End - (VBlank_DMACall + 3)

SECTION "rom0_VBlankEnd", ROM0[VBlank_End]
    call OvlEnd             ; the FAULT / OUT card's sprites; then the original two instructions

SECTION "rom0_023A", ROM0[VBlank_End + 3]
    INCBIN "baserom.gb", VBlank_End + 3, LCDOn_Orig - (VBlank_End + 3)

SECTION "rom0_LCDOn", ROM0[LCDOn_Orig]
    jp LCDOnHook1

SECTION "rom0_2F72", ROM0[LCDOn_Orig + 3]
    INCBIN "baserom.gb", LCDOn_Orig + 3, SprBuild2_Attr - (LCDOn_Orig + 3)

SECTION "rom0_SprBuild2", ROM0[SprBuild2_Attr]
    call SprHook2

SECTION "rom0_3085", ROM0[SprBuild2_Attr + 3]
    INCBIN "baserom.gb", SprBuild2_Attr + 3, $4000 - (SprBuild2_Attr + 3)

; ---------------------------------------------------------------- bank 1
SECTION "rom1", ROMX[$4000], BANK[1]
    INCBIN "baserom.gb", $4000, $7FE3 - $4000

SECTION "rom1_tramp", ROMX[$7FE3], BANK[1]  ; unused tail of bank 1
    BANK_TRAMPOLINE 1

SECTION "rom2_tramp", ROMX[$7FE3], BANK[2]
    BANK_TRAMPOLINE 2
