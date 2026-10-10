# -*- coding: utf-8 -*-
"""Capcom's "Bigg Building" in the pictures the fan lettered "Grand Tower".

The fan patch drew its own name for the tower into pictures; Capcom's English
(loc_en.json "Bigg Building", "The Bigg Building"; Collection textures
cut04_010_eng, the city map, and cut03_006_eng, the cross-section) calls it the
Bigg Building. tools/bigg_detect.py finds every picture that carries the fan's
"Grand Tower" (its DETECT.tsv is the list this module works from); this module
re-letters them in the fan's own faces, cut out of the fan's own labels at build
time (no picture ships with the tool).

  jpn/idlocal.bin        place strips 328, 331, 334, 337, 340 (cell 1); map pieces 337 and 340
                         (wedge label, cell 0); map piece 343 (label, cell 0)
  jpn/upcut_local.bin    city map 264 and 280 (the ground under the old label is derived from Capcom's own
                         city map by tools/bigg_ground.py), cross-section title on 208, 244, 246, 278, 282
  jpn/cutobj_local.bin   entry 26, the cross-section picture drawn from sprites

Run after tools/room_names.py on the built bytes (room_names cuts its T and F from
idlocal 340, which this module changes afterwards). Every changed entry keeps the fan's
decoded size and is stored in no more bytes than the fan's (tools/bufcheck.py check o).
"""
import sys, os, struct, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import room_names as rn
from room_names import Bundle, Face, Style, harvest, layout, segment, ink_mask, ring_of, RoomNamesError
from choice_strips import Idlocal, rebuild, rom_file


class BiggError(ValueError):
    pass


NEW_NAME = 'Bigg Building'

# ---------------------------------------------------------------------------
# helpers shared by every picture
# ---------------------------------------------------------------------------
def line_base(runs):
    return collections.Counter(r[3] for r in runs).most_common(1)[0][0]


def paint_ring_keep(grid, mask, style, keep):
    """rn.paint, except that a ring pixel never overwrites a pixel in `keep` (a set of (x, y) the
    label must leave alone, such as an underline)."""
    orth, diag = ring_of(mask)
    h, w = grid.shape
    for q in diag:
        if 0 <= q[0] < w and 0 <= q[1] < h and q not in keep:
            grid[q[1], q[0]] = style.halo2
    for q in orth:
        if 0 <= q[0] < w and 0 <= q[1] < h and q not in keep:
            grid[q[1], q[0]] = style.halo
    for (x, y) in mask:
        if 0 <= x < w and 0 <= y < h:
            grid[y, x] = style.ink


def composite_b(face, parts, src):
    """The face has no capital B anywhere in the fan's labels. Build it from the face's own letters: `parts`
    lists (letter, first row, last row) slices of glyphs of the same face, top to bottom, eight rows in all
    and one width. The result is registered in the face with its source noted."""
    rows = []
    for ch, r0, r1 in parts:
        bits, top, adv = face.g[ch]
        rows += list(bits[r0:r1 + 1])
    w = len(rows[0]) if rows else 0
    if len(rows) != 8 or any(len(r) != w for r in rows):
        raise BiggError('composite B: %d rows, widths %s' % (len(rows), sorted(set(len(r) for r in rows))))
    ref = face.g[parts[0][0]]
    face.g['B'] = (tuple(rows), ref[1], ref[2])
    face.src['B'] = [('composite', src)]


def faces_for(src):
    """-> dict of Face (strip, wedge, big) for the new name, with the letters the old faces lack:
         wedge  'd' (G r a n d) from the "Grand" of idlocal 340; B composite (top of R, bottom of D)
         big    B from "Block" of idlocal 294 (the big face, lit style); d from the "Grand" of 343
         strip  B composite (P's bowl, then P's own side rows and bar)"""
    F = rn.build_faces(src)
    wedge, big, strip = F['wedge'], F['big'], F['strip']
    harvest(wedge, src.grid(340, 0), (53, 85, 19, 29), 7, 'Grand', '340 Grand')
    harvest(big, src.grid(294, 0), (61, 68, 54, 63), 7, 'B', '294 Block (B)', base=62)
    harvest(big, src.grid(343, 0), (52, 125, 19, 29), 13, 'Grand Tower', '343 Grand Tower')
    composite_b(strip, [('P', 0, 4), ('P', 1, 2), ('P', 0, 0)], 'P (strip face)')
    composite_b(wedge, [('R', 0, 3), ('D', 4, 7)], 'R rows 0-3 and D rows 4-7 (wedge face)')
    return F


