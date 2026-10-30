; Tennis DX - Mario's overlay sprites, added right before the OAM DMA.
;
; Mario (the umpire) is drawn with BG tiles, and a BG tile only gets four
; colours, one of them the grass. To give him a red shirt over blue
; overalls we draw the shirt pixels again as sprites on top of him.
;
; This runs inside the game's VBlank handler, so it lives in WRAM (bank 2
; is not mapped there) and must be quick: the game still has VRAM work to
; do in the same VBlank. a, bc, de, hl are free (the handler saved them).
; Two entry points: OvlVBlank (instead of the OAM DMA call, first thing in
; the handler) and OvlEnd (last thing the handler does, after the game built
; the sprites for the next frame).

MACRO CardEntry         ; hl -> y of an OAM entry; \1 = x register, \2 = tile, \3 = attribute (optional)
    inc l
    ld [hl], \1
    inc l
    ld [hl], \2
    inc l
IF _NARG > 2
    ld [hl], \3
ELSE
    ld [hl], CARD_ATTR
ENDC
    inc l
ENDM

MACRO LoadPal5          ; colours 1-3 of OBJ palette 5 = \1_0 ... \1_5 (clobbers a)
    AuditVBlank
    ld a, $80 | (5 * 8 + 2)
    ldh [rOCPS], a
    ld a, \1_0
    ldh [rOCPD], a
    ld a, \1_1
    ldh [rOCPD], a
    ld a, \1_2
    ldh [rOCPD], a
    ld a, \1_3
    ldh [rOCPD], a
    ld a, \1_4
    ldh [rOCPD], a
    ld a, \1_5
    AuditVBlank
    ldh [rOCPD], a
ENDM


MACRO ReadVRAM          ; a = [\1], waiting until the PPU lets us (not in mode 3)
.wait\@:
    ldh a, [rSTAT]
    and 3
    cp 3
    jr z, .wait\@
    ld a, [\1]
    inc a
    jr z, .wait\@           ; $FF: the PPU got there first
    dec a
ENDM

MACRO Todo              ; ask the next OvlVBlank for work that needs VBlank (clobbers a)
    ld a, [wCardTodo]
    or 1 << \1
    ld [wCardTodo], a
ENDM

; Mario (the umpire) on the court: 4 sprites on top of his 2 x 2 tiles. Runs
; before the OAM DMA, so it is written for speed: no calls, no push / pop,
; everything unrolled. Mario's head turns, so which tiles sit in the 4 map
; cells (and so which sprites they need) is looked up again every frame.
;   b = y of the row, c = x of the sprite, e = low byte of its OAM entry
MACRO WinLim            ; [wOvlLim] = the x beyond which the score / FAULT window hides sprites of row b
    ldh a, [hShadowLCDC]
    bit LCDCB_WINON, a
    jr z, .nowin\@
    ldh a, [hShadowWY]      ; window rows: WY .. WY + 40
    add 8
    cp b
    jr nc, .nowin\@
    ldh a, [hShadowWY]
    add 56
    cp b
    jr c, .nowin\@
    jr z, .nowin\@
    ldh a, [hShadowWX]
    sub 6
    jr c, .nowin\@
    dec a                   ; WX - 7
    jr .setlim\@
.nowin\@:
    ld a, $FF               ; nothing is hidden
.setlim\@:
    ld [wOvlLim], a
ENDM

MACRO MarioSprite       ; \1 = map cell of the tile under this sprite
    ld a, e
    ld hl, wOAMNext
    cp [hl]
    jr c, .next\@           ; slot used by the game: leave it alone
    ld a, [wOvlLim]
    cp c
    jr c, .hide\@           ; under the window
    ld a, [\1]
    ld l, a
    ld h, HIGH(wOvlSlot)
    ld a, [hl]              ; sprite tile for that BG tile, 0 = none
    and a
    jr z, .hide\@
    ld h, HIGH(wOvlAttr)
    ld d, [hl]
    ld h, HIGH(wShadowOAM)
    ld l, e
    ld [hl], b
    inc l
    ld [hl], c
    inc l
    inc l
    ld [hl], d              ; attribute
    dec l
    ld [hl], a              ; tile
    jr .next\@
