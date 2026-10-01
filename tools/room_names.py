# -*- coding: utf-8 -*-
"""Capcom's room names on the cake-show map pictures.

The Mind map pieces of the cake show were lettered by the fan patch with the
fan's own room names (Gustavia's, Delicia's, Master's, Dover's). Capcom's own
English map (Collection texture cut02_003_eng, already used by cg_names.py for
the room map in jpn/upcut_local.bin entry 100) calls the four rooms Gusto's,
Scone's, Tangaroa's and Frost's. This tool re-letters the other places the fan
names are drawn, in place, in the fan's own lettering:

  jpn/cutobj_local.bin  entry 10   the three orange wedge sprites (map_font.json,
                                   the same face cg_names.py uses on entry 100)
  jpn/idlocal.bin       entry 321  the four-wedge map piece (small face)
  jpn/idlocal.bin       entry 324  the lit label "Master's Room" and its strip
  jpn/idlocal.bin       entry 327  the lit label "Delicia's Room" and its strip

No game picture is stored in the repository. The letters are cut out of the
fan's own labels at build time (see WEDGE_SOURCES, BIG_SOURCES and STRIP_SOURCES), and before anything is
written every source label is redrawn from the cut letters and compared with
the fan's pixels; one differing pixel stops the build.
"""
import sys, os, struct, json, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from lz11 import decompress, compress
from ncer import ncer
from nitro import ncgr, nclr, tile_pixels, _sections

HERE = os.path.dirname(os.path.abspath(__file__))


class RoomNamesError(ValueError):
    pass


