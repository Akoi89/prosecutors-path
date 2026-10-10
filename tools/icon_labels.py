# -*- coding: utf-8 -*-
"""Words on the labels of the evidence icons (com/idcom.bin), set as pixel lettering in the face the fan
drew them in.

The fan's bottle labels carry one-pixel-stroke lettering: capitals seven rows high, lower case five rows
(ascenders seven) and four pixels wide, a pixel of space between letters ("Norm", "Fatal"). Five letters of that
face are HARVESTED at build time from the fan's own icons (N o r from 487 "Norm", F a from 489 "Fatal": the pixels of
the three darkest palette entries inside a glyph box), so no pixel of the fan's art is stored in this module; harvest() must
run before a word is set (idcom_icons.patch and the audit do it from the fan's container). The others are designed here from
the strokes of those letters by the same rules, as the one-stroke glyphs of tools/marker_letters.py and plates.py are: a bowl
is the o, a stem is the l, an arm is the r's, a tail the a's, a foot the t's. Nothing is scaled or squeezed; a word that is
longer than its label runs off the label's edge where the fan's did ("Norm|", "Fatal|") and is clipped there.

A word is set into a copy of the fan's icon grid: the old word's pixels are replaced by the label ground
(the colour of a clean row of the same label, column by column, or one flat index), then the new word is drawn
in the label's own ink colour. The palette and everything outside the word's box stay the fan's.

    harvest(grids)          grids: {icon entry: index grid of the fan's icon}
    set_words(grid, words) -> new grid
"""
import numpy as np

# The letters taken from the fan's icons when the build runs: letter -> (x of its left column, y of its top row, width, rows)
# in that icon's pixel grid. A pixel is ink when its palette index is one of INK_INDICES (the label's three darkest entries).
HARVEST = {
    487: (('N', 23, 32, 4, 7), ('o', 28, 34, 4, 5), ('r', 33, 34, 3, 5)),     # "Norm"
    489: (('F', 23, 32, 3, 7), ('a', 27, 34, 4, 5)),                          # "Fatal"
}
INK_INDICES = (1, 2, 3)

# 4 pixels wide unless the rows say otherwise; rows top to bottom; '#' ink. Capitals and ascenders use 7 rows,
# lower case 5 (they are drawn two rows down), a descender adds rows below (marked by "desc").
FACE = {
    # --- plain stem shapes ---
    't': ['.#.', '.#.', '###', '.#.', '.#.', '.#.', '.##'],
    'l': ['#', '#', '#', '#', '#', '#', '#'],
    # --- built from the strokes of the harvested letters ---
    'i': ['#', '.', '#', '#', '#', '#', '#'],                        # the l's stem under a dot
    'n': ['###.', '#..#', '#..#', '#..#', '#..#'],                  # the r's arm on the o's right side
    'u': ['#..#', '#..#', '#..#', '#..#', '.###'],                  # the n turned over
    'm': ['##.#.', '#.#.#', '#.#.#', '#.#.#', '#.#.#'],              # two arches
    'b': ['#...', '#...', '###.', '#..#', '#..#', '#..#', '###.'],   # the l's stem and a bowl
    'd': ['...#', '...#', '.###', '#..#', '#..#', '#..#', '.###'],
    'h': ['#...', '#...', '###.', '#..#', '#..#', '#..#', '#..#'],
    'p': ['###.', '#..#', '#..#', '#..#', '###.', '#...', '#...'],   # two rows below the baseline
    'q': ['.###', '#..#', '#..#', '#..#', '.###', '...#', '...#'],
    'y': ['#..#', '#..#', '#..#', '.###', '...#', '.##.'],
    'x': ['#..#', '#..#', '.##.', '#..#', '#..#'],
    's': ['.###', '#...', '.##.', '...#', '###.'],
    'c': ['.###', '#...', '#...', '#...', '.###'],
    'e': ['.##.', '#..#', '####', '#...', '.###'],
    'f': ['.##', '#..', '###', '#..', '#..', '#..', '#..'],
    'U': ['#..#', '#..#', '#..#', '#..#', '#..#', '#..#', '.##.'],
    'A': ['.##.', '#..#', '#..#', '####', '#..#', '#..#', '#..#'],
    'L': ['#..', '#..', '#..', '#..', '#..', '#..', '###'],
    'T': ['###', '.#.', '.#.', '.#.', '.#.', '.#.', '.#.'],
    'R': ['###.', '#..#', '#..#', '###.', '#.#.', '#..#', '#..#'],
    'I': ['###', '.#.', '.#.', '.#.', '.#.', '.#.', '###'],
    'E': ['####', '#...', '#...', '###.', '#...', '#...', '####'],
    'K': ['#..#', '#..#', '#.#.', '##..', '#.#.', '#..#', '#..#'],
    'D': ['###.', '#..#', '#..#', '#..#', '#..#', '#..#', '###.'],
    'Y': ['#...#', '#...#', '.#.#.', '..#..', '..#..', '..#..', '..#..'],
    'C': ['.###', '#...', '#...', '#...', '#...', '#...', '.###'],
    'Z': ['####', '...#', '..#.', '.#..', '.#..', '#...', '####'],
    '3': ['###.', '...#', '...#', '.##.', '...#', '...#', '###.'],
}
# The small caps of the 485 label's second line (the fan's "TOXIN": four rows high, three pixels wide, a pixel of space,
# orange). Only the letters the Collection's word needs, built from the strokes of the fan's T O X I N.
FACE_TOXIN = {
    'T': ['###', '.#.', '.#.', '.#.'],
    'U': ['#.#', '#.#', '#.#', '###'],
    'L': ['#..', '#..', '#..', '###'],
    'R': ['##.', '#.#', '##.', '#.#'],
    'A': ['.#.', '#.#', '###', '#.#'],
}
FACES = {None: FACE, 'toxin': FACE_TOXIN}
LOWER = set('abcdefghijklmnopqrstuvwxyz')
TALL_LOWER = set('bdfhilt')               # lower case drawn on the 7-row grid
SPACE = 3


