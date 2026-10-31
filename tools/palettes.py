"""Tennis DX colours.

Everything a person may want to tweak lives here: the colours of each
screen and which tiles use which palette. gen_data.py turns this into the
tables the ROM reads. Colours are '#RRGGBB'; the GBC keeps 5 bits per
channel, so the last 3 bits of each channel are dropped.

Palette index 0 of a BG palette is the "paper" colour, 3 the darkest ink,
matching the original DMG shades. Index 0 of a sprite palette is
transparent and never shown. A colour can sit in several palettes, which is
how one change reaches every place it shows.
"""

# Common
WHITE = '#F8F8F8'           # lines, text, sprite paper
BLACK = '#101010'           # outlines
SKIN = '#F8B888'            # Mario, crowd and the FAULT / OUT card

# Players. On the court your shorts and the opponent's shirt are one palette
# slot (the same sprite palette draws your legs and the opponent's body).
PLAYER_SKIN = '#F8B888'
SHIRT_RED = '#D83030'       # you: shirt and headband
SHIRT_WHITE = '#F0F0F0'     # you: shorts and shoes; opponent: shirt; eyes
SHORTS_BLUE = '#3060D0'     # opponent: shorts and shoes
STRINGS = '#C0C0C0'         # racket strings

# Court (grass; the other surfaces are in SURFACES below)
GRASS_L = '#60B858'         # light stripe
GRASS_D = '#4A9C42'         # dark stripe
NET_DARK = '#183018'        # net mesh
WALL = '#2E7048'            # stadium wall
BALL_LIGHT = '#E8F040'
BALL_MID = '#90A818'
BALL_DARK = '#303800'
SHADOW_MID = '#101010'      # ball shadow
SHADOW_DARK = '#101010'
GOLD_YELLOW = '#F8D000'     # sparkles
GOLD_ORANGE = '#E05000'

# Crowd
CROWD_HAIR = '#6A3A20'      # hair (court)
CROWD_INK = '#202838'       # outline of the crowd and the stand structure (court)
CROWD_BLUE = '#3858B0'      # clothes
HAIR_BROWN = '#704020'      # hair (score board screen)
STANDS = '#B8D0F0'          # behind the crowd (score board screen)

# Score board screen
GRASS = '#58B050'           # floor
SB_GREEN = '#283038'        # board
SB_LINE = '#5C6874'         # board: faint lines
SB_TEXT = '#F8F8E8'         # board: text and frame
METAL_L = '#D8DCE0'         # metal frame
METAL_M = '#98A0A8'
METAL_D = '#586068'
METAL_INK = '#202428'
WALL_D = '#204830'          # back wall: shadow

# Mario, the umpire
CAP_RED = '#D82020'
MARIO_SHIRT = '#D83030'
MARIO_EYE = '#F0F0F0'
OVERALLS = '#2850C8'        # on the chair
CHAIR_TAN = '#D8A060'
CHAIR_DARK = '#805020'
CARD_BLUE = '#8890E0'       # FAULT / OUT card: background
BIB_BLUE = '#3060D0'        # FAULT / OUT card: overalls

# Menus
MENU_L = '#A8A8A8'          # text and (c) Nintendo: light
MENU_M = '#484848'          #   ... mid
MENU_D = '#101010'          #   ... dark
MENU_GREEN = '#40A040'      # green band and rackets
MENU_GREEN_D = '#102810'    # green band: edge
MENU_YELLOW = '#F8D038'     # logo and strings
HANDLE_RED = '#D83028'      # racket handles
CURSOR_GREY = '#B0B0B0'     # cursor (racket): metal
CURSOR_RED = '#D02020'      # cursor (racket): edge
DX_RED = '#D82828'          # "DX" letters
DX_INK = '#181010'          # "DX" outline
UNUSED_BLUE = '#3868E0'     # in a palette the game never uses


def rng(a, b):
    """Inclusive range of tile numbers."""
    return list(range(a, b + 1))


class Screen:
    def __init__(self, name, bg_pals, obj_pals, obj_default=(0, 1)):
        assert len(bg_pals) == 8 and len(obj_pals) == 8
        self.name = name
        self.bg_pals = bg_pals
        self.obj_pals = obj_pals
        self.obj_default = obj_default   # palette for OBP0 / OBP1 sprites
        self.bg = {}                     # BG tile -> palette
        self.obj0 = {}                   # sprite tile -> palette (OBP0 sprites)
        self.obj1 = {}                   # sprite tile -> palette (OBP1 sprites)
        self.rects = []                  # (map address, width, palette)

    def bg_tiles(self, pal, tiles):
        for t in tiles:
            self.bg[t] = pal

    def obj_tiles(self, pal, tiles, which=(0, 1)):
        for t in tiles:
            if 0 in which:
                self.obj0[t] = pal
            if 1 in which:
                self.obj1[t] = pal

    def rect(self, pal, map_base, row, col, width, height=1):
        for r in range(row, row + height):
            self.rects.append((map_base + r * 32 + col, width, pal))