.hide\@:
    ld h, HIGH(wShadowOAM)
    ld l, e
    xor a
    ld [hl], a
.next\@:
    ld a, e
    sub 4
    ld e, a
ENDM

MACRO MarioBody         ; \1 = map column of his left tiles (22 or 3)
    ldh a, [hShadowSCX]     ; the scroll this frame will be shown with
    ld b, a
    ld a, \1 * 8 + OAM_X_OFS
    sub b
    ld c, a                 ; OAM x of the left column
    ldh a, [hShadowSCY]
    ld b, a
    ld a, 12 * 8 + OAM_Y_OFS
    sub b
    ld b, a                 ; OAM y of the upper row
    ld e, LOW(OVL_OAM_TOP)
    WinLim
    MarioSprite _SCRN0 + 12 * 32 + \1
    ld a, c
    add 8
    ld c, a
    MarioSprite _SCRN0 + 12 * 32 + \1 + 1
    ld a, c
    sub 8
    ld c, a
    ld a, b
    add 8
    ld b, a
    WinLim
    MarioSprite _SCRN0 + 13 * 32 + \1
    ld a, c
    add 8
    ld c, a
    MarioSprite _SCRN0 + 13 * 32 + \1 + 1
ENDM

SECTION "OvlROM", ROMX, BANK[2]
OvlROM:
LOAD "OvlRAM", WRAMX[wOvlRAM]
OvlVBlank::
    ld a, [wCardTodo]       ; palette / strip work that OvlEnd asked for
    and a
    jp nz, .todo
.dispatch:
    ld a, [wOvlMode]
    and a
    jp z, hOAMDMA
    cp OVL_STATIC
    jr nz, .court

    ; ---- static sprites: copy the entries prepared at load time
    ld a, [wOAMNext]
    ld b, a
    ld a, [wOvlStaticDst]
    cp b
    jp c, hOAMDMA           ; the game needs those slots
    ld e, a
    ld d, HIGH(wShadowOAM)
    ld hl, wOvlBuf
    ld a, [wOvlStaticLen]
    rrca
    rrca
    ld c, a                 ; entries
.copy4:
REPT 4
    ld a, [hl+]
    ld [de], a
    inc e
ENDR
    dec c
    jr nz, .copy4
    jp hOAMDMA

    ; ---- court: Mario's body (2 x 2 tiles) follows the camera
.court:
    ld a, [_SCRN0 + 11 * 32 + 22]   ; Mario on the right (or left after changing ends)
    cp $80
    jp z, .left
    MarioBody 22
    jp hOAMDMA
.left:
    MarioBody 3
    jp hOAMDMA

; Work OvlEnd asked for: only VBlank lets us touch palettes and the map.
.todo:
    ld b, a
    xor a
    ld [wCardTodo], a
    bit TODO_PALCARD, b
    jr z, .t1
    LoadPal5 CARD_PAL
.t1:
    bit TODO_PALNORM, b
    jr z, .t2
    LoadPal5 PAL5_NORMAL    ; palette 5 back to what the game uses it for
.t2:
    bit TODO_STRIPON, b
    jr z, .t3
    ld a, CARD_BG_TILE
    call .stripfill
.t3:
    bit TODO_STRIPOFF, b
    jp z, .dispatch
    ld a, BLANK_TILE        ; give the strip back
    call .stripfill
    jp .dispatch

; a = tile for the 5 window cells right of the card
.stripfill:
    ld hl, _SCRN1 + CARD_STRIP_COL
    ld de, 32
REPT 5
    AuditVBlank
    ld [hl], a
    add hl, de
ENDR
    ret