def harvest(grids):
    """Cut the harvested letters out of the fan's icons (`grids` maps icon entry to its index grid) into FACE. Raises
    ValueError if an icon is missing, is not the grid it should be, or a glyph box holds no ink."""
    for entry, glyphs in HARVEST.items():
        if entry not in grids:
            raise ValueError('the fan icon %d is needed for the label face' % entry)
        g = np.asarray(grids[entry])
        if g.shape != (64, 64):
            raise ValueError('icon %d is %r, not 64 x 64' % (entry, g.shape))
        for ch, x0, y0, w, h in glyphs:
            rows = [''.join('#' if int(g[y0 + r, x0 + c]) in INK_INDICES else '.' for c in range(w)) for r in range(h)]
            if not all('#' in rows[r] for r in (0, h // 2)) or '#' not in rows[-1]:
                raise ValueError('no %r in the fan icon %d at (%d, %d): the box is empty' % (ch, entry, x0, y0))
            FACE[ch] = rows


def glyph_rows(ch, face=None):
    """-> (rows as strings, row index of the glyph's top relative to the cap line (0 = cap top))."""
    table = FACES[face]
    if ch not in table:
        raise ValueError('no glyph for %r in the icon face %r (harvest() not run yet?)' % (ch, face))
    rows = table[ch]
    if face is None and ch in LOWER and ch not in TALL_LOWER:
        return rows, 2
    return rows, 0


def word_bitmap(text, gap=1, face=None):
    """-> list of (x offset, glyph rows, top row) for the word, advance = width + gap."""
    out = []
    x = 0
    for ch in text:
        if ch == ' ':
            x += SPACE
            continue
        rows, top = glyph_rows(ch, face)
        w = max(len(r) for r in rows)
        out.append((x, rows, top))
        x += w + gap
    return out, x - gap


def set_words(grid, words):
    """grid: (h, w) index array of the fan's icon. words: list of dicts
       text   the word
       x, y   left edge and cap-line row of the first letter
       ink    palette index of the letters
       clip   (x0, x1): letters are drawn only for x0 <= x < x1
       erase  (x0, y0, x1, y1): pixels replaced by the label ground before the word is drawn
       fill   ('row', y_ref): ground = the pixel of row y_ref in the same column; ('flat', idx); or
              ('near', (idx, ...)): the pixels with those indices (the old letters' colours) become the nearest
              pixel of the same row that has none of them
       face   None (the bottle label face) or 'toxin' (the four-row capitals of the 485 label)
       gap    pixels between letters (default 1); slope: rows per column the baseline moves (default 0)
       desc_ground  optional (x0, y0, x1, y1, ('row', y)) boxes whose pixels are re-grounded too (descenders)
    -> (new grid, set of changed pixels)."""
    g = np.array(grid, np.uint8)
    base = g.copy()
    for w in words:
        x0, y0, x1, y1 = w['erase']
        kind, ref = w['fill']
        for y in range(y0, y1):
            for x in range(x0, x1):
                if kind == 'row':
                    g[y, x] = base[ref, x]
                elif kind == 'flat':
                    g[y, x] = ref
                elif base[y, x] in ref:
                    for d in range(1, 12):
                        for xx in (x - d, x + d):
                            if x0 - 12 <= xx < x1 + 12 and 0 <= xx < base.shape[1] and base[y, xx] not in ref:
                                g[y, x] = base[y, xx]
                                break
                        else:
                            continue
                        break
    for w in words:
        bm, _width = word_bitmap(w['text'], w.get('gap', 1), w.get('face'))
        cx0, cx1 = w['clip']
        slope = w.get('slope', 0.0)
        for (ox, rows, top) in bm:
            dy = int(round(slope * ox))
            for r, row in enumerate(rows):
                for c, ch in enumerate(row):
                    if ch != '#':
                        continue
                    x, y = w['x'] + ox + c, w['y'] + top + r + dy
                    if cx0 <= x < cx1:
                        g[y, x] = w['ink']
    changed = {(int(x), int(y)) for y, x in zip(*np.where(g != base))}
    return g, changed