SCRN0, SCRN1 = 0x9800, 0x9C00

# ------------------------------------------------------------------- menus
# Title screen and level select share their tiles.
menu = Screen('Menu', [
    (WHITE, MENU_L, MENU_M, MENU_D),                # 0 text
    (WHITE, MENU_GREEN, MENU_YELLOW, MENU_GREEN_D), # 1 green band, logo, rackets
    (WHITE, HANDLE_RED, MENU_YELLOW, BLACK),         # 2 racket handles
    (WHITE, MENU_L, MENU_M, MENU_D),                # 3 (c) Nintendo
] + [(WHITE, MENU_GREEN, MENU_YELLOW, MENU_GREEN_D)] * 4, [
    (WHITE, MENU_YELLOW, CURSOR_GREY, CURSOR_RED),   # 0 racket cursor (written with attr 0)
    (WHITE, MENU_L, MENU_M, MENU_D),                # 1 YES / NO sprites
    (WHITE, DX_RED, WHITE, DX_INK),                 # 2 "DX" on the title logo
] + [(WHITE, WHITE, UNUSED_BLUE, BLACK)] * 5, obj_default=(1, 1))
menu.bg_tiles(1, rng(0x81, 0xCB))
menu.bg_tiles(2, (0xBE, 0xBF))
menu.bg_tiles(3, [0xF8] + rng(0xFA, 0xFF))
menu.obj_tiles(0, [0xF9])
# "DX" badge (tools/art/dx_logo.py) at the lower right of the logo, title screen only
DX_POS = (94, 40)          # screen x, y of its top-left corner
DX_PAL = 2

# ------------------------------------------------------------- score board
# Shown before the match, when changing ends and at the end ("PLAY AGAIN").
board = Screen('Board', [
    (SB_GREEN, SB_GREEN, SB_LINE, SB_TEXT),         # 0 scoreboard (light text on charcoal, neutral for every surface)
    (METAL_L, METAL_M, METAL_D, METAL_INK),         # 1 metal frame
    (STANDS, SKIN, HAIR_BROWN, BLACK),              # 2 crowd heads (one hair colour: the heads do not line up with the tiles)
    (GRASS, WHITE, GRASS_D, NET_DARK),               # 3 net post, as the net on the court
    (WHITE, WALL, WALL_D, BLACK),                  # 4 wall
    (STANDS, SKIN, CROWD_BLUE, BLACK),              # 5 crowd clothes, Mario's overalls
    (STANDS, SKIN, CAP_RED, BLACK),                 # 6 Mario's head
    (GRASS, CHAIR_TAN, CHAIR_DARK, BLACK),         # 7 floor, chair, net post
], [
    (WHITE, PLAYER_SKIN, SHIRT_RED, BLACK),         # 0 player
    (WHITE, PLAYER_SKIN, SHIRT_WHITE, BLACK),       # 1 CPU (white shirt)
    (WHITE, PLAYER_SKIN, STRINGS, BLACK),           # 2 racket strings
    (WHITE, PLAYER_SKIN, SHIRT_WHITE, BLACK),       # 3 player legs (white shorts) / heads (white eyes)
    (WHITE, PLAYER_SKIN, SHORTS_BLUE, BLACK),       # 4 CPU legs: blue shorts and shoes, skin (hands, knees)
    (WHITE, MARIO_SHIRT, WALL, HAIR_BROWN),         # 5 Mario overlay: shirt / wall / left neighbour
    (WHITE, MARIO_SHIRT, WALL, HAIR_BROWN),         # 6 Mario overlay: shirt / wall / right neighbour
    (WHITE, SKIN, UNUSED_BLUE, BLACK),              # 7 (unused)
])
board.bg_tiles(1, rng(0x00, 0x07))
board.bg_tiles(2, (0x08, 0x09, 0x0A, 0x0B))
board.bg_tiles(3, (0x23, 0x24))
board.bg_tiles(5, (0x0C, 0x0D, 0x0E, 0x0F, 0x13, 0x14, 0x15, 0x16))
board.bg_tiles(4, (0x10, 0x81))
board.bg_tiles(6, (0x11, 0x12))
board.bg_tiles(7, (0x80, 0x17, 0x18, 0x19, 0x1A))
board.rect(0, SCRN0, 1, 1, 18, 8)                   # inside of the scoreboard
board.obj_tiles(2, (0x30, 0x31))
board.obj_tiles(3, [0x03, 0x08, 0x0A, 0x0F, 0x10, 0x13, 0x14, 0x27, 0x28, 0x36, 0x41, 0x46, 0x48] + rng(0x60, 0x63), which=(0,))
board.obj_tiles(4, [0x0F, 0x10, 0x13, 0x14, 0x27, 0x28, 0x41, 0x47, 0x49], which=(1,))

