# -*- coding: utf-8 -*-
"""Mind Chess wait button: "Wait and see." -> Capcom's "Bide my time".

The wait option's label is a graphic, the last sprite bundle of
jpn/idlocal.bin, stored split: 671 RNAN, 672 RECN (cell bank), 673 RGCN
(tiles, 4bpp, 60 of them), 674 RLCN (palette). Cells 3-7 all draw the label
with the same three OBJs (32x16 at tile id 10, 32x16 at id 12, 16x16 at
id 14, boundary 4), so one shared 80x16 area, tiles 40-59, holds the whole
text: the red plate, the orange hover plate and the rest reuse it. Only those
20 tiles change.

Where the fan's lettering comes from (measured 2026-09-29, and proven again
on every build below): the fan's label is the game's own SMALL face, the one
Mind Chess draws its option rows in (arm9 table at fontwidths.SMALL_TABLE_OFF,
glyphs 14 rows of 16 pixels at 2 bits each, least significant pair first).
Keeping only the pixels of value 1 gives the fan's letters exactly: W a t n d
s e and the full stop match the fan's button pixel for pixel; the fan's "i"
differs by one pixel (its stem starts a row higher, and its dot is a single
pixel), which is why every letter the fan's own label draws is read from the
label itself and the small face fills in only the letters it lacks (B, m, y).
Pen advances are the face's own advances (W 10, a 6, i 2, t 4, n 6, d 6, s 6,
e 6, full stop 2), the word space is 3, and the first pen sits at column 8,
row 4 of the area; each of those reproduces the fan's letter positions
exactly. The outline is every pixel touching a fill pixel, diagonals
included: it reproduces all 340 of the fan's outline pixels with none extra.
Fill is palette index 15, outline index 1.

patch() draws the fan's own words with this same routine first and compares
the result with the fan's tiles; on any difference the entry is left as it
is and the reason is logged, so the routine can never ship unproven. It also
guards on the sha256 of the fan's decoded entry 673, on the cell layout, and
on the sha256 of the decoded arm9 the small face is read from, which covers
B, m and y (letters the fan's own words cannot prove).
"""
import sys, os, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from choice_strips import Idlocal, rebuild, rom_file
from ncer import ncer
from nitro import ncgr, tile_pixels
from mindchess import _ncgr_tile_offset, _write_shape
import fontwidths

ENTRY_CELLS, ENTRY_TILES = 672, 673
FAN_TILES_SHA256 = 'd553a72c62ddd1390cbbc2f69b58be0fffba7c2c6ce0ce6023b964e430ffdbcb'
ARM9_SHA256 = 'a50bb8c350e12bf8edce044acadd4c58de4a99ed2d3db671d18fa27d6290bb9f'   # decoded, fan = port
FAN_TEXT = 'Wait and see.'
TEXT = 'Bide my time'
FILL, OUTLINE = 15, 1
AREA_W, AREA_H = 80, 16
TEXT_CELLS = (3, 4, 5, 6, 7)
OBJ_TILE_IDS = (10, 12, 14)     # x 79 / 111 / 143 at y 8: 32x16, 32x16, 16x16
OBJ_WIDTHS = (32, 32, 16)
PEN_X, PEN_Y = 8, 4             # first fill column, glyph row 0
SPACE = 3                       # word space, measured off the fan's label
GLYPH_ROWS, GLYPH_COLS, GLYPH_BYTES = 14, 16, 56
FAN_LETTER_ROWS = 1             # value in the small face that is fill
SMALL_ONLY_DIFF = 1             # pixels the small face alone gets wrong on the fan's words (its i)


def _arm9(rom):
    off, _entry, ram, size = struct.unpack_from('<IIII', rom, 0x20)
    if off + size > len(rom) or size > fontwidths.MAX_ARM9:
        return None, None
    a = fontwidths._blz_decode(bytes(rom[off:off + size]))
    return a, ram