# ---------------------------------------------------------------------------
# idlocal: place strips (cell 1), the wedge label of 337 / 340, the label of 343
# ---------------------------------------------------------------------------
PAIRS = {328: 326, 331: 330, 334: 333, 337: 336, 340: 339, 343: 342}     # G entry -> its RECN entry
STRIP_INK, STRIP_SHADOW = 4, 3
# entry -> (rows of the strip line, run index of the old name's first letter, run index of its colon,
#           shift the tail?)  Run lists (ink 4): 328 has "To" merged; 337 / 340 start with "Outside ".
STRIPS = {
    328: dict(rows=(0, 15), first=0, colon=9, shift_tail=True),
    331: dict(rows=(0, 15), first=0, colon=10, shift_tail=True),
    334: dict(rows=(0, 15), first=0, colon=10, shift_tail=True),
    337: dict(rows=(0, 13), first=7, colon=17, shift_tail=False),   # the tail is a second line drawn misplaced
    340: dict(rows=(0, 13), first=7, colon=17, shift_tail=True),
}
WEDGE_LIT_BOXES = {337: ((53, 85, 19, 29), (53, 87, 30, 40)), 340: ((53, 85, 19, 29), (53, 87, 30, 40))}
BIG_DIM = Style(13, 1, 1, 2)


def _strip_runs(a0, rows, first, colon):
    y0, y1 = rows
    m = ink_mask(a0, STRIP_INK, (0, a0.shape[1] - 1, y0, y1))
    runs = segment(m, (0, a0.shape[1] - 1, y0, y1))
    if len(runs) <= colon:
        raise BiggError('strip: %d runs, expected a colon at run %d' % (len(runs), colon))
    if runs[colon][1] - runs[colon][0] != 0:
        raise BiggError('strip: run %d is %d px wide, not a colon' % (colon, runs[colon][1] - runs[colon][0] + 1))
    return runs, line_base(runs)


def prove_strip(a0, rows, runs, first, colon):
    """Repaint the old name's own letters with the shadow rule; every pixel of the name's columns must come
    out as the fan's."""
    y0, y1 = rows
    x0, x1 = runs[first][0], runs[colon][1] + 1
    mask = set()
    for r in runs[first:colon + 1]:
        mask |= set(r[4])
    g = np.zeros_like(a0)
    rn.paint_strip(g, mask)
    d = np.argwhere(g[y0:y1 + 1, x0:x1 + 1] != a0[y0:y1 + 1, x0:x1 + 1])
    # the last column holds only the colon's shadow (the fan left two of those out on 337 / 340, where a
    # tail pixel also sits on it); every other column must match
    d = [p for p in d.tolist() if p[1] != x1 - x0]
    if d:
        raise BiggError('strip: repainting the old name differs from the fan in %d pixels (first %s)' % (len(d), d[0]))


def patch_strip(B, entry, new_text, face, info):
    spec = STRIPS[entry]
    a0, _ = B.grid(1)
    y0, y1 = spec['rows']
    runs, base = _strip_runs(a0, spec['rows'], spec['first'], spec['colon'])
    first, colon = spec['first'], spec['colon']
    prove_strip(a0, spec['rows'], runs, first, colon)
    nx0, colon_x1 = runs[first][0], runs[colon][1]
    # the label's own word space: the gap between the d of Grand and the T of Tower
    d_run, t_run = runs[first + 4], runs[first + 5]
    sp = t_run[0] - d_run[1] - 2
    face.space = sp
    tail = runs[colon + 1:]
    new = a0.copy()
    new[y0:y1 + 1, nx0:] = 0
    mask, (a, z) = layout(face, new_text, nx0, base)
    rn.paint_strip(new, mask)
    delta = z - colon_x1
    W = a0.shape[1]
    if tail:
        tx0 = tail[0][0]
        seg = a0[y0:y1 + 1, tx0:]
        if spec['shift_tail']:
            dst = tx0 + delta
            cut = max(0, dst + seg.shape[1] - W)
            if cut and np.any(seg[:, seg.shape[1] - cut:] != 0):
                raise BiggError('strip %d: the tail would run off the strip by %d px' % (entry, cut))
            new[y0:y1 + 1, dst:dst + seg.shape[1] - cut] = seg[:, :seg.shape[1] - cut]
            gap = dst - (z + 1)
            if gap < 3:
                raise BiggError('strip %d: only %d empty columns between the new colon and the tail' % (entry, gap))
        else:
            new[y0:y1 + 1, tx0:] = seg
            if tx0 - (z + 1) < 2:
                raise BiggError('strip %d: the new name runs into the tail kept in place' % entry)
    if z >= W - 1:
        raise BiggError('strip %d: the new name ends at column %d of %d' % (entry, z, W))
    info.setdefault('strip', {})[entry] = dict(old=(nx0, colon_x1), new=(a, z), delta=delta, space=sp, base=base,
                                               tail_x0=(tail[0][0] if tail else None),
                                               width_old=colon_x1 - nx0 + 1, width_new=z - a + 1)
    return B.write(1, a0, new)


def prove_label(a0, lines, style, keep=()):
    """lines: list of (box, ink). Repaint the old lines from their own ink pixels (erase, then ring and ink);
    every pixel of the label and its ring must come out as the fan's."""
    g = a0.copy()
    allm = set()
    for box, ink in lines:
        allm |= ink_mask(a0, ink, box)
    rn.erase(g, allm, style)
    paint_ring_keep(g, allm, style, set(keep))
    orth, diag = ring_of(allm)
    cover = allm | orth | diag
    bad = [(x, y) for (x, y) in cover if 0 <= y < a0.shape[0] and 0 <= x < a0.shape[1] and g[y, x] != a0[y, x]]
    if bad:
        raise BiggError('repainting the old label differs from the fan in %d pixels (first %s)' % (len(bad), sorted(bad)[:4]))
    return allm