# ------------------------------------------------------------------- court
court = Screen('Court', [
    (GRASS_L, WHITE, GRASS_D, NET_DARK),            # 0 floor + lines (2 = dark stripe, net mesh)
    (GRASS_L, WALL, GRASS_D, CROWD_INK),            # 1 walls, stadium structure (the crowd's dark, as in the original)
    (GRASS_L, SKIN, CAP_RED, BLACK),                # 2 Mario's head (light stripe)
    (GRASS_L, CHAIR_TAN, CHAIR_DARK, BLACK),         # 3 umpire chair
    (CROWD_BLUE, SKIN, CROWD_HAIR, CROWD_INK),       # 4 crowd: brown hair; colour 0 (unused by the game here): clothes of the crowd in the front and back rows
    (WHITE, SKIN, CROWD_BLUE, CROWD_INK),            # 5 crowd, blue
    (WHITE, CARD_BLUE, CAP_RED, BLACK),             # 6 window: score box, FAULT / OUT (Mario's skin = sprites)
    (GRASS_D, SKIN, OVERALLS, BLACK),               # 7 Mario's body: overalls (dark stripe)
], [
    (WHITE, PLAYER_SKIN, SHIRT_RED, BLACK),         # 0 player
    (WHITE, PLAYER_SKIN, SHIRT_WHITE, BLACK),       # 1 CPU (white shirt) and your legs
    (WHITE, PLAYER_SKIN, STRINGS, BLACK),           # 2 racket strings
    (WHITE, BALL_LIGHT, BALL_MID, BALL_DARK),       # 3 ball
    (WHITE, SHADOW_MID, SHADOW_MID, SHADOW_DARK),   # 4 ball shadow
    (WHITE, GOLD_YELLOW, GOLD_ORANGE, BLACK),       # 5 (the card borrows it, see CARD_OBJ_PAL)
    (WHITE, MARIO_EYE, MARIO_SHIRT, BLACK),         # 6 Mario's shirt overlay (red) and his white eye
    (WHITE, PLAYER_SKIN, SHORTS_BLUE, BLACK),       # 7 CPU legs: skin, blue shorts and shoes
])
# OBJ palette 5 is not used while the FAULT / OUT card is up: vblank.asm loads
# colours 1-3 of this palette into it for as long as the card shows.
CARD_OBJ_PAL = (WHITE, SKIN, BIB_BLUE, CHAIR_TAN)
court.obj_tiles(2, (0x30, 0x33, 0x34))
court.obj_tiles(3, (0x31, 0x32, 0x37, 0x38))
court.obj_tiles(4, (0x2F, 0x22))
court.obj_tiles(5, rng(0x84, 0xA2))
# lower-body tiles (found by logging sprite rows during play)
court.obj_tiles(1, [0x0F, 0x10, 0x13, 0x14, 0x4A, 0x4B, 0x4F, 0x70, 0x71] + rng(0x60, 0x69), which=(0,))
court.obj_tiles(7, rng(0x23, 0x2E) + [0x41], which=(1,))
court.bg_tiles(1, [0x39, 0x3C, 0x41, 0x42, 0x43, 0x45, 0x46, 0x48, 0x4A, 0x4C, 0x4E, 0x51, 0x81]
               + rng(0x50, 0x61) + [0x82, 0x62, 0x63, 0x64, 0x6F, 0x71, 0x72,
                                    0x44, 0x47, 0x49, 0x4B, 0x4D, 0x4F])
