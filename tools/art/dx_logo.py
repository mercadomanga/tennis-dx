"""'DX' badge for the title screen: 48 x 32 pixels, drawn with sprites.

The letters are drawn as geometric shapes at 8x resolution, tilted so the
word climbs to the right, and scaled down to pixels (smooth edges, no
rotation artefacts). Then outline, drop shadow and highlight are added.
Colours: 1 = letter, 2 = highlight, 3 = outline and shadow, 0 = transparent."""
from PIL import Image, ImageDraw

W, H = 48, 32
ANGLE = -10          # degrees: negative tilts the word down to the right
SCALE = 8
LETTER_H = 18        # pixels (the shapes below are designed for 14)


def shapes(draw, s):
    """D and X, upright, in pixel units times s, top-left at (0, 0)."""
    h = 14
    # D: outer outline with a cut right side, minus the inner hole
    draw.polygon([(0, 0), (8.5 * s, 0), (12 * s, 3.5 * s), (12 * s, (h - 3.5) * s),
                  (8.5 * s, h * s), (0, h * s)], fill=255)
    draw.polygon([(4 * s, 4 * s), (7 * s, 4 * s), (8 * s, 5 * s), (8 * s, (h - 5) * s),
                  (7 * s, (h - 4) * s), (4 * s, (h - 4) * s)], fill=0)
    # X: two thick bars with flat ends
    x0, w, t = 13.5, 13, 4.2
    draw.polygon([((x0) * s, 0), ((x0 + t) * s, 0), ((x0 + w) * s, h * s), ((x0 + w - t) * s, h * s)], fill=255)
    draw.polygon([((x0 + w - t) * s, 0), ((x0 + w) * s, 0), ((x0 + t) * s, h * s), ((x0) * s, h * s)], fill=255)


def build(angle=ANGLE):
    s = SCALE
    big = Image.new('L', (W * s, H * s), 0)
    k = LETTER_H / 14
    word = Image.new('L', (int(27 * s * k) + 1, int(14 * s * k) + 1), 0)
    shapes(ImageDraw.Draw(word), s * k)
    word = word.rotate(angle, resample=Image.BICUBIC, expand=True)
    big.paste(word, (1 * s, 1 * s))
    small = big.resize((W, H), Image.BOX)
    fill = {(y, x) for y in range(H) for x in range(W) if small.getpixel((x, y)) >= 128}
    assert max(y for y, _ in fill) < H - 3 and max(x for _, x in fill) < W - 3, 'badge too big'
    grid = [[0] * W for _ in range(H)]
    for y, x in fill:
        grid[y][x] = 1
    # exterior = transparent area reachable from the border (not the hole in D)
    ext, stack = set(), [(0, 0)]
    while stack:
        y, x = stack.pop()
        if (y, x) in ext or not (0 <= y < H and 0 <= x < W) or (y, x) in fill:
            continue
        ext.add((y, x))
        stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    for y in range(H):              # outline all round + drop shadow down/right
        for x in range(W):
            if (y, x) in fill:
                continue
            if any((y - dy, x - dx) in fill for dy in (-1, 0, 1, 2) for dx in (-1, 0, 1, 2)
                   if (dy, dx) != (-1, 2) and (dy, dx) != (2, -1)):
                grid[y][x] = 3
    for y, x in fill:               # white highlight on top edges facing outside
        if (y - 1, x) in ext or (y - 1, x) not in fill and grid[y - 1][x] == 3 and (y - 2, x) in ext:
            grid[y][x] = 2
    return grid


def tiles():
    """Non-empty 8x8 tiles: [(col, row, 16 bytes of 2bpp data)]."""
    g = build()
    out = []
    for ty in range(H // 8):
        for tx in range(W // 8):
            data = []
            for y in range(8):
                lo = hi = 0
                for x in range(8):
                    v = g[ty * 8 + y][tx * 8 + x]
                    lo |= (v & 1) << (7 - x)
                    hi |= (v >> 1) << (7 - x)
                data += [lo, hi]
            if any(data):
                out.append((tx, ty, data))
    return out


if __name__ == '__main__':
    for row in build():
        print(''.join(' o-#'[v] for v in row) + '|')
    print(len(tiles()), 'sprites')
