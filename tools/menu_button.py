# -*- coding: utf-8 -*-
"""The partner card's "Change Re-creation" button, in Capcom's words: "Switch re-creations".

jpn/idlocal.bin entries 356 (cells), 357 (tiles) and 358 (palette) hold the partner cards of the Court
Record; cells 10 (red card) and 11 (orange card) are the "Change / Re-creation" button, two lines of green
pixel lettering with a dark outline, drawn from the same tiles. Capcom's English tells the player to pick
"Switch re-creations" (loc table gk2_select_short_en, topic04_030; the script says "select Switch
re-creations"), so the button must say that.

The lettering is the fan's own face: one pixel strokes, four pixels wide, five rows of x-height, an outline
of the ink's 8-neighbour ring. The letters the old words hold (C h a n g e, R e - c r a t i o n) are cut out
of the button at build time and, before anything is written, the two old words are redrawn from the cut letters
with the ring and compared with the fan's pixels (one differing pixel stops the build). The three letters the
new words need that the old ones do not hold (S, w, s) are built from strokes of the face (an arc of the C,
the diagonals of the n, the a's tail), as marker_letters.py builds the ones Capcom needs. The words are
centred where the old ones were; the arrows beside the first line stay.

Only the tile data of entry 357 changes (310 pixels): it keeps its decoded size and is stored as a real LZ11
stream in no more bytes than the fan's entry held. A halo pixel that would fall where the card has no OBJ (above the
tops of the t and i of "Switch": the card's tiles start on that row) is dropped; no ink is.

    patch_idlocal(idl_bytes, loc_en) -> (new idlocal bytes, info)
"""
import sys, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import room_names as rn

IDLOCAL = 'jpn/idlocal.bin'
CELLS, TILES, PALETTE = 356, 357, 358
CELL = 10                                        # the red card; cell 11 (orange) draws the same tiles
FAN_SHA256 = {
    356: '9421fa77260d9bd9f324018ab3abdfdfdd4b9eee31622af2f798751836a5437f',
    357: '95ec93ea6736fbaf64db7570fac7e302c77f5efe05c777fac24ee65c745cc8e2',
    358: 'b8e6bd079f9c112aa13f6b8848fde225471b1cb27bd242ba01314cfe078b2172',
}
INK, HALO, GROUND = 12, 11, 0
LINES = ((24, 56, 48, 55, 'Change', 54), (12, 66, 56, 63, 'Re-creation', 62))      # box x0 x1 y0 y1, old word, baseline
CAPCOM_KEY = 'gk2_select_short_en'
CAPCOM_TEXT = 'Switch re-creations'


class ButtonError(ValueError):
    pass


# the letters the old words lack, built from the face's strokes (rows top to bottom, '1' ink); top is the row of the
# first row above the baseline (negative), adv the pen advance (ink width + 1)
BUILT = {
    'S': (('01110', '10001', '01100', '00010', '10001', '01110'), -5, 6),
    'w': (('10001', '10001', '10101', '10101', '01010'), -4, 6),
    's': (('0111', '1000', '0110', '0001', '1110'), -4, 5),
}


def capcom_lines(loc_en):
    """The two lines of the button from Capcom's own string; raises if the string is not there."""
    import re
    found = False
    for row in loc_en.get(CAPCOM_KEY, []):
        for x in row:
            if isinstance(x, str) and re.sub(r'<[^>]*>', '', x) == CAPCOM_TEXT:
                found = True
    if not found:
        raise ButtonError('Capcom\'s %r is not in %s' % (CAPCOM_TEXT, CAPCOM_KEY))
    first, second = CAPCOM_TEXT.split(' ')
    return first, second