def flat_ground(a0, mask, ground, pad=1):
    """Every pixel of the rectangle of `mask` (grown by pad) that is neither label nor its ring: is it the
    ground? -> list of offenders."""
    xs = [x for x, _ in mask]; ys = [y for _, y in mask]
    orth, diag = ring_of(mask)
    cover = mask | orth | diag
    bad = []
    for y in range(min(ys) - pad - 1, max(ys) + pad + 2):
        for x in range(min(xs) - pad - 1, max(xs) + pad + 2):
            if (x, y) in cover or not (0 <= y < a0.shape[0] and 0 <= x < a0.shape[1]):
                continue
            if a0[y, x] != ground:
                bad.append((x, y, int(a0[y, x])))
    return bad


def erase_stray(grid, mask, style, protect=lambda x, y: False):
    """The fan's halos have a few pixels outside the 8-neighbour ring (the gap column between two letters
    two pixels apart, for one). Any pixel of the label's rectangle (grown by two) that carries the halo
    value, is not part of the label or its ring, and is not protected, goes back to the ground too.
    -> number of pixels cleared."""
    orth, diag = ring_of(mask)
    cover = mask | orth | diag
    xs = [x for x, _ in mask]; ys = [y for _, y in mask]
    n = 0
    for y in range(min(ys) - 2, max(ys) + 3):
        for x in range(min(xs) - 2, max(xs) + 3):
            if 0 <= y < grid.shape[0] and 0 <= x < grid.shape[1] and (x, y) not in cover                     and grid[y, x] == style.halo and not protect(x, y):
                grid[y, x] = style.ground_at(x, y)
                n += 1
    return n


def patch_wedge_label(B, entry, faces, info):
    """337 / 340 cell 0: the lit wedge label "Grand" over "Tower" -> "Bigg" over "Building"."""
    wedge = faces['wedge']
    b1, b2 = WEDGE_LIT_BOXES[entry]
    a0, _ = B.grid(0)
    m1, m2 = ink_mask(a0, 7, b1), ink_mask(a0, 7, b2)
    runs1, runs2 = segment(m1, b1), segment(m2, b2)
    base1, base2 = line_base(runs1), line_base(runs2)
    left = min(r[0] for r in runs1 + runs2)
    allm = prove_label(a0, [(b1, 7), (b2, 7)], rn.LIT_WEDGE)
    bad = flat_ground(a0, allm, 5)
    new = a0.copy()
    rn.erase(new, allm, rn.LIT_WEDGE)
    # the arrow to the right of the label (ink and halo from column 85, rows up to 31) is not the label's
    stray = erase_stray(new, allm, rn.LIT_WEDGE, lambda x, y: x >= 85 and y <= 31)
    l1, (a1, z1) = layout(wedge, 'Bigg', left, base1)
    l2, (a2, z2) = layout(wedge, 'Building', left, base2)
    rn.paint(new, l1, rn.LIT_WEDGE)
    rn.paint(new, l2, rn.LIT_WEDGE)
    info.setdefault('wedge', {})[entry] = dict(
        old=((min(r[0] for r in runs1), max(r[1] for r in runs1)), (min(r[0] for r in runs2), max(r[1] for r in runs2))),
        new=((a1, z1), (a2, z2)), base=(base1, base2), ground_offenders=bad, stray=stray)
    return B.write(0, a0, new)


def patch_big_label(B, entry, faces, info, raise_rows=0):
    """343 cell 0: the single-line label "Grand Tower" -> "Bigg Building" (big face, dim style)."""
    big = faces['big']
    a0, _ = B.grid(0)
    box = (52, 125, 19, 29)
    m = ink_mask(a0, 13, box)
    runs = segment(m, box)
    base = line_base(runs)
    left = runs[0][0]
    # keep set: the underline and its leader, so a halo never cuts them
    keep = set((x, y) for y in range(28, 36) for x in range(40, 150) if a0[y, x] == 13)
    allm = prove_label(a0, [(box, 13)], BIG_DIM, keep)
    bad = flat_ground(a0, allm, 2)
    big.space = runs[5][0] - runs[4][1] - 2
    new = a0.copy()
    rn.erase(new, allm, BIG_DIM)
    stray = erase_stray(new, allm, BIG_DIM, lambda x, y: (x, y) in keep)
    mask, (a, z) = layout(big, NEW_NAME, left, base - raise_rows)
    paint_ring_keep(new, mask, BIG_DIM, keep)
    info.setdefault('big', {})[entry] = dict(old=(left, runs[-1][1]), new=(a, z), base=base - raise_rows, space=big.space,
                                             ground_offenders=bad, stray=stray, width_old=runs[-1][1] - left + 1, width_new=z - a + 1)
    return B.write(0, a0, new)


# ---------------------------------------------------------------------------
# jpn/upcut_local.bin: the city map (264, 280) and the cross-section titles
# ---------------------------------------------------------------------------
import bigg_ground
from nitro import nclr, ncgr, _sections

UPCUT_SHA256 = {
    208: '6309a0d9b7dc6e137d3597cc6e080b6349aee5835a49b718e7746afd104cecc1',
    244: '14392618820578271ab9ed443e2d83b9b415ffe6d1b212027a04ce5680ed333b',
    246: '4dd321e68d93e421273d266af06e2d780146ba9dc7507339a0daee3d779a0275',
    264: '4bea71aa70e970cf759e98abcd4d8c515819f7638529892e26331c2063fd5c7f',
    278: '3120e08c2368ac79d5d041469fa54a682c2da5e2a33958e35905bc1de4b5d904',
    280: 'c59439eebe0d5787e3b0292576d019067a752b1c65c683271cdce3c1937ba027',
    282: 'ee684c6b6a676c854c5cd337c82d8f215bad7dfd58f672eaf24eec066c3b6623',
}
MAP_ENTRIES = (264, 280)
# cross-section titles: entry -> list of (old text, new text, baseline row, centre column of the old line)
CROSS_OLD, CROSS_NEW = 'Grand Tower: Cross Section View', 'Bigg Building: Cross-Section'
TITLES = {
    208: [(CROSS_OLD, CROSS_NEW, 12)],
    244: [(CROSS_OLD, CROSS_NEW, 12)],
    246: [(CROSS_OLD, CROSS_NEW, 12)],
    278: [(CROSS_OLD, CROSS_NEW, 12)],
    282: [('Grand Tower:', 'Bigg Building:', 12), ('Cross Section View', 'Cross-Section', 23)],
}
MAP_STYLE = dict(ink=0, halo=28)               # city map: black ink, white one-pixel halo, soft corner tones
TITLE_STYLE = rn.Style(1, 6, 5)                # titles: ink 1, orthogonal halo 6, corner pixels 5
MAP_LABEL_CENTRE = 98.5                        # the old "Grand" / "Tower" are 85..112
MAP_BASES = (110, 120)                         # baselines of the old two lines
MAP_LAYOUT = 'A'                               # A: Bigg / Building on two lines where Grand / Tower sat; B: one line under the icon; C: one line centred in the old block
CORNER_WHITE_SHARE = 0.6                       # the fan's corner pixels are 0.6 white + 0.4 background (mean RGB error 8)
TITLE_SPACE = 4                                # pen advance of a blank: five empty columns between words


def map_face_fixed():
    """tools/map_font.json (the fan's city-map / title face) with two fixes: the fan never lets two letters
    touch (the 's' advance in the file is 5, the fan's pair 'ss' is 6, so every advance is at least width + 1;
    proven below on every word of the old labels), and a hyphen. The face has no hyphen anywhere the detector
    can read, so the hyphen is the one glyph that is not cut from a label: a three pixel bar on the row of
    the crossbar of the 'e'."""
    f = rn.map_face()
    f.space = TITLE_SPACE
    for c, (bits, top, adv) in list(f.g.items()):
        f.g[c] = (bits, top, max(adv, len(bits[0]) + 1))
    e_bits, e_top, _ = f.g['e']
    bar = [i for i, r in enumerate(e_bits) if r == '1' * len(r)]
    if not bar:
        raise BiggError("the face's 'e' has no full crossbar row")
    f.g['-'] = (('111',), e_top + bar[0], 4)
    f.src['-'] = [('drawn', "3 px bar on the crossbar row of 'e' (no hyphen in any map label)")]
    return f