# ---------------------------------------------------------------------------
# sprite bundles: cell rendering to an index grid and write-back into tiles
# ---------------------------------------------------------------------------
class Bundle(object):
    """A RECN (cells) + RGCN (4bpp tiles) pair. `tiles` is a bytearray copy of
    the RGCN so write-back can patch it."""

    def __init__(self, recn, rgcn):
        self.recn, self.rgcn = recn, rgcn
        self.cells, mapping = ncer(recn)
        self.boundary = 1 << (mapping & 3) if (mapping & 3) else 1
        data, bpp, self.ntiles, _w, _h = ncgr(rgcn)
        if bpp != 4:
            raise RoomNamesError('expected a 4bpp tile bank, got %dbpp' % bpp)
        p, _size, body = _sections(rgcn)[b'RAHC']
        dsize = struct.unpack_from('<I', body, 16)[0]
        doff = struct.unpack_from('<I', body, 20)[0]
        self.tile_off = p + 8 + doff
        self.tile_len = dsize
        self.new = bytearray(rgcn)

    def bbox(self, k):
        objs = self.cells[k]
        return (min(o['x'] for o in objs), min(o['y'] for o in objs),
                max(o['x'] + o['w'] for o in objs), max(o['y'] + o['h'] for o in objs))

    def tile_of(self, o, px, py):
        """(tile index, x in tile, y in tile) of an OBJ's pixel (px, py) given in OBJ space."""
        sx = o['w'] - 1 - px if o['hflip'] else px
        sy = o['h'] - 1 - py if o['vflip'] else py
        tw = o['w'] // 8
        return o['tile'] * self.boundary + (sy // 8) * tw + (sx // 8), sx % 8, sy % 8

    def grid(self, k, use_new=False):
        """Index grid (raw 4-bit values, no palette bank; -1 where no OBJ draws)
        of cell k, drawn like the hardware (the first OBJ is on top).
        -> (array, (x0, y0))."""
        x0, y0, x1, y1 = self.bbox(k)
        a = np.full((y1 - y0, x1 - x0), -1, np.int32)
        data = bytes(self.new if use_new else self.rgcn)
        for o in reversed(self.cells[k]):
            for py in range(o['h']):
                for px in range(o['w']):
                    t, tx, ty = self.tile_of(o, px, py)
                    b = data[self.tile_off + t * 32 + ty * 4 + tx // 2]
                    a[o['y'] - y0 + py, o['x'] - x0 + px] = (b >> 4) if tx & 1 else (b & 15)
        return a, (x0, y0)

    def write(self, k, old, new):
        """Patch the pixels where grid `new` differs from `old` (both grids of
        cell k). Each changed pixel must be drawn by exactly one OBJ of the cell
        (never an overlap) so the write cannot touch a tile the picture shows
        somewhere else in the same cell. Returns the number of pixels written."""
        x0, y0, _x1, _y1 = self.bbox(k)
        n = 0
        for y, x in zip(*np.nonzero(old != new)):
            cover = []
            for o in self.cells[k]:
                px, py = x + x0 - o['x'], y + y0 - o['y']
                if 0 <= px < o['w'] and 0 <= py < o['h']:
                    cover.append((o, px, py))
            if len(cover) != 1:
                raise RoomNamesError('cell %d pixel (%d,%d) is drawn by %d OBJs, expected 1' % (k, x, y, len(cover)))
            if new[y, x] < 0 or new[y, x] > 15:
                raise RoomNamesError('cell %d pixel (%d,%d): value %r is not a palette index' % (k, x, y, new[y, x]))
            o, px, py = cover[0]
            t, tx, ty = self.tile_of(o, px, py)
            if t >= self.ntiles:
                raise RoomNamesError('cell %d pixel (%d,%d) is in tile %d of %d' % (k, x, y, t, self.ntiles))
            off = self.tile_off + t * 32 + ty * 4 + tx // 2
            v = self.new[off]
            self.new[off] = (v & 0x0F) | (int(new[y, x]) << 4) if tx & 1 else (v & 0xF0) | int(new[y, x])
            n += 1
        return n

    def result(self):
        out = bytes(self.new)
        if len(out) != len(self.rgcn):
            raise RoomNamesError('RGCN changed size')
        return out


# ---------------------------------------------------------------------------
# faces: letters cut from the fan's own labels
# ---------------------------------------------------------------------------
class Face(object):
    """char -> (bits, top, adv): bits is a tuple of '0'/'1' rows, top the row of
    the glyph's first ink row relative to the baseline row (negative: above it),
    adv the pen advance.
    `space` is the pen advance of a blank."""

    def __init__(self, space):
        self.g = {}
        self.src = {}
        self.space = space

    def add(self, ch, bits, top, adv, src):
        if ch in self.g:
            if self.g[ch][:2] != (bits, top):
                self.src.setdefault(ch, []).append(('differs', src))
            else:
                self.src.setdefault(ch, []).append(('same', src))
            return
        self.g[ch] = (bits, top, adv)
        self.src[ch] = [('kept', src)]

    def width_of(self, ch):
        return len(self.g[ch][0][0])

    def __contains__(self, ch):
        return ch in self.g


def segment(mask, box):
    """Column runs of the ink pixels (a set of (x, y)) inside box (x0, x1, y0, y1),
    -> list of (x0, x1, y0, y1, frozenset of pixels)."""
    x0, x1, y0, y1 = box
    pts = [(x, y) for (x, y) in mask if x0 <= x <= x1 and y0 <= y <= y1]
    cols = sorted(set(x for x, _ in pts))
    runs, cur = [], []
    for x in cols:
        if cur and x != cur[-1] + 1:
            runs.append(cur); cur = []
        cur.append(x)
    if cur:
        runs.append(cur)
    out = []
    for r in runs:
        sel = [(x, y) for (x, y) in pts if r[0] <= x <= r[-1]]
        out.append((r[0], r[-1], min(y for _, y in sel), max(y for _, y in sel), frozenset(sel)))
    return out


def glyph_bits(run):
    x0, x1, y0, y1, pts = run
    return tuple(''.join('1' if (x, y) in pts else '0' for x in range(x0, x1 + 1)) for y in range(y0, y1 + 1))


def ink_mask(grid, ink, box):
    x0, x1, y0, y1 = box
    ys, xs = np.nonzero(grid[y0:y1 + 1, x0:x1 + 1] == ink)
    return set((int(x) + x0, int(y) + y0) for y, x in zip(ys, xs))


def harvest(face, grid, box, ink, text, src, base=None):
    """Cut the letters of one label into `face`. A glyph's `top` is counted from
    the label's baseline (the bottom ink row most letters share, or `base`).
    Raises if the number of column runs is not the number of letters."""
    m = ink_mask(grid, ink, box)
    runs = segment(m, box)
    letters = [c for c in text if c != ' ']
    if len(runs) != len(letters):
        raise RoomNamesError('%s: %d column runs for %r (%d letters)' % (src, len(runs), text, len(letters)))
    if base is None:
        base = collections.Counter(r[3] for r in runs).most_common(1)[0][0]
    for ch, r in zip(letters, runs):
        face.add(ch, glyph_bits(r), r[2] - base, (r[1] - r[0] + 1) + 1, src)
    return runs


def layout(face, text, x, y0, spacing=0, kern=None):
    """Ink pixels of `text` with the pen starting at column x, baseline row y0.
    `kern` maps a letter index to a pixel shift applied from that letter on.
    -> (set of (x, y), (left, right) ink columns)."""
    pts, pen = set(), x
    shift = 0
    first = last = None
    for i, ch in enumerate(text):
        if kern and i in kern:
            shift += kern[i]
        if ch == ' ':
            pen += face.space + spacing
            continue
        bits, top, adv = face.g[ch]
        for ry, row in enumerate(bits):
            for rx, c in enumerate(row):
                if c == '1':
                    pts.add((pen + shift + rx, y0 + top + ry))
        if first is None:
            first = pen + shift
        last = pen + shift + len(bits[0]) - 1
        pen += adv + spacing
    return pts, (first, last)


def text_width(face, text, spacing=0, kern=None):
    pts, (a, b) = layout(face, text, 0, 0, spacing, kern)
    return b - a + 1


class Style(object):
    """ink / orthogonal halo / diagonal-corner halo, and the ground a label
    stands on: an int, or a function (x, y) -> index."""

    def __init__(self, ink, halo, halo2=None, ground=0):
        self.ink, self.halo = ink, halo
        self.halo2 = halo if halo2 is None else halo2
        self.ground = ground

    def ground_at(self, x, y):
        return self.ground(x, y) if callable(self.ground) else self.ground


def ring_of(mask):
    """-> (orthogonal ring, diagonal-only ring) of a set of pixels."""
    orth, diag = set(), set()
    for (x, y) in mask:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if q not in mask:
                orth.add(q)
    for (x, y) in mask:
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            q = (x + dx, y + dy)
            if q not in mask and q not in orth:
                diag.add(q)
    return orth, diag


def erase(grid, mask, style, org=(0, 0)):
    """Old label (ink mask) and its 8-neighbour halo go back to the ground."""
    orth, diag = ring_of(mask)
    for (x, y) in mask | orth | diag:
        if 0 <= y < grid.shape[0] and 0 <= x < grid.shape[1]:
            grid[y, x] = style.ground_at(x + org[0], y + org[1])


def paint(grid, mask, style):
    """Halo first (orthogonal ring, then diagonal corners), ink on top."""
    orth, diag = ring_of(mask)
    h, w = grid.shape
    for q in diag:
        if 0 <= q[0] < w and 0 <= q[1] < h:
            grid[q[1], q[0]] = style.halo2
    for q in orth:
        if 0 <= q[0] < w and 0 <= q[1] < h:
            grid[q[1], q[0]] = style.halo
    for (x, y) in mask:
        if 0 <= x < w and 0 <= y < h:
            grid[y, x] = style.ink


# ---------------------------------------------------------------------------
# where the letters come from (idlocal picture entry, cell, box x0 x1 y0 y1, ink, text)
# ---------------------------------------------------------------------------
# The small wedge face (Master's / Delicia's / Dover's / Room, the four-wedge map
# piece and the Summer / Winter / Spring / Autumn Palace piece). The fan squeezed
# Gustavia's and Master's (3 px a, s, e, u, v), so those two come last and only
# fill letters the others lack (G); the squeezed variants are kept in a face of
# their own for the layout options. The fan's map pictures have no T, F or hyphen
# in this face anywhere, so those three are borrowed from the Temp. / Film Lot
# labels and the Work- label (cap T and F and the bar are the same shape in
# every face the fan used; see the comparison in the results notes).
WEDGE_SOURCES = [
    (321, 0, (96, 127, 34, 43), 7, "Delicia's"),
    (321, 0, (111, 140, 63, 72), 12, "Dover's"),
    (321, 0, (11, 30, 75, 83), 7, "Room"),
    (315, 0, (28, 60, 33, 43), 12, "Summer"),
    (315, 0, (95, 125, 33, 43), 7, "Winter"),
    (315, 0, (12, 42, 62, 72), 12, "Spring"),
    (315, 0, (109, 142, 62, 72), 7, "Autumn"),
    (321, 0, (26, 62, 34, 43), 12, "Gustavia's"),
]
WEDGE_BORROWED = [
    (340, 0, (13, 17, 23, 32), 13, "T", 31),
    (340, 0, (13, 17, 34, 43), 13, "F", 42),
    (306, 0, (121, 123, 42, 52), 7, "-", 50),
]
WEDGE_SQUEEZED = [
    (321, 0, (11, 42, 63, 72), 7, "Master's"),
    (321, 0, (26, 62, 34, 43), 12, "Gustavia's"),
]
WEDGE_SPACE = 5
BIG_SOURCES = [
    (324, 0, (38, 83, 50, 62), 9, "Master's"),
    (324, 0, (89, 113, 50, 62), 9, "Room"),
    (327, 0, (38, 85, 50, 62), 9, "Delicia's"),
    (321, 0, (54, 97, 64, 73), 9, "Fountain"),
    (321, 0, (54, 80, 75, 84), 9, "Patio"),
    (282, 0, (60, 92, 64, 74), 9, "Stage"),
    (309, 0, (74, 110, 64, 76), 9, "Special"),
    (309, 0, (74, 90, 78, 87), 9, "Cell"),
    (331, 0, (55, 90, 58, 68), 9, "Viewing"),
    (331, 0, (55, 97, 70, 79), 9, "Platform"),
    (340, 0, (44, 74, 79, 88), 9, "Tower"),
    (340, 0, (81, 107, 79, 88), 9, "Plaza"),
]
BIG_SPACE = 5
STRIP_CELL = 1
STRIP_SOURCES = [
    (331, STRIP_CELL, "Grand Tower: Viewing Platform"),
    (309, STRIP_CELL, "Prison: Special Cell"),
    (327, STRIP_CELL, "Contest Venue: Delicia's Room"),
    (321, STRIP_CELL, "Contest Venue: Fountain Patio"),
    (324, STRIP_CELL, "Contest Venue: Master's Room"),
]
STRIP_SPACE = 2
STRIP_FILL, STRIP_SHADOW = 4, 3

# decoded sha256 of the fan's entries the letters and targets are read from
FAN_SHA256 = {
    281: '216906eaaf31cb16692ef9473fb0b1c04f9abf7266a5806d7453555ddf1d59b4',
    282: '180a8ad8580b2d64ae2499e5a833fd3884a99274039409c2e7fdbe8c572aad31',
    305: 'ffbe460fe4221b78df60a3caceb6de8688670a9097f5380adc898b4da7f2fd0e',
    306: '46496d74c57349bf5f9194460e3179cbea944428ff729484328f9d38ec7ac0a8',
    308: '62f472176821952c13dfdab538301a54371645ffdd6dbfe7912177d6c88b9d8f',
    309: 'adb920dfdbd0a7caaa7c8d47373e6f447ae6a238794507f51e6401219e40041b',
    314: 'a78ac800d9d6e7c6fc88b48938a3f21a2ee6fc82d6d798040eee8908b361faa2',
    315: 'd9d578002929e55927de255da5f0f54d945718894b484f96f34ef0ebb72c51a6',
    320: '3202ec0db83ea97761786e857402430d709f8d40d2de5ad6e43fc4c3b1e2827a',
    321: 'c407c9c43aa123d0f97fc530bc539ef3e773b0663dfe192e7d83e0749d4052c1',
    323: 'e02e89b25221e782b914c4c1ad75c0eba01960ef26e15c15d8f72dc0d9931258',
    324: 'e13ef2756a92c7b7633d825b66942c706fc32c24f83b2be72dee96f22beeca9d',
    326: 'e02e89b25221e782b914c4c1ad75c0eba01960ef26e15c15d8f72dc0d9931258',
    327: '93dcf394c43643335a6ca116dc9d0535bdbe1e1b833b06449e52bcced719d6bc',
    330: 'dc15030240db842edc366b9391401c5b53c21a9abb6da6d9f5052b5da437b84e',
    331: '8099ead468231f7ef30229397e79d337d38332290a01e27cf0fc8ca6f974b197',
    339: '25d718151a0ca7c741e828459c4736cb5cf4166dfd0b4eee02ff3d7b75efee01',
    340: '429ec49ccc2fe7be6fcf24d5c7c75327590cd3fa62c1e5a7af31818ca6cebe9f',
}
CUTOBJ_ENTRY = 10
CUTOBJ_SHA256 = 'e11aa4c33e360a5e9c286e676f02e440ec4ae497a13dbc6cddd96420d22e7351'


class Source(object):
    """The fan's idlocal, read through its picture bundles (entry g is the RGCN,
    g - 1 its RECN); grids are cached."""

    def __init__(self, idl):
        self.idl = idl
        self.b, self.cache = {}, {}

    def bundle(self, g):
        if g not in self.b:
            self.b[g] = Bundle(self.idl.blob(g - 1), self.idl.blob(g))
        return self.b[g]

    def grid(self, g, k=0):
        if (g, k) not in self.cache:
            self.cache[(g, k)] = self.bundle(g).grid(k)[0]
        return self.cache[(g, k)]


def build_faces(src):
    """-> dict of Face: 'wedge', 'squeezed', 'big', 'strip'."""
    wedge = Face(WEDGE_SPACE)
    for g, k, box, ink, text in WEDGE_SOURCES:
        harvest(wedge, src.grid(g, k), box, ink, text, '%d %s' % (g, text))
    for g, k, box, ink, text, base in WEDGE_BORROWED:
        harvest(wedge, src.grid(g, k), box, ink, text, '%d %s (borrowed)' % (g, text), base=base)
    squeezed = Face(WEDGE_SPACE)
    for g, k, box, ink, text in WEDGE_SQUEEZED:
        harvest(squeezed, src.grid(g, k), box, ink, text, '%d %s' % (g, text))
    big = Face(BIG_SPACE)
    for g, k, box, ink, text in BIG_SOURCES:
        harvest(big, src.grid(g, k), box, ink, text, '%d %s' % (g, text))
    strip = Face(STRIP_SPACE)
    for g, k, text in STRIP_SOURCES:
        a = src.grid(g, k)
        harvest(strip, a, (0, a.shape[1] - 1, 0, a.shape[0] - 1), STRIP_FILL, text, '%d %s' % (g, text))
    return {'wedge': wedge, 'squeezed': squeezed, 'big': big, 'strip': strip}


# ---------------------------------------------------------------------------
# idlocal 321: the four-wedge map piece
# ---------------------------------------------------------------------------
LIT_WEDGE = Style(7, 3, 3, 5)
DIM_WEDGE = Style(12, 3, 3, lambda x, y: 3 if (x + y) % 2 == 0 else 4)   # checker, 3 on even x+y
# old text, new text, box of the old name, ink, style, anchor ('c' keeps the
# old label's centre, 'l' its left edge); the second line "Room" stays
WEDGE_LABELS = [
    ("Gustavia's", "Gusto's", (26, 62, 34, 43), 12, DIM_WEDGE, 'c'),
    ("Delicia's", "Scone's", (96, 127, 34, 43), 7, LIT_WEDGE, 'l'),
    ("Master's", "Tangaroa's", (11, 42, 63, 72), 7, LIT_WEDGE, 'l'),
    ("Dover's", "Frost's", (111, 140, 63, 72), 12, DIM_WEDGE, 'l'),
]
# THE one switch for the Tangaroa's wedge layout (see TANGAROA_OPTIONS). A
# placeholder until the primary has judged the renders.
TANGAROA_OPTION = 'B'


def old_label(grid, box, ink, text):
    """-> (ink mask, ink columns (left, right), baseline row) of a label."""
    m = ink_mask(grid, ink, box)
    runs = segment(m, box)
    letters = [c for c in text if c != ' ']
    if len(runs) != len(letters):
        raise RoomNamesError('label %r: %d column runs for %d letters' % (text, len(runs), len(letters)))
    base = collections.Counter(r[3] for r in runs).most_common(1)[0][0]
    return m, (min(r[0] for r in runs), max(r[1] for r in runs)), base


def tight_kern(face, text, by=1):
    """Pull each letter `by` px left of its pen where that keeps every ink pixel
    of the letter at least two px (8-neighbour clear) from the previous letter's,
    greedy from the left, shifts accumulate. -> {letter index: -by or 0}."""
    kern, shift, prev = {}, 0, None
    pen = 0
    for i, ch in enumerate(text):
        if ch == ' ':
            pen += face.space
            prev = None
            continue
        bits, top, adv = face.g[ch]
        pts = set((pen + rx, top + ry) for ry, row in enumerate(bits) for rx, c in enumerate(row) if c == '1')
        if prev is not None:
            moved = set((x + shift - by, y) for x, y in pts)
            clear = all(abs(x - px) > 1 or abs(y - py) > 1 for x, y in moved for px, py in prev)
            if clear:
                shift -= by
                kern[i] = -by
        prev = set((x + shift, y) for x, y in pts)
        pen += adv
    return kern


def interior(grid, seed, value):
    """4-connected region of `value` pixels around seed."""
    h, w = grid.shape
    seen = {seed}
    st = [seed]
    while st:
        x, y = st.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if 0 <= q[0] < w and 0 <= q[1] < h and q not in seen and grid[q[1], q[0]] == value:
                seen.add(q); st.append(q)
    return seen


TANGAROA_OPTIONS = {
    'A': "wedge face, normal spacing, over the dome border",
    'B': "wedge face, letters pulled 1 px closer where they stay clear",
    'C': "three lines: Tanga- / roa's / Room",
    'D': "the strip's face, normal spacing",
    'E': "the fan's squeezed letters (a, s) where it has them",
    'F': "the fan's squeezed letters, pulled 1 px closer where clear",
    'G': "as F, and the dome's Fountain / Patio label moved right as far as the dome allows",
    "G'": "as F, and the dome label moved right only while it stays within 2 px of its balance",
}
# The dome's own label (321, big face, ink 9) in the lit dome, and where the
# measuring starts inside the dome.
FOUNTAIN_BOX = (52, 100, 62, 87)
DOME_SEED = (75, 90)
DOME_GROUND = 7
BALANCE_SLACK = 2          # option G': left-minus-right margin may move this many px


def mixed_face(faces):
    """The wedge face with the fan's squeezed variants (Master's, Gustavia's)
    where it drew them."""
    f = Face(faces['wedge'].space)
    f.g = dict(faces['wedge'].g)
    for ch, v in faces['squeezed'].g.items():
        f.g[ch] = v
    return f


def tangaroa_lines(opt, faces, left, base):
    """The name line(s) of the Tangaroa's wedge for an option:
    [(text, x, baseline, face, kern)]. Option C returns the two name lines;
    the caller moves nothing else (Room stays where the fan has it)."""
    if opt not in TANGAROA_OPTIONS:
        raise RoomNamesError('unknown Tangaroa wedge option %r' % (opt,))
    name = "Tangaroa's"
    wedge = faces['wedge']
    if opt == 'A':
        return [(name, left, base, wedge, None)]
    if opt == 'B':
        return [(name, left, base, wedge, tight_kern(wedge, name))]
    if opt == 'C':
        return [("Tanga-", left, base - 11, wedge, None), ("roa's", left, base, wedge, None)]
    if opt == 'D':
        return [(name, left, base, faces['strip'], None)]
    mixed = mixed_face(faces)
    if opt == 'E':
        return [(name, left, base, mixed, None)]
    return [(name, left, base, mixed, tight_kern(mixed, name))]    # F, G, G'


def dome_label(grid):
    """The dome's own label in cell 0 of idlocal 321: -> dict with its ink mask,
    the dome's interior (ground left after the label is taken out), and the spare
    ground between the label (ink and halo) and the dome edge, per row, per line
    and overall."""
    m = ink_mask(grid, 9, FOUNTAIN_BOX)
    g = grid.copy()
    erase(g, m, BIG_LIT)
    inside = interior(g, DOME_SEED, DOME_GROUND)
    row_lo, row_hi = {}, {}
    for (x, y) in inside:
        row_lo[y] = min(row_lo.get(y, 999), x)
        row_hi[y] = max(row_hi.get(y, -1), x)
    orth, diag = ring_of(m)
    allp = m | orth | diag
    rows = sorted(set(y for _, y in allp))
    spare = {}
    for y in rows:
        xs = [x for x, yy in allp if yy == y]
        spare[y] = (min(xs) - row_lo[y], row_hi[y] - max(xs))
    lines, cur = [], [rows[0]]
    for y in rows[1:]:
        if y - cur[-1] > 1:
            lines.append(cur); cur = []
        cur.append(y)
    lines.append(cur)
    per_line = [(min(spare[y][0] for y in ln), min(spare[y][1] for y in ln), ln[0], ln[-1]) for ln in lines]
    left = min(v[0] for v in spare.values())
    right = min(v[1] for v in spare.values())
    return dict(ink=m, inside=inside, erased=g, spare=spare, per_line=per_line, left=left, right=right,
                box=(min(x for x, _ in allp), max(x for x, _ in allp)))


def dome_shift(opt, dl):
    """Columns the dome label moves right for an option (0 unless G or G')."""
    if opt == 'G':
        return dl['right']
    if opt == "G'":
        base = dl['left'] - dl['right']
        k = 0
        while k < dl['right'] and abs((dl['left'] + k + 1) - (dl['right'] - k - 1) - base) <= BALANCE_SLACK:
            k += 1
        return k
    return 0


def ink_gap(lines, label_ink, shift):
    """Fewest empty columns between the Tangaroa's ink and the dome label's ink
    (rows within 1 of each other); negative if they cross."""
    t = set()
    for text, x, b, face, kern in lines:
        t |= layout(face, text, x, b, 0, kern)[0]
    best = 999
    for (x, y) in t:
        for (lx, ly) in label_ink:
            if abs(ly - y) <= 1:
                best = min(best, lx + shift - x - 1)
    return best


def name_overlap(lines, label_ink, shift):
    """Pixels where the Tangaroa's lines (ink and halo) and the dome label (ink and
    halo) share a pixel after the label moves `shift` right.
    -> (ink on ink, ink on label halo, halo on label ink, halo on halo)."""
    t = set()
    for text, x, b, face, kern in lines:
        t |= layout(face, text, x, b, 0, kern)[0]
    th = set().union(*ring_of(t))
    li = set((x + shift, y) for x, y in label_ink)
    lh = set().union(*ring_of(li))
    return (len(t & li), len(t & lh), len(th & li), len(th & lh))


def wedge_measure(erased, lines, style, seed):
    """How far the lines reach past the wedge's ground (the interior around
    `seed`). -> dict(ink, width, ink_out, halo_out, over) where over is the
    largest number of columns an ink pixel sits right of the last interior
    pixel of its row."""
    inside = interior(erased, seed, style.ground if not callable(style.ground) else 5)
    right = {}
    for (x, y) in inside:
        right[y] = max(right.get(y, -1), x)
    ink = set()
    for text, x, base, face, kern in lines:
        m, _ = layout(face, text, x, base, 0, kern)
        ink |= m
    orth, diag = ring_of(ink)
    halo = orth | diag
    over = 0
    for (x, y) in ink:
        r = right.get(y)
        over = max(over, (x - r) if r is not None else 99)
    xs = [x for x, _ in ink]
    return dict(ink=len(ink), left=min(xs), right=max(xs), width=max(xs) - min(xs) + 1,
                ink_out=sum(1 for q in ink if q not in inside),
                halo_out=sum(1 for q in halo if q not in inside), over=over)


# ---------------------------------------------------------------------------
# proofs: every label the tool replaces is first redrawn from letters cut out of
# that same label and compared with the fan's pixels
# ---------------------------------------------------------------------------
# One pixel of the fan's drawing breaks its own halo rule (a corner of the halo
# left unpainted beside the v of "Dover's" on the four-wedge piece).
FAN_QUIRKS = {(321, "Dover's"): {(126, 71)}}


def _prove(name, a0, redraw, quirks=()):
    diff = set((int(x), int(y)) for y, x in np.argwhere(redraw != a0)) - set(quirks)
    if diff:
        raise RoomNamesError('%s: redrawing the fan\'s own label differs from the fan in %d pixels (first %s)'
                             % (name, len(diff), sorted(diff)[:4]))


def prove_wedge(src):
    a0 = src.grid(321, 0)
    for old, new, box, ink, style, anchor in WEDGE_LABELS:
        m, (l, r), base = old_label(a0, box, ink, old)
        f = Face(WEDGE_SPACE)
        harvest(f, a0, box, ink, old, 'self')
        g = a0.copy()
        erase(g, m, style)
        paint(g, layout(f, old, l, base)[0], style)
        _prove('idlocal 321 %s' % old, a0, g, FAN_QUIRKS.get((321, old), ()))


BIG_LIT = Style(9, 12, 12, 7)
BIG_BOX = (36, 116, 48, 64)
STRIP_BOX = (0, 159, 0, 15)


def _runs_label(grid, box, ink, text):
    m = ink_mask(grid, ink, box)
    runs = segment(m, box)
    if len(runs) != len([c for c in text if c != ' ']):
        raise RoomNamesError('%d column runs for %r' % (len(runs), text))
    base = collections.Counter(r[3] for r in runs).most_common(1)[0][0]
    return m, runs, base


def _word_space(runs, text):
    """Pen gap of the first blank of `text` (letters only in `runs`)."""
    n1 = len(text.split(' ')[0])
    return runs[n1][0] - runs[n1 - 1][1] - 2


def paint_strip(grid, mask):
    for (x, y) in mask:
        for dx, dy in ((0, 1), (1, 1)):
            q = (x + dx, y + dy)
            if q not in mask and 0 <= q[0] < grid.shape[1] and 0 <= q[1] < grid.shape[0]:
                grid[q[1], q[0]] = STRIP_SHADOW
    for (x, y) in mask:
        grid[y, x] = STRIP_FILL


def _strip_parts(a0, text):
    """-> (runs, baseline, x where the room name starts, space inside the name)."""
    m, runs, base = _runs_label(a0, STRIP_BOX, STRIP_FILL, text)
    letters = [c for c in text if c != ' ']
    ci = letters.index(':')
    name = text.split(': ')[1]
    sp = _word_space(runs[ci + 1:], name)
    return m, runs, base, runs[ci + 1][0], sp


def prove_big(src):
    for g, text in ((324, "Master's Room"), (327, "Delicia's Room")):
        a0 = src.grid(g, 0)
        m, runs, base = _runs_label(a0, BIG_BOX, 9, text)
        f = Face(_word_space(runs, text))
        harvest(f, a0, BIG_BOX, 9, text, 'self')
        gg = a0.copy()
        erase(gg, m, BIG_LIT)
        paint(gg, layout(f, text, runs[0][0], base)[0], BIG_LIT)
        _prove('idlocal %d %s' % (g, text), a0, gg)
    for g, text in ((324, "Contest Venue: Master's Room"), (327, "Contest Venue: Delicia's Room")):
        a0 = src.grid(g, STRIP_CELL)
        m, runs, base, x_name, sp = _strip_parts(a0, text)
        f = Face(sp)
        harvest(f, a0, STRIP_BOX, STRIP_FILL, text, 'self')
        gg = a0.copy()
        gg[:, x_name - 2:] = 0
        mask = layout(f, text.split(': ')[1], x_name, base)[0]
        paint_strip(gg, mask)
        _prove('idlocal %d strip' % g, a0, gg)


# ---------------------------------------------------------------------------
# the patches
# ---------------------------------------------------------------------------
BIG_NAMES = {324: ["Tangaroa's", "Room"], 327: ["Scone's Room"]}
STRIP_NAMES = {324: "Tangaroa's Room", 327: "Scone's Room"}
BIG_PITCH = 11            # the fan's two-line labels (Fountain / Patio) sit 11 rows apart
BIG_INTERIOR_SEED = (40, 40)


def patch_wedge(src, faces, option, info):
    """idlocal 321 -> new RGCN bytes."""
    B = Bundle(src.idl.blob(320), src.idl.blob(321))
    old, _ = B.grid(0)
    new = old.copy()
    work = []
    for old_t, new_t, box, ink, style, anchor in WEDGE_LABELS:
        m, (l, r), base = old_label(old, box, ink, old_t)
        erase(new, m, style)
        work.append((old_t, new_t, style, anchor, l, r, base))
    erased = new.copy()
    for old_t, new_t, style, anchor, l, r, base in work:
        if new_t == "Tangaroa's":
            lines = tangaroa_lines(option, faces, l, base)
            info['tangaroa'] = wedge_measure(erased, lines, style, (20, 70))
            info['tangaroa']['option'] = option
        else:
            w = text_width(faces['wedge'], new_t)
            x0 = l if anchor == 'l' else l + ((r - l + 1) - w) // 2
            lines = [(new_t, x0, base, faces['wedge'], None)]
            info.setdefault('wedge', {})[new_t] = (x0, x0 + w - 1, old_t, l, r)
        for text, x, b, face, kern in lines:
            paint(new, layout(face, text, x, b, 0, kern)[0], style)
    dl = dome_label(old)
    shift = dome_shift(option, dl)
    info['dome'] = dict(shift=shift, left=dl['left'], right=dl['right'], per_line=dl['per_line'], box=dl['box'])
    t_lines = tangaroa_lines(option, faces, work[2][4], work[2][6])
    info['dome']['overlap'] = name_overlap(t_lines, dl['ink'], shift)
    info['dome']['ink_gap'] = ink_gap(t_lines, dl['ink'], shift)
    if shift:
        erase(new, dl['ink'], BIG_LIT)
        moved = set((x + shift, y) for x, y in dl['ink'])
        paint(new, moved, BIG_LIT)
        orth, diag = ring_of(moved)
        if any(q not in dl['inside'] for q in moved | orth | diag):
            raise RoomNamesError('the dome label moved %d px leaves the dome' % shift)
    info['wedge_px'] = B.write(0, old, new)
    return B.result()


def patch_big(src, faces, g, info):
    """idlocal 324 / 327 -> new RGCN bytes (lit label and strip)."""
    B = Bundle(src.idl.blob(g - 1), src.idl.blob(g))
    big = faces['big']
    # the lit label
    old, _ = B.grid(0)
    new = old.copy()
    old_t = {324: "Master's Room", 327: "Delicia's Room"}[g]
    m, runs, base = _runs_label(old, BIG_BOX, 9, old_t)
    erase(new, m, BIG_LIT)
    l, r = runs[0][0], runs[-1][1]
    sp = _word_space(runs, old_t)
    inside = interior(new, BIG_INTERIOR_SEED, 7)
    xs = [p[0] for p in inside]; ys = [p[1] for p in inside]
    ix0, ix1, iy0, iy1 = min(xs), max(xs), min(ys), max(ys)
    big.space = sp
    lines = BIG_NAMES[g]
    widths = [text_width(big, t) for t in lines]
    bw = max(widths)
    rows = 8 + (len(lines) - 1) * BIG_PITCH
    top = int(np.ceil((iy0 + iy1) / 2.0 - rows / 2.0))     # first ink row of the block, centred in the lit box
    if len(lines) == 1:
        x_left = l + ((r - l + 1) - bw) // 2          # the old label's centre
    else:
        x_left = ix0 + ((ix1 - ix0 + 1) - bw) // 2     # the block centred in the lit box
    placed = []
    for i, t in enumerate(lines):
        b = top + 7 + i * BIG_PITCH
        mask, (a, z) = layout(big, t, x_left, b)
        paint(new, mask, BIG_LIT)
        placed.append((t, a, z, b))
    ink_all = set()
    for t, a, z, b in placed:
        ink_all |= layout(big, t, x_left, b)[0]
    orth, diag = ring_of(ink_all)
    if any(q not in inside for q in ink_all | orth | diag):
        raise RoomNamesError('idlocal %d: the new label leaves the lit box' % g)
    info.setdefault('big', {})[g] = dict(old=(l, r, base), lines=placed, box=(ix0, ix1, iy0, iy1), space=sp)
    px = B.write(0, old, new)
    # the strip: keep "Contest Venue: ", draw the new name from where the old one began
    sold, _ = B.grid(STRIP_CELL)
    stext = {324: "Contest Venue: Master's Room", 327: "Contest Venue: Delicia's Room"}[g]
    _m, sruns, sbase, x_name, ssp = _strip_parts(sold, stext)
    strip = faces['strip']
    strip.space = ssp
    snew = sold.copy()
    snew[:, x_name - 2:] = 0
    mask, (a, z) = layout(strip, STRIP_NAMES[g], x_name, sbase)
    if z > STRIP_BOX[1] - 1:
        raise RoomNamesError('idlocal %d strip: the name ends at column %d of 160' % (g, z))
    paint_strip(snew, mask)
    px += B.write(STRIP_CELL, sold, snew)
    info.setdefault('strip', {})[g] = dict(x=x_name, end=z, old_end=sruns[-1][1], space=ssp)
    info.setdefault('px', {})[g] = px
    return B.result()


def _content(idl, e):
    """An entry's bytes as the table sizes them (a stored-raw entry is cut at its
    size field, since the extent also holds the alignment pad)."""
    b = idl.blob(e)
    size = idl.ents[e][1]
    return b if size & 0x80000000 else b[:size]


def patch_idlocal(idl_bytes, option=None, log=None):
    """-> (new idlocal bytes, info). Raises RoomNamesError on anything that is
    not what the routine was proven on."""
    from choice_strips import Idlocal, rebuild
    log = log or (lambda s: None)
    option = option or TANGAROA_OPTION
    idl = Idlocal(idl_bytes)
    for e, sha in sorted(FAN_SHA256.items()):
        have = hashlib.sha256(idl.blob(e)).hexdigest()
        if have != sha:
            raise RoomNamesError('idlocal entry %d sha256 %s is not the fan\'s' % (e, have[:12]))
    src = Source(idl)
    faces = build_faces(src)
    prove_wedge(src)
    prove_big(src)
    info = {'option': option}
    repl = {321: patch_wedge(src, faces, option, info),
            324: patch_big(src, faces, 324, info),
            327: patch_big(src, faces, 327, info)}
    out = rebuild(idl_bytes, repl, lz=tuple(sorted(repl)))
    back = Idlocal(out)
    order = sorted(range(idl.n), key=lambda i: idl.ents[i][0])
    border = sorted(range(back.n), key=lambda i: back.ents[i][0])
    info['stored'] = {}
    for e in sorted(repl):
        if back.blob(e) != repl[e] or len(back.blob(e)) != len(idl.blob(e)):
            raise RoomNamesError('idlocal entry %d does not round-trip or changed size' % e)
        k, kb = order.index(e), border.index(e)
        was = (idl.ents[order[k + 1]][0] if k + 1 < idl.n else len(idl_bytes)) - idl.ents[e][0]
        now = (back.ents[border[kb + 1]][0] if kb + 1 < back.n else len(out)) - back.ents[e][0]
        info['stored'][e] = (was, now)
        if now > was:
            raise RoomNamesError('idlocal entry %d would be stored in %d bytes, the fan\'s is %d' % (e, now, was))
    for e in range(idl.n):
        if e not in repl and _content(back, e) != _content(idl, e):
            raise RoomNamesError('idlocal entry %d changed and should not have' % e)
    log('room names (idlocal): %s; option %s' % (', '.join('%d decoded %d stored %d (was %d)' % (
        e, len(repl[e]), info['stored'][e][1], info['stored'][e][0]) for e in sorted(repl)), option))
    return out, info


# ---------------------------------------------------------------------------
# jpn/cutobj_local.bin entry 10: the three orange wedge sprites
# ---------------------------------------------------------------------------
CUTOBJ_WEDGES = [(2, "Gustavia's", "Gusto's"), (20, "Delicia's", "Scone's"), (39, "Dover's", "Frost's")]
ORANGE = Style(15, 13, 14, 12)        # ink, orthogonal halo, corner halo, flat ground (31/29/30/28 with the palette bank)
MAP_FONT = os.path.join(HERE, 'map_font.json')


def map_face():
    """tools/map_font.json (the face cg_names.py letters the room map with) as a Face."""
    mf = json.load(open(MAP_FONT, encoding='utf-8'))
    f = Face(mf['space'])
    for c, g in mf['font'].items():
        f.g[c] = (tuple(g['bits']), g['desc'] - (g['h'] - 1), g['adv'])
    return f


def _lines_of(grid, ink):
    ys, xs = np.nonzero(grid == ink)
    rows = sorted(set(int(y) for y in ys))
    lines, cur = [], [rows[0]]
    for r in rows[1:]:
        if r - cur[-1] > 1:
            lines.append(cur); cur = []
        cur.append(r)
    lines.append(cur)
    return lines


def prove_cutobj(B, face):
    """Redraw "Delicia's" and "Dover's" (cells 20, 39) from map_font and compare with the fan."""
    for k, old_t in ((20, "Delicia's"), (39, "Dover's")):
        a0, _ = B.grid(k)
        l1 = _lines_of(a0, 15)[0]
        box = (0, a0.shape[1] - 1, l1[0] - 2, l1[-1] + 2)
        m = ink_mask(a0, 15, box)
        g = a0.copy()
        erase(g, m, ORANGE)
        left = min(x for x, _ in m)
        paint(g, layout(face, old_t, left, l1[-1])[0], ORANGE)
        _prove('cutobj_local 10 cell %d %s' % (k, old_t), a0, g)


def patch_cutobj(co_bytes, log=None):
    """-> (new cutobj_local bytes, info)."""
    from choice_strips import Idlocal, rebuild
    log = log or (lambda s: None)
    co = Idlocal(co_bytes)
    b = co.blob(CUTOBJ_ENTRY)
    have = hashlib.sha256(b).hexdigest()
    if have != CUTOBJ_SHA256:
        raise RoomNamesError('cutobj_local entry %d sha256 %s is not the fan\'s' % (CUTOBJ_ENTRY, have[:12]))
    o = struct.unpack_from('<3I', b, 0)
    B = Bundle(b[o[0]:o[1]], b[o[2]:])
    face = map_face()
    prove_cutobj(B, face)
    olds = {}
    for k, old_t, new_t in CUTOBJ_WEDGES:
        olds[k], _ = B.grid(k)
    info = {'cells': {}}
    written = 0
    for k, old_t, new_t in CUTOBJ_WEDGES:
        a0 = olds[k]
        lines = _lines_of(a0, 15)
        if len(lines) != 2:
            raise RoomNamesError('cutobj_local 10 cell %d: %d text lines, expected 2' % (k, len(lines)))
        l1, l2 = lines
        m = ink_mask(a0, 15, (0, a0.shape[1] - 1, l1[0] - 2, l1[-1] + 2))
        room = ink_mask(a0, 15, (0, a0.shape[1] - 1, l2[0] - 2, l2[-1] + 2))
        rl, rr = min(x for x, _ in room), max(x for x, _ in room)
        g = a0.copy()
        erase(g, m, ORANGE)
        w = text_width(face, new_t)
        x0 = (rl + rr) // 2 - w // 2
        mask, (a, z) = layout(face, new_t, x0, l1[-1])
        paint(g, mask, ORANGE)
        written += B.write(k, a0, g)
        info['cells'][k] = dict(old=new_t and old_t, new=new_t, x=(a, z), base=l1[-1], room=(rl, rr), width=w)
    new_g = B.result()
    nb = b[:o[2]] + new_g
    if len(nb) != len(b):
        raise RoomNamesError('cutobj_local entry %d changed size' % CUTOBJ_ENTRY)
    # every frame of the animation: only the label pixels may differ, and every
    # frame that shows a wedge shows the new name
    changed = {}
    for k in range(len(B.cells)):
        if not B.cells[k]:
            continue
        before, _ = B.grid(k)
        after, _ = B.grid(k, use_new=True)
        n = int((before != after).sum())
        if n:
            changed[k] = n
    expect = set(range(2, 19)) | set(range(20, 38)) | set(range(39, 56))
    if set(changed) - expect:
        raise RoomNamesError('cutobj_local 10: cells %s changed but are not wedge frames' % sorted(set(changed) - expect))
    info['changed_cells'] = changed
    info['pixels_written'] = written
    out = rebuild(co_bytes, {CUTOBJ_ENTRY: nb}, lz=(CUTOBJ_ENTRY,))
    back = Idlocal(out)
    if back.blob(CUTOBJ_ENTRY) != nb:
        raise RoomNamesError('cutobj_local entry %d does not round-trip' % CUTOBJ_ENTRY)
    order = sorted(range(co.n), key=lambda i: co.ents[i][0])
    border = sorted(range(back.n), key=lambda i: back.ents[i][0])
    k, kb = order.index(CUTOBJ_ENTRY), border.index(CUTOBJ_ENTRY)
    was = (co.ents[order[k + 1]][0] if k + 1 < co.n else len(co_bytes)) - co.ents[CUTOBJ_ENTRY][0]
    now = (back.ents[border[kb + 1]][0] if kb + 1 < back.n else len(out)) - back.ents[CUTOBJ_ENTRY][0]
    info['stored'] = (was, now)
    if now > was:
        raise RoomNamesError('cutobj_local entry %d would be stored in %d bytes, the fan\'s is %d' % (CUTOBJ_ENTRY, now, was))
    for e in range(co.n):
        if e != CUTOBJ_ENTRY and _content(back, e) != _content(co, e):
            raise RoomNamesError('cutobj_local entry %d changed and should not have' % e)
    log('room names (cutobj_local): entry %d decoded %d stored %d (was %d), %d pixels, frames changed %d'
        % (CUTOBJ_ENTRY, len(nb), now, was, written, len(changed)))
    return out, info


def apply_to_rom(rom, dumpdir=None, log=None, any_rom=False, option=None):
    """Re-letter the room names inside a ROM image. Returns (rom, changed)."""
    import title_logo
    from choice_strips import rom_file
    log = log or (lambda s: None)
    try:
        new_id, info = patch_idlocal(rom_file(rom, 'jpn/idlocal.bin'), option, log)
        new_co, cinfo = patch_cutobj(rom_file(rom, 'jpn/cutobj_local.bin'), log)
    except RoomNamesError as e:
        if not any_rom:
            raise RoomNamesError('%s (pass --any-rom to build without the room names)' % e)
        log('room names: NOT redrawn, --any-rom given (%s)' % e)
        return rom, False
    rom = title_logo.splice(rom, 'jpn/idlocal.bin', new_id)
    rom = title_logo.splice(rom, 'jpn/cutobj_local.bin', new_co)
    return rom, True