def build_face(grid):
    """Cut the face out of the button's old words and prove it redraws them. -> (Face, {line index: (left, right)})."""
    face = rn.Face(3)
    spans = {}
    for i, (x0, x1, y0, y1, text, base) in enumerate(LINES):
        rn.harvest(face, grid, (x0, x1, y0, y1), INK, text, 'idlocal %d cell %d line %d' % (TILES, CELL, i + 1))
        m = rn.ink_mask(grid, INK, (x0, x1, y0, y1))
        spans[i] = (min(x for x, _ in m), max(x for x, _ in m))
    style = rn.Style(INK, HALO, HALO, GROUND)
    redraw = np.zeros_like(grid)
    for i, (x0, x1, y0, y1, text, base) in enumerate(LINES):
        pts, _lr = rn.layout(face, text, spans[i][0], base)
        rn.paint(redraw, pts, style)
    # both words together against the fan's pixels over their rows, the two arrows beside the first line left out
    for yy in range(47, 65):
        for xx in range(10, 70):
            if yy < 56 and (xx < 24 or xx > 56):
                continue
            old = grid[yy, xx] if grid[yy, xx] in (INK, HALO) else 0
            if redraw[yy, xx] != old:
                raise ButtonError('the cut letters do not redraw the old words: pixel (%d,%d) is %d, the fan\'s %d' % (xx, yy, redraw[yy, xx], old))
    for ch, (bits, top, adv) in BUILT.items():
        face.add(ch, bits, top, adv, 'built')
    return face, spans