def raw_write(rgcn, old, new):
    """Write the pixels where `new` differs from `old` (index grids of a raw 8bpp tile bank laid out
    row by row) into a copy of the RGCN. -> (bytes, pixels written)."""
    data, bpp, cnt, tw, th = ncgr(rgcn)
    if bpp != 8:
        raise BiggError('raw picture is %dbpp, expected 8' % bpp)
    p, _size, body = _sections(rgcn)[b'RAHC']
    dsize = struct.unpack_from('<I', body, 16)[0]
    doff = struct.unpack_from('<I', body, 20)[0]
    off0 = p + 8 + doff
    cols = tw if 0 < tw < 256 else 32
    out = bytearray(rgcn)
    n = 0
    for y, x in zip(*np.nonzero(old != new)):
        t = (y // 8) * cols + x // 8
        if t >= cnt:
            raise BiggError('pixel (%d,%d) is in tile %d of %d' % (x, y, t, cnt))
        if not 0 <= new[y, x] <= 255:
            raise BiggError('value %r is not a palette index' % new[y, x])
        out[off0 + t * 64 + (y % 8) * 8 + (x % 8)] = int(new[y, x])
        n += 1
    return bytes(out), n


def _nearest(pal, rgb):
    P = np.array(pal, np.int32)
    return int(((P - np.array(rgb, np.int32)) ** 2).sum(axis=1).argmin())


def paint_map_label(grid, mask, pal, ink, halo):
    """Ink, one-pixel orthogonal halo, and diagonal corner pixels at 0.6 white + 0.4 background (snapped to
    the palette), as the fan's city-map labels have them."""
    orth, diag = ring_of(mask)
    h, w = grid.shape
    white = np.array(pal[halo], np.float64)
    for (x, y) in diag:
        if 0 <= x < w and 0 <= y < h and (x, y) not in mask:
            bg = np.array(pal[grid[y, x]], np.float64)
            grid[y, x] = _nearest(pal, CORNER_WHITE_SHARE * white + (1 - CORNER_WHITE_SHARE) * bg)
    for (x, y) in orth:
        if 0 <= x < w and 0 <= y < h:
            grid[y, x] = halo
    for (x, y) in mask:
        if 0 <= x < w and 0 <= y < h:
            grid[y, x] = ink


def prove_map_labels(g, face):
    """The old "Grand" / "Tower" redrawn from the face, at the fan's own positions, are the fan's ink
    pixels; every orthogonal halo pixel the fan has around them is the halo value."""
    for text, b in zip(('Grand', 'Tower'), MAP_BASES):
        pts, _ = layout(face, text, 85, b)
        old = ink_mask(g, MAP_STYLE['ink'], (80, 117, b - 8, b + 3))
        if pts != old:
            raise BiggError('city map: the face does not redraw %r as the fan has it (%d vs %d pixels)' % (text, len(pts), len(old)))
        orth, _d = ring_of(old)
        bad = [q for q in orth if g[q[1], q[0]] != MAP_STYLE['halo']]
        if bad:
            raise BiggError('city map: %d orthogonal ring pixels of %r are not the halo (first %s)' % (len(bad), text, bad[:3]))


def map_lines(layout_name, face):
    """-> list of (text, left x, baseline) for a layout of the new name on the city map."""
    if layout_name == 'A':
        out = []
        for text, b in zip(('Bigg', 'Building'), MAP_BASES):
            w = rn.text_width(face, text)
            out.append((text, int(round(MAP_LABEL_CENTRE - (w - 1) / 2.0 - 0.01)), b))
        return out
    if layout_name == 'B':
        w = rn.text_width(face, NEW_NAME)
        return [(NEW_NAME, int(round(MAP_LABEL_CENTRE - (w - 1) / 2.0 - 0.01)), MAP_BASES[0])]
    if layout_name == 'C':
        w = rn.text_width(face, NEW_NAME)
        return [(NEW_NAME, int(round(MAP_LABEL_CENTRE - (w - 1) / 2.0 - 0.01)), (MAP_BASES[0] + MAP_BASES[1]) // 2 + 1)]
    raise BiggError('unknown city map layout %r' % (layout_name,))


def patch_city_map(blob, pal, entry, face, layout_name, info, dumpdir=None, textures=None):
    import gfx_views as gv
    g = gv.raw_grid(blob)
    if g.shape != (192, 256):
        raise BiggError('city map %d is %r, expected 192x256' % (entry, g.shape))
    prove_map_labels(g, face)
    mask = bigg_ground.label_mask(g)
    want = set((int(x), int(y)) for y, x in zip(*np.nonzero(mask)))
    lines = map_lines(layout_name, face)
    label_px = set()
    placed = []
    painted = []
    for text, x0, b in lines:
        m, (a, z) = layout(face, text, x0, b)
        o, d = ring_of(m)
        label_px |= m | o | d
        painted.append(m)
        placed.append((text, a, z, b))
    keep = mask.copy()
    for (x, y) in label_px:
        if 0 <= y < keep.shape[0] and 0 <= x < keep.shape[1]:
            keep[y, x] = False
    # the ground under the old label, from Capcom's own city map (tools/bigg_ground.py)
    new, ginfo = bigg_ground.derive(g, pal, mask, keep, dumpdir, textures)
    ginfo.pop('stage_ds', None)
    for m in painted:
        paint_map_label(new, m, pal, MAP_STYLE['ink'], MAP_STYLE['halo'])
    # every changed pixel is in the erase mask or belongs to the new label; nothing else moved
    changed = set((int(x), int(y)) for y, x in zip(*np.nonzero(new != g)))
    stray = changed - want - label_px
    if stray:
        raise BiggError('city map %d: %d pixels changed outside the mask and the new label' % (entry, len(stray)))
    out, n = raw_write(blob, g, new)
    info.setdefault('map', {})[entry] = dict(layout=layout_name, lines=placed, mask=len(want), written=n, ground=ginfo,
                                             ink_width=max(z for _, a, z, b in placed) - min(a for _, a, z, b in placed) + 1)
    return out, new


def retitle(g, lines, face, style, ink):
    """Re-letter title lines on a flat ground. lines: list of (old text, new text, baseline row, x lo, x hi) with
    the column window the old line sits in. The old line is checked word by word (the face redraws each word
    at the fan's own x as the fan has it; every ring pixel is the fan's two-tone halo; the ground around it
    is one value), erased to that ground, and the new text is drawn centred on the old line's centre.
    -> (new grid, [per line info])."""
    new = g.copy()
    done = []
    for old_t, new_t, b, xlo, xhi in lines:
        y0, y1 = max(0, b - 8), b + 3
        m = ink_mask(g, ink, (xlo, xhi, y0, y1))
        xs = [x for x, _ in m]
        x0, x1 = min(xs), max(xs)
        cols = sorted(set(xs))
        runs, s_, p_ = [], cols[0], cols[0]
        for c in cols[1:]:
            if c - p_ > 1:
                runs.append((s_, p_)); s_ = c
            p_ = c
        runs.append((s_, p_))
        words, cur = [], [runs[0]]
        for r in runs[1:]:
            if r[0] - cur[-1][1] - 1 >= 4:
                words.append(cur); cur = []
            cur.append(r)
        words.append(cur)
        texts = old_t.split(' ')
        if len(words) != len(texts):
            raise BiggError('title %r: %d words found, expected %d' % (old_t, len(words), len(texts)))
        for w, text in zip(words, texts):
            wx0, wx1 = w[0][0], w[-1][1]
            pts, _ = layout(face, text, wx0, b)
            ow = set(q for q in m if wx0 <= q[0] <= wx1)
            if pts != ow:
                raise BiggError('title: the face does not redraw %r as the fan has it' % text)
        orth, diag = ring_of(m)
        inside = lambda q: 0 <= q[1] < g.shape[0] and 0 <= q[0] < g.shape[1]
        bad = [q for q in orth if inside(q) and g[q[1], q[0]] != style.halo] +               [q for q in diag if inside(q) and g[q[1], q[0]] != style.halo2]
        if bad:
            raise BiggError('title %r: %d ring pixels are not the two-tone halo (first %s)' % (old_t, len(bad), bad[:3]))
        cover = m | orth | diag
        rect = [(x, y) for y in range(max(0, b - 8), b + 4) for x in range(x0 - 3, x1 + 4)
                if 0 <= x < g.shape[1] and (x, y) not in cover]
        ground = collections.Counter(int(g[y, x]) for x, y in rect).most_common(1)[0][0]
        off = [(x, y, int(g[y, x])) for x, y in rect if g[y, x] != ground]
        if off:
            raise BiggError('title %r: the ground under the old title is not flat (%d pixels, first %s)' % (old_t, len(off), off[:3]))
        for (x, y) in cover:
            if inside((x, y)):
                new[y, x] = ground
        w = rn.text_width(face, new_t)
        left = int(round((x0 + x1) / 2.0 - (w - 1) / 2.0 - 0.01))
        mask, (a, z) = layout(face, new_t, left, b)
        rn.paint(new, mask, style)
        done.append(dict(old=(x0, x1), new=(a, z), base=b, ground=ground, width_old=x1 - x0 + 1, width_new=z - a + 1))
    return new, done


def patch_title(blob, entry, face, info):
    import gfx_views as gv
    g = gv.raw_grid(blob)
    lines = [(o, n, b, 0, g.shape[1] - 1) for o, n, b in TITLES[entry]]
    new, done = retitle(g, lines, face, TITLE_STYLE, 1)
    out, n = raw_write(blob, g, new)
    info.setdefault('title', {})[entry] = dict(lines=done, written=n)
    return out, new


def patch_upcut(upcut_bytes, log=None, layout_name=None, dumpdir=None, textures=None):
    """-> (new upcut_local bytes, info, {entry: (old grid, new grid, palette)})."""
    layout_name = layout_name or MAP_LAYOUT
    idl = Idlocal(upcut_bytes)
    for e, sha in sorted(UPCUT_SHA256.items()):
        have = hashlib.sha256(idl.blob(e)).hexdigest()
        if have != sha:
            raise BiggError('upcut_local entry %d sha256 %s is not the fan\'s' % (e, have[:12]))
    if textures is None:
        textures = bigg_ground.load_textures(dumpdir)
    face = map_face_fixed()
    info, repl, grids = {}, {}, {}
    import gfx_views as gv
    for e in MAP_ENTRIES:
        pal = nclr(idl.blob(e + 1))
        pal = pal + [(255, 0, 255)] * (256 - len(pal))
        blob = idl.blob(e)
        repl[e], new = patch_city_map(blob, pal, e, face, layout_name, info, dumpdir, textures)
        grids[e] = (gv.raw_grid(blob), new, pal)
    for e in TITLES:
        pal = nclr(idl.blob(e + 1))
        blob = idl.blob(e)
        repl[e], new = patch_title(blob, e, face, info)
        grids[e] = (gv.raw_grid(blob), new, pal)
    out = rebuild(upcut_bytes, repl, lz=tuple(sorted(repl)))
    back = Idlocal(out)
    info['stored'] = _stored_check(idl, upcut_bytes, back, out, repl, 'upcut_local')
    for e in range(idl.n):
        if e not in repl and _content(back, e) != _content(idl, e):
            raise BiggError('upcut_local entry %d changed and should not have' % e)
    return out, info, grids


def _content(idl, e):
    b = idl.blob(e)
    size = idl.ents[e][1]
    return b if size & 0x80000000 else b[:size]


def _stored_check(idl, old_bytes, back, new_bytes, repl, name):
    """Round trip, decoded size unchanged, stored size not over the old entry's. -> {entry: (stored now, stored before)}."""
    order = sorted(range(idl.n), key=lambda i: idl.ents[i][0])
    border = sorted(range(back.n), key=lambda i: back.ents[i][0])
    res = {}
    for e in sorted(repl):
        if back.blob(e) != repl[e] or len(back.blob(e)) != len(idl.blob(e)):
            raise BiggError('%s entry %d does not round-trip or changed size' % (name, e))
        k, kb = order.index(e), border.index(e)
        was = (idl.ents[order[k + 1]][0] if k + 1 < idl.n else len(old_bytes)) - idl.ents[e][0]
        now = (back.ents[border[kb + 1]][0] if kb + 1 < back.n else len(new_bytes)) - back.ents[e][0]
        res[e] = (now, was)
        if now > was:
            raise BiggError('%s entry %d would be stored in %d bytes, the fan\'s is %d' % (name, e, now, was))
    return res


# ---------------------------------------------------------------------------
# jpn/cutobj_local.bin entry 26: the cross-section picture drawn from sprites
# ---------------------------------------------------------------------------
CUTOBJ_ENTRY = 26
CUTOBJ_SHA256 = 'a10d4658c82256847a86a43a87c9904bf80d21c5ea0fbbf76c1049b92242261d'
CUTOBJ_CELL = 41                       # the only cell that draws the picture's tiles (12 OBJs of 64x64, palette bank 15)
CUTOBJ_STYLE = rn.Style(1, 15, 12, 8)  # ink 1, orthogonal halo 15, corner pixels 12, ground 8
# the two title pieces of the cell: old text, new text, baseline, column window
CUTOBJ_TITLE = [('Grand Tower:', 'Bigg Building:', 60, 90, 175), ('Cross Section View', 'Cross-Section', 7, 140, 250)]


def patch_cutobj(co_bytes, face):
    """-> (new cutobj_local bytes, info, (old grid, new grid))."""
    co = Idlocal(co_bytes)
    b = co.blob(CUTOBJ_ENTRY)
    have = hashlib.sha256(b).hexdigest()
    if have != CUTOBJ_SHA256:
        raise BiggError('cutobj_local entry %d sha256 %s is not the fan\'s' % (CUTOBJ_ENTRY, have[:12]))
    o = struct.unpack_from('<3I', b, 0)
    B = Bundle(b[o[0]:o[1]], b[o[2]:])
    old, _ = B.grid(CUTOBJ_CELL)
    new, done = retitle(old, CUTOBJ_TITLE, face, CUTOBJ_STYLE, 1)
    n = B.write(CUTOBJ_CELL, old, new)
    nb = b[:o[2]] + B.result()
    if len(nb) != len(b):
        raise BiggError('cutobj_local entry %d changed size' % CUTOBJ_ENTRY)
    # every cell: only cell 41 may change
    changed = {}
    for k in range(len(B.cells)):
        if B.cells[k]:
            before, _ = B.grid(k)
            after, _ = B.grid(k, use_new=True)
            c = int((before != after).sum())
            if c:
                changed[k] = c
    if set(changed) != {CUTOBJ_CELL}:
        raise BiggError('cutobj_local %d: cells %s changed, expected only %d' % (CUTOBJ_ENTRY, sorted(changed), CUTOBJ_CELL))
    out = rebuild(co_bytes, {CUTOBJ_ENTRY: nb}, lz=(CUTOBJ_ENTRY,))
    back = Idlocal(out)
    stored = _stored_check(co, co_bytes, back, out, {CUTOBJ_ENTRY: nb}, 'cutobj_local')
    for e in range(co.n):
        if e != CUTOBJ_ENTRY and _content(back, e) != _content(co, e):
            raise BiggError('cutobj_local entry %d changed and should not have' % e)
    return out, dict(lines=done, written=n, changed=changed, stored=stored), (old, new)


# ---------------------------------------------------------------------------
# the idlocal container and the ROM
# ---------------------------------------------------------------------------
IDLOCAL_SHA256 = {            # decoded fan entries this module reads or writes
    293: '44b12d55582979f0dd5e103f09329ef81192316112f3b53e09ceab47eb928c7e',
    294: '8edc4a51ca4e00be2d8c9bfaf7cbf3a94565f54004bc82498c4aa527c077a09c',
    326: 'e02e89b25221e782b914c4c1ad75c0eba01960ef26e15c15d8f72dc0d9931258',
    328: 'edc39cdecc6a22456252533c47d758b3cf7f631dfa135c194c5457e8c9c9bc5c',
    330: 'dc15030240db842edc366b9391401c5b53c21a9abb6da6d9f5052b5da437b84e',
    331: '8099ead468231f7ef30229397e79d337d38332290a01e27cf0fc8ca6f974b197',
    333: 'dc15030240db842edc366b9391401c5b53c21a9abb6da6d9f5052b5da437b84e',
    334: '684af7e9952c39adbcd9e7ee1d27f5427932f65a93f7e0bccfbdcf47a572a535',
    336: 'd60dfa9ceefa3c1924d7d147089acd772d93462ed36080c84d939aee5a18d39f',
    337: '2136f397f2268ebe90237b8d28d16a57f116daa092302c430ad3f66fdfb9809a',
    339: '25d718151a0ca7c741e828459c4736cb5cf4166dfd0b4eee02ff3d7b75efee01',
    340: '429ec49ccc2fe7be6fcf24d5c7c75327590cd3fa62c1e5a7af31818ca6cebe9f',
    342: '25d718151a0ca7c741e828459c4736cb5cf4166dfd0b4eee02ff3d7b75efee01',
    343: 'ff447da4846721151a9e9687dd0dbd3e1ff00c47f9b72788dc932f564c2cc25d',
}
IDLOCAL_GROUPS = (328, 331, 334, 337, 340, 343)     # G entries written


def patch_idlocal(idl_bytes, fan_idl_bytes, log=None):
    """-> (new idlocal bytes, info). The letters are cut from the fan's own idlocal; the entries written are
    the built file's, which must still be the fan's."""
    log = log or (lambda s: None)
    idl, fan = Idlocal(idl_bytes), Idlocal(fan_idl_bytes)
    for e, sha in sorted(IDLOCAL_SHA256.items()):
        if hashlib.sha256(fan.blob(e)).hexdigest() != sha:
            raise BiggError('idlocal entry %d of the fan file sha256 is not the one this module was proven on' % e)
        if idl.blob(e) != fan.blob(e):
            raise BiggError('idlocal entry %d is not the fan\'s in the ROM being built' % e)
    for e, sha in sorted(rn.FAN_SHA256.items()):
        if hashlib.sha256(fan.blob(e)).hexdigest() != sha:
            raise BiggError('idlocal entry %d of the fan file is not the fan\'s' % e)
    faces = faces_for(rn.Source(fan))
    info, repl = {}, {}
    for g in IDLOCAL_GROUPS:
        B = Bundle(idl.blob(PAIRS[g]), idl.blob(g))
        n = 0
        if g in STRIPS:
            n += patch_strip(B, g, NEW_NAME + ':', faces['strip'], info)
        if g in WEDGE_LIT_BOXES:
            n += patch_wedge_label(B, g, faces, info)
        if g == 343:
            n += patch_big_label(B, g, faces, info)
        repl[g] = B.result()
        info.setdefault('written', {})[g] = n
    out = rebuild(idl_bytes, repl, lz=tuple(sorted(repl)))
    back = Idlocal(out)
    info['stored'] = _stored_check(idl, idl_bytes, back, out, repl, 'idlocal')
    for e in range(idl.n):
        if e not in repl and _content(back, e) != _content(idl, e):
            raise BiggError('idlocal entry %d changed and should not have' % e)
    info['faces'] = {k: {c: v for c, v in faces[k].src.items() if c in ('B', 'd')} for k in ('strip', 'wedge', 'big')}
    log('bigg building (idlocal): %s' % ', '.join('%d decoded %d stored %d (was %d)' % (
        e, len(repl[e]), info['stored'][e][0], info['stored'][e][1]) for e in sorted(repl)))
    return out, info


def apply_to_rom(rom, dumpdir, log=None, any_rom=False, layout_name=None):
    """Re-letter the tower name inside a ROM image: returns (rom, changed). Run after room_names (it cuts
    letters from idlocal 340, which this changes) and after the last step that writes upcut_local."""
    import title_logo
    log = log or (lambda s: None)
    try:
        fan_idl = open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'idlocal.bin'), 'rb').read()
        new_id, iinfo = patch_idlocal(rom_file(rom, 'jpn/idlocal.bin'), fan_idl, log)
        new_up, uinfo, _g = patch_upcut(rom_file(rom, 'jpn/upcut_local.bin'), log, layout_name, dumpdir)
        new_co, cinfo, _g2 = patch_cutobj(rom_file(rom, 'jpn/cutobj_local.bin'), map_face_fixed())
    except (BiggError, RoomNamesError, bigg_ground.GroundError) as e:
        if not any_rom:
            raise BiggError('%s (pass --any-rom to build without the Bigg Building pictures)' % e)
        log('bigg building: NOT redrawn, --any-rom given (%s)' % e)
        return rom, False
    log('bigg building (upcut_local): %s; city map layout %s' % (', '.join('%d decoded %d stored %d (was %d)' % (
        e, 49200, uinfo['stored'][e][0], uinfo['stored'][e][1]) for e in sorted(uinfo['stored'])), layout_name or MAP_LAYOUT))
    log('bigg building (cutobj_local): entry %d stored %d (was %d)' % (CUTOBJ_ENTRY, cinfo['stored'][CUTOBJ_ENTRY][0], cinfo['stored'][CUTOBJ_ENTRY][1]))
    rom = title_logo.splice(rom, 'jpn/idlocal.bin', new_id)
    rom = title_logo.splice(rom, 'jpn/upcut_local.bin', new_up)
    rom = title_logo.splice(rom, 'jpn/cutobj_local.bin', new_co)
    return rom, True