; FAULT / OUT card in the window. Its light blue background shares colour 1
; with Mario's skin, so sprites on top of the portrait's tiles put the skin
; back on his face, paint the white of his bib blue and the pixels beside
; his shoulders in the umpire chair's brown; OBJ palette 5 (not used by the
; game while the card is up) holds the card's colours meanwhile. The portrait is a
; 3 x 3 block of window tiles (rows 2-4, columns 1-3); each row has its own
; sprites and is drawn only while its first tile is on the window map (the
; score box leaves single rows of the card behind):
;   row 2 (cap, 2 sprites) and row 3 (face, 3 sprites): the game's first five
;       OAM entries - it keeps them hidden (y = 0) while the card is up;
;   row 4 (collar and bib, 3 sprites): free slots CARD_OAM...
; The VBlank handler is also the game's whole frame, and its VRAM updates
; (the window map included) come right after the OAM DMA: anything slow
; before the DMA makes the game finish its map only a few tiles per frame
; and the score box shows half drawn. So OvlVBlank does almost nothing here;
; the map is looked at and the sprites are set by OvlEnd, once the game is
; done (they are DMA'd by the next OvlVBlank); the palette and the strip next
; to the card wait for that OvlVBlank, the only place with VBlank to spare
; (wCardTodo). Once drawn only the y of each
; sprite is refreshed; x, tile and attribute are redone only when the rows on
; screen, the window x or the OAM contents changed.
; The sprite tiles are the CARD_SPR_xx constants from data.inc.
; wCardMask: rows drawn (bit 0 = row 2, bit 1 = row 3, bit 2 = row 4), or 0.
; The blank window column right of the card (3 pixels stick out of the
; screen's edge) gets the card's background tile while all three rows show.


; OvlEnd: the game is done with this frame, map included (it draws it a few
; tiles at a time, while its logic runs). Sets the card's sprites; they are
; DMA'd by the next OvlVBlank.
OvlEnd::
    ld a, [wOvlMode]
    dec a                   ; OVL_COURT
    jp nz, .out
    ld d, 0                 ; d = rows of the portrait on the window map
    ldh a, [hGameState]
    dec a                   ; the rally
    jr nz, .have
    ldh a, [hShadowLCDC]
    bit LCDCB_WINON, a
    jr z, .have
    ReadVRAM _SCRN1 + 4 * 32 + 1
    cp CARD_TILE
    jr nz, .not4
    set 2, d
.not4:
    ReadVRAM _SCRN1 + 3 * 32 + 1
    cp CARD_MID_TILE
    jr nz, .not3
    set 1, d
.not3:
    ReadVRAM _SCRN1 + 2 * 32 + 1
    cp CARD_FACE_TILE
    jr nz, .not2
    set 0, d
.not2:
.have:
    ld a, d
    and a
    jp z, .cardoff
    ldh a, [hShadowWX]
    ld e, a
    ld a, [wCardMask]
    cp d
    jp nz, .redraw
    ld a, [wCardWX]
    cp e
    jp nz, .redraw
    bit 0, d                ; still our sprites?
    jr z, .ok0
    ld a, [wShadowOAM + 2]
    cp CARD_SPR_AD
    jp nz, .redraw
.ok0:
    bit 1, d
    jr z, .ok1
    ld a, [wShadowOAM + 2 * 4 + 2]
    cp CARD_SPR_B0
    jp nz, .redraw
.ok1:
    bit 2, d
    jp z, .cardy
    ld a, [CARD_OAM + 2]
    cp CARD_SPR_B3
    jp nz, .redraw
    jp .cardy

.redraw:
    ld a, e
    ld [wCardWX], a
    ld a, [wCardMask]
    and 3
    jr nz, .faceok          ; the face entries are ours already
    ld a, d
    and 3
    jr z, .faceok
    ld hl, wShadowOAM       ; newly needed: are the game's five entries hidden?
    ld a, [hl]
    ld l, 4
    or [hl]
    ld l, 8
    or [hl]
    ld l, 12
    or [hl]
    ld l, 16
    or [hl]
    jr z, .faceok
    res 0, d                ; the game uses them: no face
    res 1, d
.faceok:
    bit 2, d
    jr z, .bibok
    ld a, [wOAMNext]
    cp LOW(CARD_OAM) + 1
    jr c, .bibok
    res 2, d                ; the game needs the bib slots
.bibok:
    ld a, d
    and a
    jp z, .cardoff
    ld a, [wCardMask]
    and a
    jr nz, .palok           ; the card palette is loaded already
    Todo TODO_PALCARD
.palok:
    ld a, d
    cpl                     ; hide the rows that went away
    ld hl, wCardMask
    and [hl]
    ld b, a
    xor a
    bit 0, b
    jr z, .g0
    ld [wShadowOAM], a
    ld [wShadowOAM + 4], a
.g0:
    bit 1, b
    jr z, .g1
    ld [wShadowOAM + 2 * 4], a
    ld [wShadowOAM + 3 * 4], a
    ld [wShadowOAM + 4 * 4], a
.g1:
    bit 2, b
    jr z, .g2
    ld [CARD_OAM], a
    ld [CARD_OAM + 4], a
    ld [CARD_OAM + 8], a
.g2:
    ld a, e                 ; x of the three columns: c, b, e
    add 8 + OAM_X_OFS - 7
    ld c, a
    add 8
    ld b, a
    add 8
    ld e, a
    bit 0, d
    jr z, .w2
    ld hl, wShadowOAM
    CardEntry c, CARD_SPR_AD
    CardEntry b, CARD_SPR_AE, CARD_ATTR_AE
.w2:
    bit 1, d
    jr z, .w3
    ld hl, wShadowOAM + 2 * 4
    CardEntry c, CARD_SPR_B0
    CardEntry b, CARD_SPR_B1
    CardEntry e, CARD_SPR_B2
.w3:
    bit 2, d
    jr z, .w4
    ld hl, CARD_OAM
    CardEntry c, CARD_SPR_B3
    CardEntry b, CARD_SPR_B4
    CardEntry e, CARD_SPR_B5
.w4:
    ld a, d                 ; strip: on while all three rows show
    cp 7
    jr z, .stripon
    ld a, [wCardMask]
    cp 7
    jr nz, .stripdone       ; it was off and stays off
    Todo TODO_STRIPOFF
    jr .stripdone
.stripon:
    Todo TODO_STRIPON
.stripdone:
    ld a, d
    ld [wCardMask], a

; y of the sprites of the rows on screen
.cardy:
    ldh a, [hShadowWY]
    add 2 * 8 + OAM_Y_OFS
    ld b, a                 ; y of window row 2
    bit 0, d
    jr z, .y3
    ld [wShadowOAM], a
    ld [wShadowOAM + 4], a
.y3:
    add 8
    bit 1, d
    jr z, .y4
    ld [wShadowOAM + 2 * 4], a
    ld [wShadowOAM + 3 * 4], a
    ld [wShadowOAM + 4 * 4], a
.y4:
    add 8
    bit 2, d
    jr z, .out
    ld [CARD_OAM], a
    ld [CARD_OAM + 4], a
    ld [CARD_OAM + 8], a
.out:
    xor a                   ; what the game does here
    ldh [hBusy], a
    ret

; Nothing of the card on the window map: hide what we drew.
.cardoff:
    ld a, [wCardMask]
    and a
    jr z, .out
    ld c, a
    xor a
    ld [wCardMask], a
    bit 0, c
    jr z, .o0
    ld [wShadowOAM], a
    ld [wShadowOAM + 4], a
.o0:
    bit 1, c
    jr z, .o1
    ld [wShadowOAM + 2 * 4], a
    ld [wShadowOAM + 3 * 4], a
    ld [wShadowOAM + 4 * 4], a
.o1:
    bit 2, c
    jr z, .o2
    ld [CARD_OAM], a
    ld [CARD_OAM + 4], a
    ld [CARD_OAM + 8], a
.o2:
    Todo TODO_PALNORM
    ld a, c
    cp 7
    jr nz, .out
    Todo TODO_STRIPOFF
    jr .out

ENDL
OvlROMEnd:
