; Tennis DX - shared definitions
;
; Addresses inside the original game (Tennis, 1989, ROM-only 32 KiB):

DEF hShadowLCDC     EQU $FFA6   ; game's copy of LCDC
DEF hShadowSCX      EQU $FFA8   ; copied to SCX later in the same VBlank
DEF hShadowSCY      EQU $FFAA   ; copied to SCY later in the same VBlank
DEF hShadowWX       EQU $FFAB   ; copied to WX later in the same VBlank
DEF hShadowWY       EQU $FFAC   ; copied to WY later in the same VBlank
; (rLCDC itself has the window bit cleared mid-frame by the game's STAT
; handler, so VBlank code must look at hShadowLCDC.)
DEF hSprXorAttr     EQU $FFEB   ; attribute XOR used by sprite builder 1
DEF wShadowOAM      EQU $DE00   ; copied to OAM by DMA every VBlank
DEF wOAMNext        EQU $DEA0   ; next free byte in wShadowOAM (game's fill pointer)
DEF hOAMDMA         EQU $FF80   ; game's OAM DMA routine in HRAM

DEF LCDOn_Orig      EQU $2F6F   ; "turn LCD on" routine we hook
DEF LCDOn_Resume    EQU $2F73   ; ...and where we resume it
DEF SprBuild1_Tile  EQU $0096   ; builder 1: tile + attribute writes
DEF SprBuild2_Attr  EQU $3082   ; builder 2: attribute write
DEF VBlank_DMACall  EQU $01FC   ; "call OAM DMA" inside the VBlank handler
DEF VBlank_End      EQU $0237   ; last thing the handler does: "xor a, ldh [hBusy], a"
DEF hGameState      EQU $FF8B   ; 1 = the rally
DEF wLevel          EQU $C0DF   ; level 1-4: chosen in the menu (a win preselects the next one)
DEF hBusy           EQU $FF8C   ; non-zero while the VBlank handler runs (it is not re-entrant)

; ---------------------------------------------------------------------------
; Our WRAM. The game only uses $C000-$C0FF and $DD00-$DFFF (and clears all
; of WRAM at boot), so $D000-$DCFF is free.

DEF wObjPal0        EQU $D000   ; [256] sprite tile -> CGB attr bits 0-3 (OBP0 sprites)
DEF wObjPal1        EQU $D100   ; [256] same for OBP1 sprites
DEF wOvlRAM         EQU $D600   ; VBlank overlay routine (copied from ROM)
DEF wCardMask       EQU $D2FA   ; FAULT / OUT card: rows of the portrait drawn as sprites (bits 0-2), 0 = none
DEF wCardWX         EQU $D2FB   ; window x they were drawn for
; VRAM_AUDIT builds only (make audit): counters of writes the PPU could drop
DEF wAuditLY        EQU $D2F0   ; VRAM / palette writes outside VBlank (LY < 144)
DEF wAuditLCDOn     EQU $D2F1   ; screens left uncoloured because the LCD was already on
DEF wAuditMinLY     EQU $D2F2   ; lowest LY seen at such a write in VBlank (144-153)
DEF wSgbFound      EQU $D2F3   ; SGB_YES / SGB_NO once looked for (anything else: not yet)
DEF SGB_YES         EQU $5A
DEF SGB_NO          EQU $A5
DEF wZoneTile       EQU $D2F4   ; dotted floor tile of this court (CourtTexture)
DEF wZoneRows       EQU $D2F5   ; rows 11-15 (bits 0-4) of Mario's empty spot to dot, 0 = none
DEF wZoneCol        EQU $D2F6   ; first column of that spot once known, 0 = not yet
DEF wOvlLim         EQU $D2F8   ; court overlay: sprites right of this x are hidden by the window
DEF wCardTodo       EQU $D2F9   ; TODO_xx bits: work for the next OvlVBlank
DEF TODO_PALCARD    EQU 0       ; load the card's colours into OBJ palette 5
DEF TODO_PALNORM    EQU 1       ; ...and give it back
DEF TODO_STRIPON    EQU 2       ; strip right of the card: card background
DEF TODO_STRIPOFF   EQU 3       ; ...blank again
DEF TODO_ZONE       EQU 4       ; dotted floor where Mario is not (wZoneCol)
DEF wOvlStaticDst   EQU $D2FC   ; OVL_STATIC: low byte of the first shadow OAM slot used
DEF wOvlStaticLen   EQU $D2FD   ; OVL_STATIC: bytes to copy (multiple of 4)
DEF wOvlCount       EQU $D2FE   ; row counter used by that routine
DEF wOvlMode        EQU $D2FF   ; OVL_* below
DEF wOvlSlot        EQU $D300   ; [256] Mario BG tile -> overlay sprite tile (0 = none)
DEF wOvlAttr        EQU $D400   ; [256] Mario BG tile -> overlay OAM attribute
DEF wOvlBuf         EQU $D500   ; [<=96] OVL_STATIC: ready-made OAM entries
DEF OVL_STATIC_MAX  EQU 24      ; entries

DEF OVL_OFF         EQU 0
DEF OVL_COURT       EQU 1       ; Mario moves with the camera, 2 rows of sprites
DEF OVL_STATIC      EQU 2       ; fixed sprites (score-board Mario, title DX): wOvlBuf copied as is
DEF OVL_SGB         EQU 3       ; Super Game Boy court: only the strip right of the FAULT / OUT card

; Overlay sprites use the highest OAM slots, but only while the game
; leaves them free (slot >= wOAMNext).
DEF OVL_OAM_TOP     EQU wShadowOAM + 39 * 4
DEF OVL_OAM_BASE    EQU wShadowOAM + 32 * 4
DEF CARD_OAM        EQU wShadowOAM + 33 * 4   ; 3 slots below Mario's court overlay (bib row)
DEF CARD_FACE_TILE  EQU $AD     ; FAULT / OUT card: tile at window row 2, column 1
DEF CARD_MID_TILE   EQU $B0     ;   ... row 3, column 1
DEF CARD_TILE       EQU $B3     ; FAULT / OUT card: tile at window row 4, column 1
DEF CARD_BG_TILE    EQU $81     ; plain background tile (colour 1) of the card
DEF BLANK_TILE      EQU $80     ; what the game draws right of the card
DEF CARD_STRIP_COL  EQU 5       ; first window column right of the card

; Screen data block layout (one 1 KiB-aligned block per screen, see gen_data.py)
RSRESET
DEF BLK_BG_ATTR     RB 256      ; BG tile -> attribute
DEF BLK_OBJ0        RB 256      ; sprite tile -> attribute bits (OBP0)
DEF BLK_OBJ1        RB 256      ; sprite tile -> attribute bits (OBP1)
DEF BLK_BG_PALS     RB 64
DEF BLK_OBJ_PALS    RB 64
DEF BLK_LISTS       RB 0        ; overrides, patches, overlays (variable)

; VRAM_AUDIT builds: before a write to VRAM or palette RAM made with the LCD
; on, count it if the PPU is not in VBlank (keeps all registers and flags)
MACRO AuditVBlank
IF DEF(VRAM_AUDIT)
    push af
    ldh a, [rLY]
    cp 144
    jr nc, .vb\@
    ld a, [wAuditLY]
    inc a
    ld [wAuditLY], a
    jr .done\@
.vb\@:
    push hl
    ld hl, wAuditMinLY
    cp [hl]
    jr nc, .keep\@
    ld [hl], a
.keep\@:
    pop hl
.done\@:
    pop af
ENDC
ENDM