def _small_face(arm9, ram):
    """-> {char: (advance, set of (x, y) fill pixels)} for printable ASCII."""
    off, n = fontwidths.SMALL_TABLE_OFF, fontwidths.SMALL_TABLE_N
    if fontwidths._read_table_range(arm9, off, n) is None:
        return None
    rec = {}
    for i in range(n):
        cp, adv, ptr = struct.unpack_from('<HHI', arm9, off + i * 8)
        rec[cp] = (adv, ptr)
    face = {}
    for c in range(0x21, 0x7F):
        cp = 0xFF00 + c - 0x20
        if cp not in rec:
            continue
        adv, ptr = rec[cp]
        b = ptr - ram
        if b < 0 or b + GLYPH_BYTES > len(arm9):
            return None
        pts = set()
        for y in range(GLYPH_ROWS):
            v = int.from_bytes(arm9[b + y * 4:b + y * 4 + 4], 'little')
            for x in range(GLYPH_COLS):
                if (v >> (2 * x)) & 3 == FAN_LETTER_ROWS:
                    pts.add((x, y))
        face[chr(c)] = (adv, pts)
    return face


def _area_of(rgcn):
    """The 80x16 text area of an entry 673 as a grid of palette indices."""
    data, bpp, _cnt, _w, _h = ncgr(rgcn)
    g = [[0] * AREA_W for _ in range(AREA_H)]
    x = 0
    for tid, wpx in zip(OBJ_TILE_IDS, OBJ_WIDTHS):
        tw = wpx // 8
        for ty in range(2):
            for tx in range(tw):
                tp = tile_pixels(data, tid * 4 + ty * tw + tx, bpp)
                for yy in range(8):
                    for xx in range(8):
                        g[ty * 8 + yy][x + tx * 8 + xx] = tp[yy][xx]
        x += wpx
    return g


def _fan_letters(area):
    """The fan's own letters of "Wait and see." cut from the label itself:
    {char: set of (dx, dy)} relative to the letter's pen (column, PEN_Y). A
    letter is a run of fill pixels; runs whose columns overlap are one letter
    (the dot and stem of an i). Returns None if the label is not the one
    expected."""
    fill = {(x, y) for y in range(AREA_H) for x in range(AREA_W) if area[y][x] == FILL}
    seen, comps = set(), []
    for p in sorted(fill):
        if p in seen:
            continue
        st, c = [p], [p]
        seen.add(p)
        while st:
            x, y = st.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in fill and q not in seen:
                        seen.add(q); st.append(q); c.append(q)
        comps.append(c)
    spans = sorted([[min(x for x, _ in c), max(x for x, _ in c), list(c)] for c in comps])
    merged = []
    for s in spans:
        if merged and s[0] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], s[1]); merged[-1][2] += s[2]
        else:
            merged.append(s)
    letters = [c for c in FAN_TEXT if c != ' ']
    if len(merged) != len(letters):
        return None
    out = {}
    for ch, (x0, _x1, pts) in zip(letters, merged):
        out.setdefault(ch, {(x - x0, y - PEN_Y) for x, y in pts})
    return out


def draw(text, face, letters):
    """-> (grid of palette indices, info). Fill from the fan's own letter where
    the label has one, else the small face; 8-neighbour outline; pen advance
    from the small face. Raises ValueError if fill or a needed glyph falls
    outside what the area or the face has."""
    fill, pen = set(), PEN_X
    for ch in text:
        if ch == ' ':
            pen += SPACE
            continue
        if ch not in face:
            raise ValueError('mc_wait: the small face has no glyph for %r' % ch)
        adv, pts = face[ch]
        for dx, dy in (letters.get(ch) if ch in letters else pts):
            fill.add((pen + dx, PEN_Y + dy))
        pen += adv
    ring = {(x + dx, y + dy) for (x, y) in fill for dy in (-1, 0, 1) for dx in (-1, 0, 1)} - fill
    g = [[0] * AREA_W for _ in range(AREA_H)]
    clipped = sorted(p for p in ring if not (0 <= p[0] < AREA_W and 0 <= p[1] < AREA_H))
    for x, y in ring:
        if 0 <= x < AREA_W and 0 <= y < AREA_H:
            g[y][x] = OUTLINE
    for x, y in fill:
        if not (0 <= x < AREA_W and 0 <= y < AREA_H):
            raise ValueError('mc_wait: fill pixel (%d,%d) falls outside the %dx%d area' % (x, y, AREA_W, AREA_H))
        g[y][x] = FILL
    ink = fill | {p for p in ring if p not in clipped}
    info = dict(ink_x=(min(x for x, _ in ink), max(x for x, _ in ink)),
                ink_y=(min(y for _, y in ink), max(y for _, y in ink)),
                fill_y=(min(y for _, y in fill), max(y for _, y in fill)),
                clipped=clipped)
    return g, info