court.bg_tiles(2, (0x84, 0x85, 0x86, 0x87, 0x37, 0x38))
court.bg_tiles(3, (0x3A, 0x3B, 0x3D, 0x3E))
court.bg_tiles(4, (0x75, 0x76, 0x7D, 0x7E, 0x73, 0x83, 0x40, 0x3F, 0x32, 0x79, 0x7A, 0x7F, 0x70, 0x74))
court.bg_tiles(5, (0x77, 0x78, 0x7B, 0x7C))
# The rows of crowd in front ($7D-$7E over $7F-$70 / $3F-$32, seen from
# behind) and at the back ($74) have hair and clothes in the same colour 2:
# gen_data.py turns their clothes into colour 0 in VRAM bank 1 (CROWD_CLOTHES).
court.rect(6, SCRN1, 0, 0, 8, 8)                    # window layer (score box, FAULT / OUT)
# Mario and his chair are drawn after the LCD is on: fixed rectangles,
# right of the court and (after changing ends) left of it.
for col in (22, 3):
    court.rect(2, SCRN0, 11, col, 2)                # head, light stripe
    court.rect(7, SCRN0, 12, col, 2, 2)             # body, dark stripe
    court.rect(3, SCRN0, 14, col, 2, 2)             # chair, light stripe

# ---------------------------------------------------------------- surfaces
# The court's floor changes with the level the game is playing (it picks it
# in the level menu and offers the next one after each win). LEVELS gives
# the surface of LEVEL 1-4, slowest to fastest, like real tennis: clay, hard,
# carpet, grass. Grass is the court and score board above, with their
# mowing stripes (the colours at the top of this file); the
# others replace the palettes of the floor (BG 0), walls (BG 1), the floor
# around Mario (BG 2, 3, 7). (OBJ 4, the ball's shadow, is black on all.)
#   inside / outside   floor inside the lines and around the court. When they
#                      differ, the outside is drawn with colour 2 of BG 0
#                      (copies of the floor tiles in VRAM bank 1), so the net
#                      mesh, also colour 2, takes the outside colour.
#   mesh               net mesh (= outside when they differ)
#   wall, wall_d       stadium wall (and its shadow on the score board)
# The score board before a match shows the same floor (the colour around
# the court, the one that tells the surfaces apart) and wall: BG 3, 4 and 7
# and the wall behind Mario's shirt (OBJ 5, 6).
SURFACES = [
    dict(name='Hierba', grass=True, texture=0b11001),
    dict(name='Tierra batida', texture=0b11111, inside='#D07848', outside='#D07848', mesh='#A85430',
         wall='#2E6B48', wall_d='#1E4A30', slope='#A85430', net='#3A1C10'),
    dict(name='Pista dura', inside='#3060A8', outside='#50A0D8', mesh='#50A0D8',
         wall='#203C70', wall_d='#142850', slope='#3878B8', net='#101830'),
    dict(name='Moqueta', inside='#68B878', outside='#C05068', mesh='#C05068',
         wall='#4A2838', wall_d='#301824', slope='#983850', net='#182818'),
]
# texture: the plain floor gets a few dots of colour 2 of its palette (the
# mesh on clay, the dark stripe on grass, where only the light rows show them).
# Mario's empty spot (rows 11-15) is dotted too, in the rows given here as
# bits 0-4: all of them on clay; on grass rows 12-13 are a dark stripe.
# (x, y) of the dots in each 8 x 8 floor tile:
FLOOR_DOTS = [(1, 2), (5, 0), (3, 5), (7, 6)]
LEVELS = ['Tierra batida', 'Pista dura', 'Moqueta', 'Hierba']      # LEVEL 1, 2, 3, 4
SURFACE = {sf['name']: sf for sf in SURFACES}
assert sorted(LEVELS) == sorted(SURFACE)


def surface_palettes(sf):
    """(8 BG palettes, OBJ palette 4, in/out) of a surface on the court."""
    bg = list(court.bg_pals)
    bg[0] = (sf['inside'], WHITE, sf['mesh'], sf['net'])
    bg[1] = (sf['outside'], sf['wall'], sf['slope'], CROWD_INK)
    for p in (2, 3, 7):
        bg[p] = (sf['outside'],) + tuple(court.bg_pals[p][1:])
    inout = sf['inside'] != sf['outside']
    assert not inout or sf['mesh'] == sf['outside']
    return bg, court.obj_pals[4], inout          # the ball's shadow: black, as the players'


def surface_board(sf):
    """(8 BG palettes, OBJ palettes 5 and 6) of a surface on the score board."""
    floor = sf['outside']
    bg = list(board.bg_pals)
    bg[3] = (floor, WHITE, sf['slope'], sf['net'])           # net post: its mesh a darker floor (the court's mesh colour can be the floor's)
    bg[4] = (WHITE, sf['wall'], sf['wall_d'], BLACK)
    bg[7] = (floor,) + tuple(board.bg_pals[7][1:])
    obj = [tuple(p[:2]) + (sf['wall'],) + tuple(p[3:]) for p in board.obj_pals[5:7]]   # colour 2: the wall
    return bg, obj


SCREENS = [menu, board, court]
