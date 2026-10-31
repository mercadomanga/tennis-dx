; Tennis DX - colorization, run each time the game turns the LCD on.
;
; The game always loads a screen with the LCD off and then calls its
; "LCD on" routine, which we hook. At that moment all of VRAM is free to
; read and write, so we:
;   1. detect the screen (title/menus, score board, court) from the map,
;   2. load its palettes and sprite tables,
;   3. write a BG attribute for every map cell from its tile number,
;   4. apply per-screen extras (the court's surface, fixed rectangles,
;      pixel patches, Mario's overlay sprites).
; On a DMG or Super Game Boy it only sends the SGB the level's palette; at
; power on it also sends the SGB its border (PowerOn).

SECTION "Colorize", ROMX, BANK[2]

; Called with LCD off, interrupts masked and bank 2 mapped.
; Preserves bc, de, hl (the original routine only used a).
ColorizeScreen::
    push bc
    push de
    push hl
    ld hl, sp+0
    ld a, h
    inc a
    jp z, PowerOn           ; stack still in HRAM: the jump at $0100, not the game
    call InstallOvlRoutine  ; on DMG too: there it only does the OAM DMA
    ldh a, [rLCDC]
    bit LCDCB_ON, a
IF DEF(VRAM_AUDIT)
    jr z, .off
    ld a, [wAuditLCDOn]
    inc a
    ld [wAuditLCDOn], a
    jr .done
.off:
ELSE
    jr nz, .done            ; never touch VRAM with the LCD on
ENDC
    call IsCGB
    jr nz, .cgb
    call DmgScreen          ; DMG / Super Game Boy (sprite tables stay 0)
    jr .done
.cgb:

    call DetectScreen       ; b = block page
    call LoadPalettes
    ld a, b
    cp HIGH(BlockBoard)
    call z, BoardSurface
    call LoadSpriteTables
    call ApplyAttributes
    ld a, b
    cp HIGH(BlockCourt)
    call z, CourtSurface
    ld a, b
    cp HIGH(BlockCourt)
    call z, CourtCrowd
    ld h, b
    ld l, LOW(BLK_LISTS)
    inc h
    inc h
    inc h                   ; hl = block + BLK_LISTS
    call ApplyOverrides
    call CopySpriteTilesToBank1
    call ApplySpritePatches
    ld c, $00               ; BG tiles: signed, VRAM bank 0
    call ApplyPixelPatches
    call LoadOverlays
    call LoadStaticSprites
    xor a
    ldh [rVBK], a
.done:
    pop hl
    pop de
    pop bc
    ret

; z = DMG (VBK reads $FF there), nz = CGB
IsCGB:
    xor a
    ldh [rVBK], a
    ldh a, [rVBK]
    inc a
    ret

; DMG and Super Game Boy (the game's own shades). On the court, the CPU's
; eyes and shoes get their white: they were transparent, and its sprite
; palette (OBP1) shows colour 2 as white (only in the tiles your player never
; uses: your palette, OBP0, has no white). And the strip right of the
; FAULT / OUT card (OVL_DMG). On a Super Game Boy,
; also the palette of the current level for the whole screen (one PAL01
; packet; the attributes stay as the SGB starts: palette 0 everywhere).
DmgScreen:
    ld a, [_SCRN0]
    cp $82                  ; court (see DetectScreen)
    jr nz, .sgb
    ld a, OVL_DMG
    ld [wOvlMode], a
    ld hl, DmgWhiteCourt
    call DmgWhite
.sgb:
    call FindSgb
    ret nz
    ld a, [wLevel]
    dec a
    cp 4
    jr c, .level
    xor a                   ; not a level yet (power on): LEVEL 1
.level:
    swap a                  ; * 16
    ld e, a
    ld d, 0
    ld hl, SgbPalPackets
    add hl, de
    jp SgbSend

; hl -> db count, then count * (db sprite tile, row, pixels): the pixels
; that are transparent in that row become colour 2 (VRAM bank 0, LCD off).
DmgWhite:
    ld a, [hl+]
    and a
    ret z
    ld c, a
.pixel:
    ld a, [hl+]             ; tile -> de = $8000 + tile * 16 + row * 2
    ld e, a
    swap a
    and $0F
    or $80
    ld d, a
    ld a, e
    swap a
    and $F0
    ld e, a
    ld a, [hl+]
    add a
    add e
    ld e, a
    ld a, [de]              ; low plane
    ld b, a
    inc de
    ld a, [de]              ; high plane
    or b
    cpl
    and [hl]                ; wanted pixels that are colour 0
    inc hl
    ld b, a
    ld a, [de]
    or b
    ld [de], a
    dec c
    jr nz, .pixel
    ret

; z = Super Game Boy. Looked for once: ask for two controllers and see
; whether the joypad register starts answering for the second one.
FindSgb:
    ld a, [wSgbFound]
    cp SGB_YES
    ret z
    cp SGB_NO
    jr z, .no
    ld hl, SgbMlt2
    call SgbSend
    call SgbWait
    ld b, SGB_NO
    ld c, 4                 ; a few reads after each change, as the docs advise
.read:
    ld a, $20               ; pulse P14 and P15: next controller
    ldh [rP1], a
    ldh a, [rP1]
    ldh a, [rP1]
    ld a, $30
    ldh [rP1], a
    ld a, $10
    ldh [rP1], a
    ldh a, [rP1]
    ldh a, [rP1]
    ldh a, [rP1]
    ldh a, [rP1]
    ld a, $30
    ldh [rP1], a
    ldh a, [rP1]
    ldh a, [rP1]
    ldh a, [rP1]
    ldh a, [rP1]
    and $03
    cp $03
    jr z, .next
    ld b, SGB_YES           ; controller 2 answered ($E)
.next:
    dec c
    jr nz, .read
    ld a, b
    ld [wSgbFound], a
    cp SGB_YES
    ret nz
    ld hl, SgbMlt1          ; back to one controller
    call SgbSend
    call SgbWait
    xor a                   ; z
    ret
.no:
    or a                    ; nz
    ret

; Power on, from the jump at $0100 (bank 2 mapped, interrupts off, LCD on as
; the boot ROM leaves it). On a Super Game Boy: send our border. Then start
; the game as the cartridge did: $0150 with bank 1 mapped.
PowerOn:
    call IsCGB
    jr nz, .start
    ld hl, FarCopyCode
    ld de, FarCopy
    ld c, FarCopyCodeEnd - FarCopyCode
.far:
    ld a, [hl+]
    ld [de], a
    inc de
    dec c
    jr nz, .far
    call SgbWait            ; give the SGB a moment after power on
    call SgbWait
    xor a
    ld [wSgbFound], a       ; RAM is random at power on
    call FindSgb
    call z, SgbBorder
    xor a                   ; look again at the first screen (palettes), whatever we found
    ld [wSgbFound], a
.start:
    ld sp, $FFFE
    ld hl, StartStub
    ld de, _RAM
    ld c, StartStubEnd - StartStub
.copy:
    ld a, [hl+]
    ld [de], a
    inc de
    dec c
    jr nz, .copy
    jp _RAM

; Runs from WRAM: switching to bank 1 here would pull bank 2's code away.
StartStub:
    ld a, 1
    ld [$2000], a
    jp $0150
StartStubEnd:

; The border goes through VRAM: the SGB copies what the screen shows, a
; frame after the packet (tiles: CHR_TRN; map and palette: PCT_TRN).
; The TV keeps the last picture meanwhile (MASK_EN freeze).
SgbBorder:
    ld hl, SgbMaskFreeze
    call SgbSend
    call SgbWait
    call LcdOff
    ld hl, _SCRN0           ; tiles 0-255 in reading order on the screen (20 x 13)
    xor a
    ld c, 13
.row:
    ld b, 20
.col:
    ld [hl+], a
    inc a
    dec b
    jr nz, .col
    ld de, 12
    add hl, de
    dec c
    jr nz, .row
    ld a, %11100100         ; shades as they are
    ldh [rBGP], a
    ; tiles
    ld hl, _VRAM
    ld bc, $1000
    call Clear
    ld hl, SgbBorderTiles
    ld de, _VRAM
    ld bc, SgbBorderTilesEnd - SgbBorderTiles
    call FarCopy
    ld hl, SgbChrTrn
    call SgbTransfer
    ; map and palette 4
    ld hl, _VRAM
    ld bc, $1000
    call Clear
    ld hl, SgbBorderMap
    ld de, _VRAM
    ld bc, SgbBorderMapEnd - SgbBorderMap
    call FarCopy
    ld hl, SgbBorderPal
    ld de, _VRAM + $800
    ld bc, SgbBorderPalEnd - SgbBorderPal
    call FarCopy
    ld hl, SgbPctTrn
    call SgbTransfer
    ; a blank screen for the game to start from
    ld hl, _VRAM
    ld bc, $2000
    call Clear
    ld a, LCDCF_ON | LCDCF_BGON
    ldh [rLCDC], a
    ld hl, SgbMaskOff
    call SgbSend
    jp SgbWait

; In: hl -> packet. Shows the prepared VRAM, sends the packet, waits, LCD off.
SgbTransfer:
    ld a, LCDCF_ON | LCDCF_BG8000 | LCDCF_BGON
    ldh [rLCDC], a
    push hl
    call SgbWait
    pop hl
    call SgbSend
    call SgbWait
    call SgbWait
LcdOff:
    ldh a, [rLCDC]
    bit LCDCB_ON, a
    ret z
.wait:
    ldh a, [rLY]
    cp 144
    jr c, .wait
    xor a
    ldh [rLCDC], a
    ret

; hl = destination, bc = bytes
Clear:
    xor a
    ld [hl+], a
    dec bc
    ld a, b
    or c
    jr nz, Clear
    ret

; hl = source in bank 3 (the border), de = destination, bc = bytes.
; Copied to WRAM at power on and run from there: switching banks here
; would pull this code away.
DEF FarCopy EQU _RAM + $10
FarCopyCode:
    ld a, BANK(SgbBorderTiles)
    ld [$2000], a
.loop:
    ld a, [hl+]
    ld [de], a
    inc de
    dec bc
    ld a, b
    or c
    jr nz, .loop
    ld a, BANK(@)
    ld [$2000], a
    ret
FarCopyCodeEnd:

SgbMaskFreeze:
    db $B9, $01, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
SgbMaskOff:
    db $B9, $00, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
SgbChrTrn:                  ; border tiles $00-$7F
    db $99, $00, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
SgbPctTrn:
    db $A1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0

; About 4 frames: the SGB reads a packet only that often.
SgbWait:
    ld bc, 10500
.loop:
    dec bc
    ld a, b
    or c
    jr nz, .loop
    ret

SgbMlt2:
    db $89, $01, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
SgbMlt1:
    db $89, $00, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0

; In: hl -> 16-byte packet. Sent through the joypad register:
; a 0 bit pulls P14 low, a 1 bit P15, each followed by both high.
SgbSend:
    xor a                   ; reset pulse
    ldh [rP1], a
    ld a, $30
    ldh [rP1], a
    ld b, 16
.byte:
    ld e, 8
    ld d, [hl]
    inc hl
.bit:
    ld a, $10
    srl d
    jr c, .one
    ld a, $20
.one:
    ldh [rP1], a
    ld a, $30
    ldh [rP1], a
    dec e
    jr nz, .bit
    dec b
    jr nz, .byte
    ld a, $20               ; stop bit (0)
    ldh [rP1], a
    ld a, $30
    ldh [rP1], a
    ret

; Out: b = page of the screen's data block
DetectScreen:
    ld a, [_SCRN0]
    ld b, HIGH(BlockCourt)
    cp $82                  ; court: stadium corner
    ret z
    ld b, HIGH(BlockBoard)
    cp $80                  ; score board / end screen: frame tiles $00-$07
    ret c
    ld b, HIGH(BlockMenu)   ; title and level select: tiles $80+
    ret

; Copies the VBlank routine to WRAM and resets the overlay state.
InstallOvlRoutine:
    ld hl, OvlROM
    ld de, wOvlRAM
    ld bc, OvlROMEnd - OvlROM
.copy:
    ld a, [hl+]
    ld [de], a
    inc de
    dec bc
    ld a, b
    or c
    jr nz, .copy
    xor a
    ld [wOvlMode], a
    ld [wCardMask], a
    ld [wCardTodo], a
    ld [wZoneRows], a
    ld [wZoneCol], a
    ld a, BLANK_TILE
    ld [wZoneTile], a       ; (the empty spot reads as floor either way)
    xor a
    ld hl, wOvlSlot
.clear:
    ld [hl+], a
    inc l
    dec l
    jr nz, .clear
    ret

; In: b = block page
LoadPalettes:
    ld h, b
    inc h
    inc h
    inc h
    ld l, LOW(BLK_BG_PALS)
    ld a, BCPSF_AUTOINC
    ldh [rBCPS], a
    ld c, 64
.bg:
    ld a, [hl+]
    ldh [rBCPD], a
    dec c
    jr nz, .bg
    ld a, OCPSF_AUTOINC
    ldh [rOCPS], a
    ld c, 64
.obj:
    ld a, [hl+]
    ldh [rOCPD], a
    dec c
    jr nz, .obj
    ret

; Both 256-byte sprite tables -> wObjPal0/wObjPal1 (read by SprHook1/2).
LoadSpriteTables:
    ld h, b
    inc h
    ld l, 0
    ld de, wObjPal0
    ld c, 0
.loop:
    ld a, [hl+]
    ld [de], a
    inc de
    ld a, [hl+]
    ld [de], a
    inc de
    dec c
    jr nz, .loop
    ret

; Attribute of every cell of both maps = table[tile].
ApplyAttributes:
    ld h, b
    ld de, _SCRN0
.loop:
    xor a
    ldh [rVBK], a
    ld a, [de]
    ld l, a
    ld a, 1
    ldh [rVBK], a
    ld a, [hl]
    ld [de], a
    inc de
    ld a, d
    cp HIGH(_SCRN1 + $400)
    jr nz, .loop
    ret                     ; VBK = 1

; The court's floor depends on the level (palettes.py, LEVELS): grass keeps
; the block's palettes and gets mowing stripes; the other surfaces load their
; own palettes and, when the outside of the court has its own colour, draw
; it from VRAM bank 1.
; Out: VBK = 1
CourtSurface:
    call CourtTexture
    call SurfaceOfLevel
    jp z, CourtStripes
    push bc
    ld a, [hl+]             ; kind
    push af
    ld a, BCPSF_AUTOINC
    ldh [rBCPS], a
    ld c, 64
.bg:
    ld a, [hl+]
    ldh [rBCPD], a
    dec c
    jr nz, .bg
    ld a, OCPSF_AUTOINC | (4 * 8)
    ldh [rOCPS], a
    ld c, 8
.obj:
    ld a, [hl+]
    ldh [rOCPD], a
    dec c
    jr nz, .obj
    pop af
    cp SURF_INOUT
    jr nz, .done
    ld hl, CourtInOut
    call InOutTiles
    call InOutRemaps
    call InOutCells
.done:
    ld a, 1
    ldh [rVBK], a
    pop bc
    ret

; Dotted floor on the levels that have it (LevelTexture): a copy of the
; plain floor tile with a few dots of colour 2 in a spare tile number, and
; the floor cells pointed at it. Before the grass stripes, so their bank-1
; copies (colour 0 -> 2) keep the dark rows plain. Mario's two spots get
; their palettes from fixed rectangles and he is drawn after this: the spot
; he leaves empty is dotted later, in VBlank (wZoneRows, TODO_ZONE).
CourtTexture:
    ld a, [wLevel]
    dec a
    cp 4
    ret nc
    ld e, a
    ld d, 0
    ld hl, LevelTexture
    add hl, de
    ld a, [hl]
    and a
    ret z
    ld [wZoneRows], a
    xor a
    ldh [rVBK], a
    ld hl, FloorDots
    ld a, [hl+]
    push af
    ld a, [hl]
    ld [wZoneTile], a       ; the first (only) dotted tile
    pop af
.tile:
    and a
    jr z, .cells
    push af
    ld a, [hl+]
    call BGTileAddr
    ld c, 16
.copy:
    ld a, [hl+]
    ld [de], a
    inc de
    dec c
    jr nz, .copy
    pop af
    dec a
    jr .tile
.cells:
    ld a, [hl+]
    ld e, a
    ld a, [hl+]
    ld d, a
    or e
    ret z
    ld a, [hl+]
    ld c, a
    ld a, [hl+]
.fill:
    ld [de], a
    inc de
    dec c
    jr nz, .fill
    jr .cells

; Out: hl -> surface entry of the level (its kind byte), z = grass
SurfaceOfLevel:
    ld a, [wLevel]
    dec a
    cp 4
    jr c, .level
    ld a, SURF_FALLBACK
.level:
    add a
    add LOW(LevelSurfaces)
    ld l, a
    adc HIGH(LevelSurfaces)
    sub l
    ld h, a
    ld a, [hl+]
    ld h, [hl]
    ld l, a
    ld a, [hl]
    cp SURF_GRASS
    ret

; Score board before a match: the floor and wall of the court of the level.
BoardSurface:
    push bc
    call SurfaceOfLevel
    jr z, .done
    ld de, SURF_BOARD
    add hl, de
    ld a, BCPSF_AUTOINC
    ldh [rBCPS], a
    ld c, 64
.bg:
    ld a, [hl+]
    ldh [rBCPD], a
    dec c
    jr nz, .bg
    ld a, OCPSF_AUTOINC | (5 * 8)
    ldh [rOCPS], a
    ld c, 16
.obj:
    ld a, [hl+]
    ldh [rOCPD], a
    dec c
    jr nz, .obj
.done:
    pop bc
    ret

; Crowd in front of and behind the court: their clothes, colour 2 like
; their hair, are drawn from bank-1 copies with them in colour 0 (gen_data.py,
; CrowdClothes). Out: VBK = 1
CourtCrowd:
    push bc
    ld hl, CrowdClothes
    call ClearTiles
    call InOutCells
    pop bc
    ret

; db count, then count * (db tile, 8 row masks): the bank-1 copy of the tile
; with the masked pixels in colour 0. In: hl -> list. Out: hl after it
ClearTiles:
    ld a, [hl+]
.tile:
    and a
    ret z
    push af
    ld a, [hl+]
    call BGTileAddr
    ld b, 8
.row:
    xor a
    ldh [rVBK], a
    ld a, [hl+]
    cpl
    ld c, a                 ; c = pixels kept
    ld a, [de]
    and c
    push af                 ; low plane
    inc de
    ld a, [de]
    and c
    ld c, a                 ; high plane
    ld a, 1
    ldh [rVBK], a
    ld a, c
    ld [de], a
    dec de
    pop af
    ld [de], a
    inc de
    inc de
    dec b
    jr nz, .row
    pop af
    dec a
    jr .tile

; a = BG tile number -> de = its data ($00-$7F at $9000, $80-$FF at $8800)
BGTileAddr:
    ld e, a
    swap a
    and $0F
    bit 7, e
    jr nz, .high
    add $10
.high:
    or $80
    ld d, a
    ld a, e
    swap a
    and $F0
    ld e, a
    ret

; db count, then count * (db destination, source, 8 row masks): the bank-1
; copy of the source tile with the floor (colour 0) of the masked pixels
; turned into colour 2. In: hl -> list. Out: hl after it
InOutTiles:
    ld a, [hl+]
.tile:
    and a
    ret z
    push af
    ld a, [hl+]
    call BGTileAddr
    ld b, d
    ld c, e                 ; bc = destination, bank 1
    ld a, [hl+]
    call BGTileAddr         ; de = source, bank 0
    ld a, 8
.row:
    push af
    xor a
    ldh [rVBK], a
    ld a, [de]
    cpl
    and [hl]                ; masked pixels that are not colour 1 or 3 ...
    inc hl
    push hl
    ld h, a
    ld a, [de]
    ld l, a                 ; l = low plane, unchanged
    inc de
    ld a, [de]
    inc de
    or h                    ; ... get the high bit: 0 -> 2 (2 stays 2)
    ld h, a
    ld a, 1
    ldh [rVBK], a
    ld a, l
    ld [bc], a
    inc bc
    ld a, h
    ld [bc], a
    inc bc
    pop hl
    pop af
    dec a
    jr nz, .row
    pop af
    dec a
    jr .tile

; db count, then count * (dw map address, db tile): cells of a tile that
; needs a second copy. In: hl -> list. Out: hl after it
InOutRemaps:
    xor a
    ldh [rVBK], a
    ld a, [hl+]
    and a
    ret z
    ld c, a
.cell:
    ld a, [hl+]
    ld e, a
    ld a, [hl+]
    ld d, a
    ld a, [hl+]
    ld [de], a
    dec c
    jr nz, .cell
    ret

; (dw map address, db length) ... dw 0: cells drawn from VRAM bank 1
InOutCells:
    ld a, 1
    ldh [rVBK], a
.run:
    ld a, [hl+]
    ld e, a
    ld a, [hl+]
    ld d, a
    or e
    ret z
    ld c, [hl]
    inc hl
.cell:
    ld a, [de]
    or OAMF_BANK1           ; same bit as BG attribute "VRAM bank 1"
    ld [de], a
    inc de
    dec c
    jr nz, .cell
    jr .run

; Mowing stripes: VRAM bank 1 gets every BG tile with colour 0 turned into
; colour 2 (dark grass in palettes 0 and 1); rows 4-5, 8-9 ... 24-25 use it.
CourtStripes:
    push bc
    ld hl, _VRAM8800
.tile:
    xor a
    ldh [rVBK], a
    ld a, [hl+]
    ld c, a                 ; low plane
    ld a, [hl-]
    ld b, a                 ; high plane
    ld a, c
    cpl
    or b                    ; colour 0 -> 2, others unchanged
    ld b, a
    ld a, 1
    ldh [rVBK], a
    ld a, c
    ld [hl+], a
    ld a, b
    ld [hl+], a
    ld a, h
    cp HIGH(_SCRN0)
    jr nz, .tile
    ld hl, _SCRN0 + 3 * 32  ; VBK = 1: flag the cells of the dark rows
    ld d, 3
.row:
    bit 1, d
    jr nz, .light
    ld e, 32
.cell:
    ld a, [hl]
    cp 2                    ; floor / lines (0) and walls (1) only
    jr nc, .skip
    or OAMF_BANK1           ; same bit as BG attribute "VRAM bank 1"
    ld [hl], a
.skip:
    inc hl
    dec e
    jr nz, .cell
    jr .next
.light:
    ld bc, 32
    add hl, bc
.next:
    inc d
    ld a, d
    cp 28
    jr nz, .row
    pop bc
    ret

; Fixed rectangles (things the game draws after the LCD is on).
; List: dw map address, db width, db attribute ... dw 0
; In/out: hl -> list, VBK = 1
ApplyOverrides:
    ld a, [hl+]
    ld e, a
    ld a, [hl+]
    ld d, a
    or e
    ret z
    ld a, [hl+]
    ld c, a
    ld a, [hl+]
.fill:
    ld [de], a
    inc de
    dec c
    jr nz, .fill
    jr ApplyOverrides

CopySpriteTilesToBank1:
    push hl
    ld hl, _VRAM8000
.loop:
    xor a
    ldh [rVBK], a
    ld a, [hl]
    ld c, a
    ld a, 1
    ldh [rVBK], a
    ld a, c
    ld [hl+], a
    ld a, h
    cp HIGH(_VRAM8800)
    jr nz, .loop
    pop hl
    ret

; Sprite tile patches, XORed into the bank-1 copies:
;   db tile, checksum low, checksum high, row count, then per row: db row, low mask, high mask
;   ... db $FF
; A tile is only patched if the 16-bit sum of its bytes in bank 0 is the
; checksum: in a 2-player game the players' tiles hold other drawings, and
; patches made for one drawing would spoil another.
; In: hl -> list. Out: hl after the list.
ApplySpritePatches:
.tile:
    ld a, [hl+]
    cp $FF
    ret z
    ld e, a
    swap a
    and $0F
    or $80
    ld d, a
    ld a, e
    swap a
    and $F0
    ld e, a                 ; de = tile data
    xor a
    ldh [rVBK], a
    push hl
    ld h, d
    ld l, e
    ld bc, 0
    ld a, 16
.sum:
    push af
    ld a, [hl+]
    add c
    ld c, a
    jr nc, .nocarry
    inc b
.nocarry:
    pop af
    dec a
    jr nz, .sum
    pop hl
    ld a, [hl+]
    cp c
    jr nz, .mismatch_lo
    ld a, [hl+]
    cp b
    jr nz, .mismatch_hi
    ld a, 1
    ldh [rVBK], a
    ld a, [hl+]
    ld b, a                 ; row count
.row:
    ld a, [hl+]
    add a
    add e
    ld c, a                 ; low byte of the row address
    push de
    ld e, c
    ld a, [de]
    xor [hl]
    ld [de], a
    inc hl
    inc e
    ld a, [de]
    xor [hl]
    ld [de], a
    inc hl
    pop de
    dec b
    jr nz, .row
    jr .tile
.mismatch_lo:
    inc hl                  ; skip the checksum's high byte
.mismatch_hi:
    ld a, [hl+]             ; row count: skip its rows
    ld b, a
.skip:
    inc hl
    inc hl
    inc hl
    dec b
    jr nz, .skip
    jr .tile

; BG pixel masks: db tile, row, low mask, high mask ... db $FF
; In: hl -> list, c = $80 for sprite tiles in VRAM bank 1,
;                 $00 for BG tiles (signed numbers) in VRAM bank 0
; Out: hl after the list
ApplyPixelPatches:
    ld a, c
    rlca                    ; bit 7 -> bit 0 = VRAM bank
    and 1
    ldh [rVBK], a
.loop:
    ld a, [hl+]
    cp $FF
    ret z
    ld e, a                 ; tile
    swap a
    and $0F
    bit 7, c
    jr nz, .unsigned
    bit 7, e
    jr nz, .unsigned        ; $80-$FF live at $8800 either way
    add $10                 ; $00-$7F live at $9000 for BG
.unsigned:
    or $80
    ld d, a
    ld a, e
    swap a
    and $F0
    ld e, a
    ld a, [hl+]             ; row
    add a
    add e
    ld e, a
    ld a, [de]
    or [hl]                 ; OR: BG tiles are patched in place, maybe more than once
    ld [de], a
    inc hl
    inc de
    ld a, [de]
    or [hl]
    ld [de], a
    inc hl
    jr .loop

; db mode, count, then count * (db BG tile, sprite slot, OAM attr, 16 bytes)
LoadOverlays:
    ld a, [hl+]
    ld b, a                 ; mode
    ld a, [hl+]
    and a
    ret z
    ld c, a
    ld a, b
    ld [wOvlMode], a
.entry:
    ld a, [hl+]             ; BG tile
    ld e, a
    ld d, HIGH(wOvlSlot)
    ld a, [hl+]             ; sprite slot
    ld [de], a
    ld b, a
    ld d, HIGH(wOvlAttr)
    ld a, [hl+]
    ld [de], a
    ld a, b                 ; de = $8000 + slot * 16, VRAM bank 1
    swap a
    and $0F
    or $80
    ld d, a
    ld a, b
    swap a
    and $F0
    ld e, a
    ld a, 1
    ldh [rVBK], a
    ld b, 16
.copy:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .copy
    dec c
    jr nz, .entry
    ld a, [wOvlMode]
    cp OVL_STATIC
    ret nz
    push hl
    call PrepareBoardOverlay
    pop hl
    ret

; Score screen: Mario sits still at cols 9-10, rows 10-13, so his overlay
; entries are built once here (the VBlank routine just copies them).
PrepareBoardOverlay:
    ld a, 8 * 4
    ld [wOvlStaticLen], a
    ld a, LOW(OVL_OAM_BASE)
    ld [wOvlStaticDst], a
    xor a
    ldh [rVBK], a
    ld hl, _SCRN0 + 10 * 32 + 9
    ld de, wOvlBuf
    ld b, 10 * 8 + OAM_Y_OFS
.row:
    ld c, 9 * 8 + OAM_X_OFS
    call .entry
    inc hl
    ld c, 10 * 8 + OAM_X_OFS
    call .entry
    ld a, l
    add 31
    ld l, a
    jr nc, .nc
    inc h
.nc:
    ld a, b
    add 8
    ld b, a
    cp 14 * 8 + OAM_Y_OFS
    jr nz, .row
    ret
.entry:                     ; b = y, c = x, hl -> map cell, de -> buffer
    push hl
    ld l, [hl]
    ld h, HIGH(wOvlSlot)
    ld a, [hl]
    and a
    jr z, .hidden
    push af
    ld a, b
    ld [de], a
    inc e
    ld a, c
    ld [de], a
    inc e
    pop af
    ld [de], a
    inc e
    ld h, HIGH(wOvlAttr)
    ld a, [hl]
    ld [de], a
    inc e
    pop hl
    ret
.hidden:                    ; y = 0 -> off screen
    ld [de], a
    inc e
    ld [de], a
    inc e
    ld [de], a
    inc e
    ld [de], a
    inc e
    pop hl
    ret

; Fixed sprites, e.g. the "DX" on the title screen.
; db first map tile required (screen check), count (<= OVL_STATIC_MAX),
;    then count * (db y, x, sprite slot, OAM attr, 16 bytes of tile data)
; They go to the last count OAM slots.
LoadStaticSprites:
    ld a, [hl+]
    ld b, a
    ld a, [hl+]
    and a
    ret z
    ld c, a
    ld a, [_SCRN0]
    cp b
    ret nz                  ; another screen sharing this block
    ld a, OVL_STATIC
    ld [wOvlMode], a
    ld a, c
    add a
    add a
    ld [wOvlStaticLen], a
    cpl
    inc a
    add LOW(wShadowOAM) + OAM_COUNT * 4
    ld [wOvlStaticDst], a
    ld de, wOvlBuf
.entry:
    ld a, [hl+]             ; y
    ld [de], a
    inc e
    ld a, [hl+]             ; x
    ld [de], a
    inc e
    ld a, [hl+]             ; slot
    ld [de], a
    inc e
    ld b, a
    ld a, [hl+]             ; attribute
    ld [de], a
    inc e
    push de
    ld a, b                 ; tile data -> $8000 + slot * 16, VRAM bank 1
    swap a
    and $0F
    or $80
    ld d, a
    ld a, b
    swap a
    and $F0
    ld e, a
    ld a, 1
    ldh [rVBK], a
    ld b, 16
.copy:
    ld a, [hl+]
    ld [de], a
    inc de
    dec b
    jr nz, .copy
    pop de
    dec c
    jr nz, .entry
    ret