def _check_layout(recn):
    cells, _mapping = ncer(recn)
    for ci in TEXT_CELLS:
        objs = sorted(cells[ci], key=lambda o: o['x'])
        got = tuple(o['tile'] for o in objs)
        dims = tuple((o['w'], o['h'], o['y']) for o in objs)
        if got != OBJ_TILE_IDS or dims != ((32, 16, 8), (32, 16, 8), (16, 16, 8)):
            return 'cell %d is %r %r, expected tiles %r' % (ci, got, dims, OBJ_TILE_IDS)
    return None


def patch(idlocal_bytes, arm9, ram, log=None):
    """-> (new_idlocal_bytes, changed). Leaves the entry alone (and says why)
    when anything the drawing depends on is not what it was proven against."""
    log = log or (lambda s: None)
    idl = Idlocal(idlocal_bytes)

    def skip(why):
        log('Mind Chess wait button: not redrawn (%s)' % why)
        return idlocal_bytes, False

    if idl.n <= ENTRY_TILES:
        return skip('idlocal has %d entries' % idl.n)
    rgcn = idl.blob(ENTRY_TILES)
    have = hashlib.sha256(rgcn).hexdigest()
    if have != FAN_TILES_SHA256:
        return skip('entry %d sha256 %s is not the fan\'s' % (ENTRY_TILES, have[:12]))
    why = _check_layout(idl.blob(ENTRY_CELLS))
    if why:
        return skip(why)
    if arm9 is None:
        return skip('the ROM\'s arm9 could not be read')
    have = hashlib.sha256(arm9).hexdigest()
    if have != ARM9_SHA256:
        return skip('arm9 sha256 %s is not the one the small face was proven on' % have[:12])
    face = _small_face(arm9, ram)
    if face is None:
        return skip('the small font table is not where it was measured')
    area = _area_of(rgcn)
    letters = _fan_letters(area)
    if letters is None:
        return skip('the fan\'s label is not made of the expected letters')
    proof, _ = draw(FAN_TEXT, face, letters)
    if proof != area:
        n = sum(1 for y in range(AREA_H) for x in range(AREA_W) if proof[y][x] != area[y][x])
        return skip('redrawing the fan\'s own words differs from the fan in %d pixels' % n)
    # the small face alone (no fan letters) must agree with the fan's label
    # except for the one pixel of its "i" (measured: exactly 1 of 1280)
    alone, _ = draw(FAN_TEXT, face, {})
    n = sum(1 for y in range(AREA_H) for x in range(AREA_W) if alone[y][x] != area[y][x])
    if n != SMALL_ONLY_DIFF:
        return skip('the small face alone differs from the fan\'s label in %d pixels, expected %d'
                    % (n, SMALL_ONLY_DIFF))
    g, info = draw(TEXT, face, letters)
    new = bytearray(rgcn)
    tile_off, _size = _ncgr_tile_offset(rgcn)
    x = 0
    for tid, wpx in zip(OBJ_TILE_IDS, OBJ_WIDTHS):
        sub = [row[x:x + wpx] for row in g]
        _write_shape(new, tile_off, tid, 4, sub, w_tiles=wpx // 8, h_tiles=2)
        x += wpx
    new = bytes(new)
    if len(new) != len(rgcn):
        raise ValueError('mc_wait: entry %d changed size %d -> %d' % (ENTRY_TILES, len(rgcn), len(new)))
    log('Mind Chess wait button: Bide my time (fan\'s small face, proven on the fan\'s own words: 0 of %d '
        'pixels differ; ink x %d..%d, y %d..%d, fill rows %d..%d, %d outline px clipped)'
        % (AREA_W * AREA_H, info['ink_x'][0], info['ink_x'][1], info['ink_y'][0], info['ink_y'][1],
           info['fill_y'][0], info['fill_y'][1], len(info['clipped'])))
    return rebuild(idlocal_bytes, {ENTRY_TILES: new}, lz=(ENTRY_TILES,)), True


def apply_to_rom(rom, dumpdir, log=None):
    import title_logo
    cur = rom_file(rom, 'jpn/idlocal.bin')
    arm9, ram = _arm9(rom)
    new_idlocal, changed = patch(cur, arm9, ram, log)
    if not changed:
        return rom, False
    return title_logo.splice(rom, 'jpn/idlocal.bin', new_idlocal), True