def write_cell(B, k, old, new):
    """Bundle.write that also handles the card's overlapping OBJs: a pixel covered by two OBJs is written in the one that
    draws it now (the first non-transparent), else in the topmost."""
    x0, y0, _x1, _y1 = B.bbox(k)
    n = 0
    for y, x in zip(*np.nonzero(old != new)):
        cover = []
        for o in B.cells[k]:
            px, py = x + x0 - o['x'], y + y0 - o['y']
            if 0 <= px < o['w'] and 0 <= py < o['h']:
                t, tx, ty = B.tile_of(o, px, py)
                b = B.new[B.tile_off + t * 32 + ty * 4 + tx // 2]
                cover.append((o, t, tx, ty, (b >> 4) if tx & 1 else (b & 15)))
        if not cover:
            raise ButtonError('pixel (%d,%d) is drawn by no OBJ' % (x, y))
        lit = [c for c in cover if c[4] != 0]
        pick = lit[0] if lit else cover[0]
        if any(c[4] != 0 for c in cover[:cover.index(pick)]):
            raise ButtonError('pixel (%d,%d): an OBJ above the one written is not transparent' % (x, y))
        o, t, tx, ty, _v = pick
        if t >= B.ntiles:
            raise ButtonError('pixel (%d,%d) is in tile %d of %d' % (x, y, t, B.ntiles))
        off = B.tile_off + t * 32 + ty * 4 + tx // 2
        v = B.new[off]
        B.new[off] = (v & 0x0F) | (int(new[y, x]) << 4) if tx & 1 else (v & 0xF0) | int(new[y, x])
        n += 1
    return n


def new_grid(face, spans, grid, lines):
    """The cell with the old words erased and Capcom's painted, centred on the old ones."""
    style = rn.Style(INK, HALO, HALO, GROUND)
    new = grid.copy()
    for i, (x0, x1, y0, y1, text, base) in enumerate(LINES):
        pts, _lr = rn.layout(face, text, spans[i][0], base)
        # only the old ink and its halo go back to the ground (nothing is written where no OBJ draws)
        orth, diag = rn.ring_of(pts)
        for (x, y) in pts | orth | diag:
            if 0 <= y < new.shape[0] and 0 <= x < new.shape[1] and grid[y, x] in (INK, HALO):
                new[y, x] = GROUND
    dropped = 0
    for i, (x0, x1, y0, y1, text, base) in enumerate(LINES):
        word = lines[i]
        w = rn.text_width(face, word)
        centre = (spans[i][0] + spans[i][1]) / 2.0
        x = int(np.floor(centre - (w - 1) / 2.0 + 0.5))
        pts, (l, r) = rn.layout(face, word, x, base)
        before = new.copy()
        rn.paint(new, pts, style)
        for yy in range(new.shape[0]):
            for xx in range(new.shape[1]):
                if grid[yy, xx] < 0 and new[yy, xx] != before[yy, xx]:
                    if new[yy, xx] == INK:
                        raise ButtonError('%r: ink at (%d,%d) would fall where the card has no OBJ' % (word, xx, yy))
                    new[yy, xx] = grid[yy, xx]
                    dropped += 1
    return new, dropped


def patch_idlocal(idl_bytes, loc_en, log=None):
    """-> (new idlocal bytes, info). Raises ButtonError on anything that is not what the routine was proven on."""
    from choice_strips import Idlocal, rebuild
    log = log or (lambda s: None)
    idl = Idlocal(idl_bytes)
    for e in (CELLS, TILES, PALETTE):
        want = FAN_SHA256[e]
        have = hashlib.sha256(idl.blob(e)).hexdigest()
        if have != want:
            raise ButtonError('idlocal entry %d sha256 %s is not the fan\'s' % (e, have[:12]))
    lines = capcom_lines(loc_en)
    B = rn.Bundle(idl.blob(CELLS), idl.blob(TILES))
    grid, _org = B.grid(CELL)
    face, spans = build_face(grid)
    new, dropped = new_grid(face, spans, grid, lines)
    n = write_cell(B, CELL, grid, new)
    back, _o = B.grid(CELL, use_new=True)
    if not np.array_equal(back, new):
        raise ButtonError('cell %d does not read back as the picture written' % CELL)
    for k in range(len(B.cells)):
        if k in (10, 11):
            continue
        a, _x = rn.Bundle(idl.blob(CELLS), idl.blob(TILES)).grid(k)
        b, _x = B.grid(k, use_new=True)
        if not np.array_equal(a, b):
            raise ButtonError('cell %d changed and should not have' % k)
    tiles = B.result()
    out = rebuild(idl_bytes, {TILES: tiles}, lz=(TILES,))
    fan_ext = _extent(idl_bytes, TILES)
    new_ext = _extent(out, TILES)
    from lz11 import compress
    stored = len(compress(tiles))
    if stored > fan_ext:
        raise ButtonError('idlocal entry %d would be stored in %d bytes, the fan\'s is %d; it must not be larger' % (TILES, stored, fan_ext))
    back = Idlocal(out)
    for e in range(idl.n):
        if e != TILES and _content(back, e) != _content(idl, e):
            raise ButtonError('idlocal entry %d changed and should not have' % e)
    info = dict(pixels=n, dropped_halo=dropped, lines=lines, stored=stored, fan_stored=fan_ext, decoded=len(tiles))
    log('menu button (idlocal %d, cells 10 and 11): %r / %r in the fan\'s face, %d px written (%d halo pixels dropped), '
        'decoded %d bytes, stored %d (fan %d)' % (TILES, lines[0], lines[1], n, dropped, len(tiles), stored, fan_ext))
    return out, info


def _extent(d, e):
    from choice_strips import Idlocal
    t = Idlocal(d)
    order = sorted(range(t.n), key=lambda i: t.ents[i][0])
    k = order.index(e)
    return (t.ents[order[k + 1]][0] if k + 1 < t.n else len(d)) - t.ents[e][0]


def _content(idl, e):
    b = idl.blob(e)
    size = idl.ents[e][1]
    return b if size & 0x80000000 else b[:size]


def apply_to_rom(rom, dumpdir, log=None, any_rom=False):
    """Run after the last step that writes jpn/idlocal.bin. -> (rom, changed)."""
    import json, io, title_logo
    from choice_strips import rom_file
    log = log or (lambda s: None)
    try:
        loc = json.load(io.open(os.path.join(dumpdir, 'loc_en.json'), encoding='utf-8'))
        new, _info = patch_idlocal(rom_file(rom, IDLOCAL), loc, log)
    except (ButtonError, rn.RoomNamesError) as e:
        if not any_rom:
            raise ButtonError('%s (pass --any-rom to build without the button text)' % e)
        log('menu button: NOT redrawn, --any-rom given (%s)' % e)
        return rom, False
    return title_logo.splice(rom, IDLOCAL, new), True
