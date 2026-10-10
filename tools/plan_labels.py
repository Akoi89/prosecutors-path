# -*- coding: utf-8 -*-
"""Capcom's wording on the fan's map pieces and floor plans.

The fan patch lettered the map pieces of jpn/idlocal.bin (the lit room on the bottom-screen
location map and the title strip under it) with its own words. Capcom's script names the same
places differently (the location captions "Prison - Corridor", "Prison - Workshop", "Prison -
Maximum Security", "Prison - Yard", "Zodiac Hall - Winter Wing", "Zodiac Hall - Fountain Room"),
and one piece, the office of room 1202, the fan never translated at all.

This module re-letters those pictures in place, in the fan's own lettering. Every letter is cut
out of the fan's own labels at build time (nothing game-derived is stored in the repository). A
label is only erased where the picture holds nothing but the label's own colours and the flat
ground, and a new label is only painted on pixels that hold that ground after the erase; anything
else stops the build.

Picture classes:
  '1202'    the retail-Japanese office of room 1202 (idlocal 349)
  'prison'  the lit-room map pieces of the Detention Center and the Prison and their strips (idlocal 291 to 312)
  plans     the seven full-screen plans of the prison and the detention center (jpn/upcut_local.bin 36, 40, 48, 52,
            78, 80, 82); where "Maximum Security" and the longer titles would not fit the fan's stored bytes the
            entries keep the old wording (PLAN_FIT, KNOWN_LEFT) unless LARGER lists them
  'zodiac'  the Zodiac Hall pieces and the contest venue's Fountain Room (idlocal 315, 318, 321, 324, 327)

Every changed entry keeps the fan's decoded size and is stored as a real LZ11 stream in no more
bytes than the fan's entry (tools/bufcheck.py check p). tools/plan_detect.py looks for the old
wording in a built ROM.
"""
import sys, os, struct, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import room_names as rn
from room_names import (Bundle, Face, Style, harvest, layout, segment, ink_mask, ring_of, interior,
                        paint, erase, text_width, RoomNamesError)
from choice_strips import Idlocal, rebuild


class PlanError(ValueError):
    pass


# ---------------------------------------------------------------------------
# which RECN goes with which RGCN: the game's own location table (overlay 7,
# 0x020D4DA0, rows of RECN, RNAN, RGCN, RLCN handles). Entry g is the RGCN.
# ---------------------------------------------------------------------------
RECN_OF = {282: 281, 285: 284, 288: 287, 291: 290, 294: 293, 297: 296, 300: 299, 303: 302, 306: 305,
           309: 308, 312: 311, 321: 320, 324: 323, 327: 326, 315: 314, 318: 317, 349: 351, 346: 348,
           352: 354}

BIG = Style(9, 12, 12, 7)            # white letters, grey outline, in a lit box (ground 7)


# (face, rgcn, cell, box, ink, text). The big face is the lettering of the lit rooms and of the larger labels
# on bands (6 px letters, white or olive, 8 rows to the ascender); letters are taken from the labels that keep
# the fan's normal letter widths first (the fan squeezed a few labels; Face.add keeps the first glyph it meets,
# so the later, squeezed variants never replace a normal one). The strip face is the title strip's lettering.
SOURCES = [
    ('big', 291, 0, (39, 79, 47, 54), 9, "Visitor's"),
    ('big', 291, 0, (39, 63, 58, 65), 9, 'Room'),
    ('big', 288, 0, (64, 97, 54, 61), 9, 'Office'),
    ('big', 312, 0, (75, 107, 54, 61), 9, 'Court-'),
    ('big', 312, 0, (75, 98, 65, 73), 9, 'yard'),
    ('big', 294, 0, (63, 79, 44, 51), 7, 'Cell'),
    ('big', 294, 0, (63, 89, 55, 62), 7, 'Block'),
    ('big', 352, 0, (110, 132, 68, 73), 7, 'room'),
    ('big', 349, 0, (59, 81, 63, 69), 9, '1202'),
    ('big', 282, 0, (60, 92, 64, 74), 9, 'Stage'),
    ('big', 331, 0, (55, 90, 58, 68), 9, 'Viewing'),
    ('big', 331, 0, (55, 97, 70, 79), 9, 'Platform'),
    ('big', 324, 0, (38, 83, 50, 62), 9, "Master's"),
    ('big', 346, 0, (49, 102, 77, 84), 9, 'Front Yard'),
    ('big', 309, 0, (74, 110, 65, 75), 9, 'Special'),
    ('big', 306, 0, (42, 68, 43, 50), 9, 'Work-'),
    ('big', 306, 0, (42, 74, 54, 61), 9, 'room A'),
    ('big', 321, 0, (54, 97, 64, 73), 9, 'Fountain'),
    ('big', 321, 0, (54, 80, 75, 84), 9, 'Patio'),
    ('big', 291, 0, (92, 130, 83, 91), 7, 'Hallway'),
    ('big', 294, 0, (60, 94, 78, 86), 9, 'Hallway'),          # squeezed variant: last
]
# single-line title strips, the whole cell: (rgcn, text)
STRIP_TEXTS = [
    (294, 'Detention Center: Hallway'), (300, 'Prison: Hallway'), (306, 'Prison: Workroom A'),
    (309, 'Prison: Special Cell'), (312, 'Prison: Courtyard'), (297, 'Detention Center: Holding Cell'),
    (346, 'Orphanage: Front Yard'), (352, 'District Court: 3rd Floor Lobby'), (282, 'Gourd Lake Park: Stage'),
    (288, "President's Plane: Office"), (324, "Contest Venue: Master's Room"), (331, 'Grand Tower: Viewing Platform'),
]


# lines of the two-line title strips: (rgcn, rows, text)
STRIP_LINE_TEXTS = [(315, (2, 13), 'Zodiac Art Gallery:'), (315, (14, 24), 'Fountain Patio'), (318, (14, 24), 'Winter Palace')]


def _bundle(idl, g):
    return Bundle(idl.blob(RECN_OF.get(g, g - 1)), idl.blob(g))


def _derive(face, ch, rows, src):
    """A glyph built from rows of the face's own letters: rows is a list of (letter, row index)."""
    bits = []
    for c, r in rows:
        bits.append(face.g[c][0][r])
    w = set(len(b) for b in bits)
    if len(w) != 1:
        raise PlanError('derived %r: rows of different widths %s' % (ch, sorted(w)))
    top = face.g[rows[0][0]][1]
    face.add(ch, tuple(bits), top, len(bits[0]) + 1, src)


def build_faces(fan_idl):
    """-> {'big': Face, 'strip': Face} cut from the fan's own labels. The letters the fan's labels do not
    have are derived from the face's own letters: h = the stem of l over the arch of n, x = the first
    rows of y, mirrored (the strip face has an h of its own, which is that shape; no x anywhere)."""
    faces = {}
    cache = {}
    for name, g, k, box, ink, text in SOURCES:
        if (g, k) not in cache:
            cache[(g, k)] = _bundle(fan_idl, g).grid(k)[0]
        harvest(faces.setdefault(name, Face(5)), cache[(g, k)], box, ink, text, '%d %s' % (g, text))
    strip = faces['strip'] = Face(rn.STRIP_SPACE)
    for g, text in STRIP_TEXTS:
        a = _bundle(fan_idl, g).grid(1)[0]
        harvest(strip, a, (0, a.shape[1] - 1, 0, a.shape[0] - 1), rn.STRIP_FILL, text, 'strip %d %s' % (g, text))
    for g, (y0, y1), text in STRIP_LINE_TEXTS:
        a = _bundle(fan_idl, g).grid(1)[0]
        harvest(strip, a, (0, a.shape[1] - 1, y0, y1), rn.STRIP_FILL, text, 'strip %d %s' % (g, text))
    big = faces['big']
    nb = big.g['n'][0]
    lb = big.g['l'][0]
    if nb != strip.g['n'][0] or lb != strip.g['l'][0]:
        raise PlanError('the big face and the strip face no longer share n and l')
    big.add('h', tuple(lb[0][:1] + '0' * (len(nb[0]) - 1) for _ in range(len(lb) - len(nb))) + tuple(nb),
            big.g['l'][1], len(nb[0]) + 1, 'derived: stem of l over the arch of n (the strip face has this h)')
    if big.g['h'][0] != strip.g['h'][0]:
        raise PlanError("the derived h is not the strip face's h")
    yb = big.g['y'][0]
    big.add('x', (yb[0], yb[1], yb[3], yb[3], yb[1], yb[0]), big.g['o'][1], len(yb[0]) + 1, 'derived: rows of y, mirrored')
    P, F = big.g['P'][0], big.g['F'][0]
    if len(P) != 8 or P[4] != '10000' or F[0] != '11111':
        raise PlanError('the fan\'s big P and F are not the shapes the derived L expects')
    big.add('L', tuple([P[4]] * 7 + [F[0]]), big.g['P'][1], 6, 'derived: stem of P over the bar of F')
    ys = strip.g['y'][0]
    strip.add('x', (ys[0], ys[3], ys[5], ys[5], ys[3], ys[0]), strip.g['o'][1], len(ys[0]) + 1, 'derived: rows of y, mirrored')
    wedge = faces['wedge'] = rn.build_faces(rn.Source(fan_idl))['wedge']        # the small olive face (4 px letters)
    harvest(wedge, _bundle(fan_idl, 315).grid(0)[0], (70, 82, 41, 48), 12, 'EV', '315 EV')
    E = wedge.g['E'][0]
    wedge.add('L', tuple([E[1]] * 5 + [E[0]]), wedge.g['E'][1], 5, 'derived: stem of E over the bar of E')
    return faces


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _xs(pts):
    return min(x for x, _ in pts), max(x for x, _ in pts)


def erase_colours(grid, rect, colours, ground, what):
    """Everything in `rect` (x0, x1, y0, y1) that carries one of `colours` goes back to `ground`; any
    other index but the ground inside the rect raises (the rect must hold the label and nothing else)."""
    x0, x1, y0, y1 = rect
    n = 0
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            v = int(grid[y, x])
            if v in colours:
                grid[y, x] = ground
                n += 1
            elif v != ground:
                raise PlanError('%s: (%d,%d) is index %d, not a label colour %s or the ground %d' % (what, x, y, v, sorted(colours), ground))
    if not n:
        raise PlanError('%s: nothing to erase in %s' % (what, rect))
    return n


def require_flat(grid, rect, value, what):
    x0, x1, y0, y1 = rect
    sub = grid[y0:y1 + 1, x0:x1 + 1]
    bad = np.argwhere(sub != value)
    if len(bad):
        y, x = bad[0]
        raise PlanError('%s: after erasing, (%d,%d) is %d, not the ground %d' % (what, x + x0, y + y0, sub[y, x], value))


def paint_checked(grid, lines, face, style, allow, what, over=()):
    """Paint text lines [(text, x, baseline)] with `style`; every ink and ring pixel must lie on a pixel
    that holds the style's ground (style.ground_at) in the erased picture, or one of the indices in `over`
    (a decoration the label may lie on top of), and inside `allow` (a set of (x, y), or None).
    -> the set of ink pixels."""
    ink = set()
    for text, x, b in lines:
        m, _ = layout(face, text, x, b)
        ink |= m
    return paint_ink(grid, ink, style, allow, what, over)


def paint_ink(grid, ink, style, allow, what, over=()):
    orth, diag = ring_of(ink)
    h, w = grid.shape
    for q in ink | orth | diag:
        if not (0 <= q[0] < w and 0 <= q[1] < h):
            raise PlanError('%s: the new label leaves the picture at %s' % (what, q))
        if allow is not None and q not in allow:
            raise PlanError('%s: the new label leaves its room at %s' % (what, q))
        if grid[q[1], q[0]] != style.ground_at(q[0], q[1]) and int(grid[q[1], q[0]]) not in over:
            raise PlanError('%s: the new label covers (%d,%d), which is index %d, not ground %d'
                            % (what, q[0], q[1], grid[q[1], q[0]], style.ground_at(q[0], q[1])))
    paint(grid, ink, style)
    return ink


# ---------------------------------------------------------------------------
# class 1: the office of room 1202 (Japanese in the fan's own build)
# ---------------------------------------------------------------------------
# JP 執務室 ("office"), 1202号 ("No. 1202") in the lit box, ink 9 with a grey outline;
# 廊下 ("corridor") on the band, ink 3, no outline. Capcom's captions for the place:
# "High Prosecutor's Office - Room 1202" (sce1_c1_00) and "High Prosecutors' Offices -
# Room 1202" (sce3_c0_01); its word for the Japanese 廊下 everywhere in the game is "Corridor".
P1202 = dict(g=349, lit_seed=(45, 35), band_seed=(20, 95),
             jp_lines=[(49, 100, 43, 57), (56, 93, 60, 72)], jp_corridor=(58, 92, 90, 100),
             lines=['Office', 'Room 1202'], corridor='Corridor', corridor_baseline=98,
             # Each line is centred in the lit box (columns 41 to 110: 'Office' 34 px at 59, 'Room 1202' 51 px at 50);
             # the rows (block_top) and the corridor label's column are the placement within 2 px of the centred one
             # that stores in 1,311 bytes, the fan's entry holding 1,344.
             block_x=(59, 50), block_top=49, corridor_x=57)
CORRIDOR = Style(7, 3, 3, 5)


def patch_1202(idl, faces, info):
    """-> new RGCN bytes of idlocal entry 349."""
    spec = P1202
    big = faces['big']
    B = _bundle(idl, spec['g'])
    old, _ = B.grid(0)
    new = old.copy()
    # 1. erase the Japanese
    for box in spec['jp_lines']:
        erase_colours(new, box, (9, 12), 7, 'idlocal 349 Japanese lines')
    erase_colours(new, spec['jp_corridor'], (3,), 5, 'idlocal 349 Japanese corridor')
    lit = interior(new, spec['lit_seed'], 7)
    band = interior(new, spec['band_seed'], 5)
    x0, x1, y0, y1 = _xs(lit) + (min(y for _, y in lit), max(y for _, y in lit))
    require_flat(new, (x0 + 1, x1 - 1, y0 + 1, y1 - 12), 7, 'idlocal 349 lit box')
    require_flat(new, (spec['jp_corridor'][0], spec['jp_corridor'][1], 90, 99), 5, 'idlocal 349 corridor band')
    # 2. the two lines in the lit box: left aligned, the block centred, 11 rows apart like the fan's
    big.space = 5
    widths = [text_width(big, t) for t in spec['lines']]
    bw = max(widths)
    rows = 8 + 11
    iy0 = min(y for _, y in lit); iy1 = max(y for _, y in lit)
    ix0, ix1 = _xs(lit)
    top = spec['block_top']
    placed = [(t, spec['block_x'][i], top + 7 + i * 11) for i, t in enumerate(spec['lines'])]
    ink1 = paint_checked(new, placed, big, BIG, lit, 'idlocal 349 lit label')
    # 3. the corridor label, centred where the Japanese one was
    cw = text_width(big, spec['corridor'])
    cx = spec['corridor_x']
    ink2 = paint_checked(new, [(spec['corridor'], cx, spec['corridor_baseline'])], big, CORRIDOR, band, 'idlocal 349 corridor')
    info['1202'] = dict(lines=placed, widths=widths, corridor=(cx, cx + cw - 1), box=(ix0, ix1, iy0, iy1))
    info['1202_px'] = B.write(0, old, new)
    return B.result()


# ---------------------------------------------------------------------------
# the engine: take the fan's old labels off the ground and letter the new ones
# ---------------------------------------------------------------------------
def footprint(grid, ink, box, text, halo, quirks=()):
    """The fan's label with ink index `ink` inside `box` (spelling `text`, ring colour `halo`).
    Raises unless it follows the fan's own rule: every pixel of its 8-neighbour ring holds `halo`.
    `quirks` are pixels of `halo` the fan drew outside its own ring rule (they go with the label).
    -> dict(mask=ink pixels, E=ink, ring and quirks, l, r, base)."""
    m = ink_mask(grid, ink, box)
    runs = segment(m, box)
    letters = [c for c in text if c != ' ']
    if len(runs) != len(letters):
        raise PlanError('label %r in %s: %d column runs for %d letters' % (text, box, len(runs), len(letters)))
    orth, diag = ring_of(m)
    h, w = grid.shape
    ok = set(halo) if isinstance(halo, tuple) else set([halo])      # a tuple: the colours the ring may show (a
    for (x, y) in orth | diag:                                         # checkerboard ground that has the ring's colour)
        if 0 <= x < w and 0 <= y < h and grid[y, x] not in ok:
            raise PlanError('label %r in %s: ring pixel (%d,%d) is index %d, not %s' % (text, box, x, y, grid[y, x], sorted(ok)))
    for (x, y) in quirks:
        if grid[y, x] != halo:
            raise PlanError('label %r in %s: quirk pixel (%d,%d) is index %d, not %d' % (text, box, x, y, grid[y, x], halo))
    base = collections.Counter(r[3] for r in runs).most_common(1)[0][0]
    return dict(mask=m, E=m | orth | diag | set(quirks), l=min(r[0] for r in runs), r=max(r[1] for r in runs), base=base)


def old_gap(grid, ink, box, text):
    """The gap the fan left between the words of its label (pen advance of the first blank)."""
    return rn._word_space(rn._runs_label(grid, box, ink, text)[1], text)


def centred(face, text, l, r):
    """Left column that centres `text` on the columns l..r."""
    return l + ((r - l + 1) - text_width(face, text)) // 2


def relabel(grid, olds, ground, news, what):
    """Erase the old labels and paint the new ones.
    olds   [(ink, box, text, halo colour[, quirks])]  the fan's labels to take off
    ground int, or a function (x, y) -> index: what lies under the old labels
    news   [(face, style, lines[, over])]   lines are (text, x, baseline); the style's ground is `ground`;
                                            `over` are indices of a decoration the label may lie on top of
    Every pixel a new label (ink and ring) covers must hold the ground after the erase.
    -> (new grid, [footprints], [ink sets])."""
    gf = ground if callable(ground) else (lambda x, y, v=ground: v)
    fps = [footprint(grid, *o) for o in olds]
    E = set()
    for fp in fps:
        E |= fp['E']
    new = grid.copy()
    for (x, y) in E:
        new[y, x] = gf(x, y)
    inks = [paint_checked(new, n[2], n[0], n[1], None, what, n[3] if len(n) > 3 else ()) for n in news]
    return new, fps, inks


def rot_label(face, text, x_left, y_top, rows):
    """The ink of `text` set horizontally and turned a quarter clockwise (the fan turns the label of a
    vertical corridor that way): `rows` is the height of the horizontal label's box (ascender to the
    descender row), (x_left, y_top) the top-left pixel of the turned box. -> set of (x, y)."""
    pts, _ = layout(face, text, 0, rows - 2)
    xs = [x for x, _ in pts]
    arr = np.zeros((rows, max(xs) + 1), np.int8)
    for (x, y) in pts:
        arr[y, x] = 1
    t = np.rot90(arr, 3)
    return set((int(x) + x_left, int(y) + y_top) for y, x in np.argwhere(t))


def strip_edit(grid, text, name_old, name_new, face, what):
    """A one-line title strip: keep everything before the name, draw `name_new` from where `name_old`
    began, the fan's way (ink 4, shadow 3 one row down and one right, ground 0). -> (new grid, x, end)."""
    m, runs, base = rn._runs_label(grid, rn.STRIP_BOX, rn.STRIP_FILL, text)
    letters = [c for c in text if c != ' ']
    n_old = len([c for c in name_old if c != ' '])
    x_name = runs[len(letters) - n_old][0]
    if ' ' in name_old:
        face.space = rn._word_space(runs[len(letters) - n_old:], name_old)
    new = grid.copy()
    new[:, x_name - 2:] = 0
    mask, (a, z) = layout(face, name_new, x_name, base)
    if z > rn.STRIP_BOX[1] - 1:
        raise PlanError('%s: the name ends at column %d of 160' % (what, z))
    rn.paint_strip(new, mask)
    return new, x_name, z


def strip_lines(grid, lines, face, what):
    """A title strip of several lines drawn again from the start of each line, the fan's way. lines is
    [((y0, y1), old text, new text)], y0..y1 the rows the line's ink and shadow lie in. -> new grid."""
    new = grid.copy()
    for (y0, y1), old_text, new_text in lines:
        m, runs, base = rn._runs_label(grid, (0, grid.shape[1] - 1, y0, y1), rn.STRIP_FILL, old_text)
        if ' ' in old_text:
            face.space = rn._word_space(runs, old_text)
        blk = new[y0:y1 + 1, :]
        blk[blk >= 0] = 0
        mask, (a, z) = layout(face, new_text, runs[0][0], base)
        if z > grid.shape[1] - 2:
            raise PlanError('%s: the line ends at column %d of %d' % (what, z, grid.shape[1]))
        rn.paint_strip(new, mask)
    return new


# ---------------------------------------------------------------------------
# class 2: the prison and the detention center (idlocal 291 to 312)
# ---------------------------------------------------------------------------
# Capcom's captions for these places: "Detention Center - Corridor", "Prison - Corridor",
# "Prison - Workshop", "Prison - Maximum Security", "Prison - Yard" (sce1_c1_02, sce1_c0_05,
# sce1_c0_03, sce1_c1_07, sce1_c2_01); Capcom's own plan of the prison (cut01_004_eng) letters the
# rooms Workshop A / Workshop B / Maximum Security / Corridor and the Detention Center plan
# (cut01_008_eng) Holding Cells / Corridor.
OLIVE5 = Style(7, 3, 3, 5)           # olive letters on flat ground 5 (unlit rooms and corridor bands)
OLIVE = lambda g: Style(7, 3, 3, g)
WHITE = BIG                          # white letters on the lit room (ground 7)
GRID294 = lambda x, y: 4 if (x in (70, 81) or (y in (46, 56, 65) and not 71 <= x <= 80)) else 5     # the cell block: walls between three columns of cells, the middle column open


def _strip_face(faces):
    f = faces['strip']
    f.space = rn.STRIP_SPACE
    return f


def _pc(idl, g):
    B = _bundle(idl, g)
    return B, B.grid(0)[0], B.grid(1)[0]


def _lab(old, ink, box, text, halo, quirks=()):
    return footprint(old, ink, box, text, halo, quirks)


def callout_303(grid, big, what):
    """Take "Spec. / Cell" off the room at the right end of idlocal 303 and letter "Maximum / Security" on the
    ground below it as a callout: the fan's marker (a 3 x 3 ring of the callout colour 13) in the room, a one pixel
    line of that colour out through the wall and down the empty ground to the label, a dark rim on both sides of
    the line as the fan's leaders have. -> new grid."""
    sc = footprint(grid, 7, (110, 133, 67, 77), 'Spec.', 3)
    cl = footprint(grid, 7, (110, 123, 81, 88), 'Cell', 3)
    new, _, _ = relabel(grid, [(7, (110, 133, 67, 77), 'Spec.', 3), (7, (110, 123, 81, 88), 'Cell', 3)], 5, [], what)
    ink = set()
    for text, x, b in (('Maximum', 96, 115), ('Security', 95, 125)):
        ink |= layout(big, text, x, b)[0]
    paint_ink(new, ink, Style(7, 3, 3, 2), None, what)
    line = set()
    for dx in range(3):
        for dy in range(3):
            if (dx, dy) != (1, 1):
                line.add((129 + dx, 79 + dy))
    line |= set((x, 81) for x in range(132, 143))
    line |= set((142, y) for y in range(81, 121))      # one column right of where it first ran: clear of the 'y' of 'Security'
    h, w = new.shape
    for (x, y) in line:
        for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if q not in line and 0 <= q[0] < w and 0 <= q[1] < h and new[q[1], q[0]] == 2:
                new[q[1], q[0]] = 1
    for (x, y) in line:
        if new[y, x] not in (2, 1, 5, 8):
            raise PlanError('%s: the callout line meets index %d at (%d,%d)' % (what, new[y, x], x, y))
        new[y, x] = 13
    return new


def patch_prison(idl, faces, info):
    """-> {RGCN entry: new bytes} for idlocal 291, 294, 297, 300, 303, 306, 309 and 312."""
    big, strip = faces['big'], _strip_face(faces)
    out = {}
    stats = info.setdefault('prison', {})

    # 291: the detention center, visitor's room lit: the corridor band's label
    B, old, sold = _pc(idl, 291)
    fp = _lab(old, 7, (92, 130, 83, 91), 'Hallway', 3, [(125, 89)])
    new, _, _ = relabel(old, [(7, (92, 130, 83, 91), 'Hallway', 3, [(125, 89)])], 5,
                        [(big, OLIVE5, [('Corridor', fp['l'], fp['base'])])], 'idlocal 291')
    stats[291] = dict(px=B.write(0, old, new))
    out[291] = B.result()

    # 294: the cell block (olive, on the grid of walls) and the lit corridor, and the strip
    B, old, sold = _pc(idl, 294)
    f1 = _lab(old, 7, (63, 79, 44, 51), 'Cell', 3)
    f2 = _lab(old, 7, (63, 89, 55, 62), 'Block', 3)
    f3 = _lab(old, 9, (60, 94, 78, 86), 'Hallway', 12, [(90, 84)])
    new, _, _ = relabel(old, [(7, (63, 79, 44, 51), 'Cell', 3), (7, (63, 89, 55, 62), 'Block', 3)], GRID294,
                        [(big, OLIVE(GRID294), [('Holding', 58, f1['base']), ('Cells', 58, f2['base'])])], 'idlocal 294 cell block')
    new, _, _ = relabel(new, [(9, (60, 94, 78, 86), 'Hallway', 12, [(90, 84)])], 7,
                        [(big, WHITE, [('Corridor', centred(big, 'Corridor', f3['l'], f3['r']), f3['base'])])], 'idlocal 294 corridor')
    snew, x, z = strip_edit(sold, 'Detention Center: Hallway', 'Hallway', 'Corridor', strip, 'idlocal 294 strip')
    stats[294] = dict(px=B.write(0, old, new) + B.write(1, sold, snew), strip=(x, z))
    out[294] = B.result()

    # 297: the holding cell, the vertical corridor's label turned a quarter (the fan's 'Hallway' is the
    # horizontal olive label turned clockwise, to the pixel)
    B, old, sold = _pc(idl, 297)
    box = (64, 80, 36, 80)
    m_old = ink_mask(old, 7, box)
    turned = rot_label(big, 'Hallway', 68, 40, 9)
    if turned != m_old:
        raise PlanError('idlocal 297: the vertical Hallway is not the horizontal one turned a quarter clockwise')
    orth, diag = ring_of(m_old)
    quirk = [(70, 73)]          # the same stray halo pixel the horizontal Hallways carry, turned with the label
    for (x, y) in list(orth | diag) + quirk:
        if old[y, x] != 3:
            raise PlanError('idlocal 297: ring pixel (%d,%d) of the vertical label is index %d, not 3' % (x, y, old[y, x]))
    new = old.copy()
    for (x, y) in m_old | orth | diag | set(quirk):
        new[y, x] = 5
    paint_ink(new, rot_label(big, 'Corridor', 68, 39, 9), OLIVE5, None, 'idlocal 297')
    stats[297] = dict(px=B.write(0, old, new))
    out[297] = B.result()

    # 300 and 303: the long corridor, work rooms A and B, and (303) the special cell
    for g in (300, 303):
        B, old, sold = _pc(idl, g)
        wa = _lab(old, 7, (44, 70, 29, 37), 'Work-', 3)
        wb = _lab(old, 7, (82, 108, 29, 37), 'Work-', 3)
        ra = _lab(old, 7, (44, 76, 40, 48), 'room A', 3)
        rb = _lab(old, 7, (82, 114, 40, 48), 'room B', 3)
        hw = _lab(old, 9, (48, 86, 69, 77), 'Hallway', 12, [(81, 75)])
        # The two work rooms are 37 px wide and 24 rows tall, and the fan lettered "Work-" / "room A" with no row to
        # spare. "shop" hangs a p three rows below its baseline, so the whole label moves up two rows (it keeps the
        # fan's 11 rows between the lines). The fan closed the gap between "room" and "A" to the width it had
        # room for; "shop A" takes the same gap.
        olds = [(7, (44, 70, 29, 37), 'Work-', 3), (7, (82, 108, 29, 37), 'Work-', 3),
                (7, (44, 76, 40, 48), 'room A', 3), (7, (82, 114, 40, 48), 'room B', 3)]
        top = wa['base'] - 2
        sp_a = rn._word_space(rn._runs_label(old, (44, 76, 40, 48), 7, 'room A')[1], 'room A')
        sp_b = rn._word_space(rn._runs_label(old, (82, 114, 40, 48), 7, 'room B')[1], 'room B')
        if sp_a != sp_b:
            raise PlanError('idlocal %d: room A and room B have different word gaps' % g)
        big.space = sp_a
        try:
            new, _, _ = relabel(old, olds, 5,
                                [(big, OLIVE5, [('Work-', wa['l'], top), ('shop A', ra['l'], top + 11),
                                                ('Work-', wb['l'], top), ('shop B', rb['l'], top + 11)])],
                                'idlocal %d work rooms' % g)
        finally:
            big.space = 5
        new, _, _ = relabel(new, [(9, (48, 86, 69, 77), 'Hallway', 12, [(81, 75)])], 7,
                            [(big, WHITE, [('Corridor', centred(big, 'Corridor', hw['l'], hw['r']), hw['base'])], (6,))],
                            'idlocal %d corridor' % g)       # the faint circle of the hall is index 6; the fan's label lay on it too
        if g == 303 and 303 in LARGER:
            # "Spec. / Cell" is the special cell, a 26 px room: Capcom's "Maximum Security" does not fit it. The
            # label goes where the fan puts what does not fit (its "To Detention Center" callout): on the empty
            # ground below, in two lines, with a marker in the room and a leader line to the label.
            new = callout_303(new, big, 'idlocal 303 maximum security')
        snew, x, z = strip_edit(sold, 'Prison: Hallway', 'Hallway', 'Corridor', strip, 'idlocal %d strip' % g)
        stats[g] = dict(px=B.write(0, old, new) + B.write(1, sold, snew), strip=(x, z))
        out[g] = B.result()

    # 306: workroom A lit, workroom B, the corridor band
    B, old, sold = _pc(idl, 306)
    ra = _lab(old, 9, (42, 74, 54, 61), 'room A', 12)
    rb = _lab(old, 7, (97, 129, 54, 61), 'room B', 3)
    hw = _lab(old, 7, (75, 113, 88, 96), 'Hallway', 3, [(108, 94)])
    new, _, _ = relabel(old, [(9, (42, 74, 54, 61), 'room A', 12)], 7,
                        [(big, WHITE, [('shop A', ra['l'], ra['base'])])], 'idlocal 306 workshop A')
    new, _, _ = relabel(new, [(7, (97, 129, 54, 61), 'room B', 3), (7, (75, 113, 88, 96), 'Hallway', 3, [(108, 94)])], 5,
                        [(big, OLIVE5, [('shop B', rb['l'], rb['base']), ('Corridor', centred(big, 'Corridor', hw['l'], hw['r']), hw['base'])])],
                        'idlocal 306 workshop B and corridor')
    snew, x, z = strip_edit(sold, 'Prison: Workroom A', 'Workroom A', 'Workshop A', strip, 'idlocal 306 strip')
    stats[306] = dict(px=B.write(0, old, new) + B.write(1, sold, snew), strip=(x, z))
    out[306] = B.result()

    # 309 (only when listed in LARGER, see there): the corridor band, the maximum security room lit
    if 309 in LARGER:
        B, old, sold = _pc(idl, 309)
        hw = _lab(old, 7, (20, 58, 65, 73), 'Hallway', 3, [(53, 71)])
        new, _, _ = relabel(old, [(7, (20, 58, 65, 73), 'Hallway', 3, [(53, 71)])], 5,
                            [(big, OLIVE5, [('Corridor', hw['r'] - 40, hw['base'])])], 'idlocal 309 corridor')   # ends where Hallway ended
        lit = interior(old, (70, 100), 7)
        erased = new.copy()
        sp = _lab(old, 9, (74, 110, 65, 75), 'Special', 12)
        ce = _lab(old, 9, (74, 90, 79, 86), 'Cell', 12)
        for fp in (sp, ce):
            for (x, y) in fp['E']:
                erased[y, x] = 7
        lit = interior(erased, (70, 100), 7)
        ix0, ix1 = _xs(lit)
        iy0, iy1 = min(y for _, y in lit), max(y for _, y in lit)
        wid = max(text_width(big, t) for t in ('Maximum', 'Security'))
        pitch = ce['base'] - sp['base']       # the fan's own two-line pitch ('Special' / 'Cell'), 14 rows: the room has the height
        top = int(np.ceil((iy0 + iy1) / 2.0 - (8 + pitch) / 2.0))
        xl = ix0 + ((ix1 - ix0 + 1) - wid) // 2
        new, _, _ = relabel(new, [(9, (74, 110, 65, 75), 'Special', 12), (9, (74, 90, 79, 86), 'Cell', 12)], 7,
                            [(big, WHITE, [('Maximum', xl, top + 7), ('Security', xl, top + 7 + pitch)])], 'idlocal 309 maximum security')
        snew, x, z = strip_edit(sold, 'Prison: Special Cell', 'Special Cell', 'Maximum Security', strip, 'idlocal 309 strip')
        stats[309] = dict(px=B.write(0, old, new) + B.write(1, sold, snew), strip=(x, z), lit=(ix0, ix1, iy0, iy1), block=(xl, top))
        out[309] = B.result()

    # 312: the yard
    B, old, sold = _pc(idl, 312)
    c1 = _lab(old, 9, (75, 107, 54, 61), 'Court-', 12)
    c2 = _lab(old, 9, (75, 98, 65, 73), 'yard', 12)
    cx = centred(big, 'Yard', min(c1['l'], c2['l']), max(c1['r'], c2['r']))
    cy = int(round((54 + 73) / 2.0 + 3.5))
    new, _, _ = relabel(old, [(9, (75, 107, 54, 61), 'Court-', 12), (9, (75, 98, 65, 73), 'yard', 12)], 7,
                        [(big, WHITE, [('Yard', cx, cy)])], 'idlocal 312 yard')
    snew, x, z = strip_edit(sold, 'Prison: Courtyard', 'Courtyard', 'Yard', strip, 'idlocal 312 strip')
    stats[312] = dict(px=B.write(0, old, new) + B.write(1, sold, snew), strip=(x, z), label=(cx, cy))
    out[312] = B.result()
    return out
# ---------------------------------------------------------------------------
# class 3: the plans of the prison and the detention center (jpn/upcut_local.bin 36, 40, 48, 52, 78, 80, 82)
# ---------------------------------------------------------------------------
# 256x192 pictures, 8 bits a pixel, flat grounds and straight walls, lettered in a 5x7 pixel face: the ink is
# palette index 1 (dark brown; a dark green on the cells), a one pixel outline round it (white; a pale green on
# the cells) and, on the diagonal corners of the outline, the blend of that white with the ground under it.
# Capcom's own plans (cut01_004_eng, cut01_008_eng, cut01_00e_eng, cut01_015_eng) letter the rooms Workshop A /
# Workshop B / Corridor / Maximum Security / Holding Cells / Office Area / Yard / Connecting Corridor / Main
# Prison, and call the picture a Layout, not a Map.
UP_W, UP_H = 256, 192
GALLERY_ENTRY = 114
BOARD_ENTRY = 116

# (entry, ink index, box, text): the fan's own labels the letters are cut from
PLAN_SOURCES = [
    (36, 1, (10, 70, 5, 16), 'Prison Map'), (36, 1, (85, 146, 27, 38), 'Workroom A'), (36, 1, (152, 214, 27, 38), 'Workroom B'),
    (36, 1, (16, 34, 71, 81), 'Cell'), (36, 1, (208, 246, 94, 106), 'Special'), (36, 1, (83, 121, 114, 124), 'Hallway'),
    (40, 1, (29, 118, 7, 13), 'Detention Center'), (40, 1, (79, 117, 26, 37), 'Offices'),
    (40, 1, (156, 207, 61, 71), 'Courtyard'), (40, 1, (110, 172, 120, 131), 'Passageway'),
    (40, 1, (186, 228, 7, 13), '(Partial)'), (48, 1, (11, 47, 21, 31), 'Center'),
    # the hall's plan 102 (the same face, ink 15): the capitals Capcom's words need and the fan's labels had
    (102, 15, (120, 136, 46, 56), 'EV'), (102, 15, (104, 152, 76, 86), 'Fountain'), (102, 15, (106, 149, 177, 187), 'Gardens'),
    (102, 15, (150, 173, 142, 152), 'Rec.'), (102, 15, (146, 177, 152, 162), 'Booth'), (102, 15, (81, 107, 152, 162), 'Room'),
]


def up_grid(gfx):
    """Index grid (192 x 256) of an upcut_local RGCN (8 bits a pixel, tiles in raster order)."""
    from nitro import ncgr
    data, bpp, cnt, tw, th = ncgr(gfx)
    if bpp != 8:
        raise PlanError('upcut_local picture is not 8 bpp')
    n = len(data) // 64
    g = np.zeros((UP_H, UP_W), np.int32)
    for t in range(n):
        g[(t // 32) * 8:(t // 32) * 8 + 8, (t % 32) * 8:(t % 32) * 8 + 8] = np.frombuffer(data[t * 64:(t + 1) * 64], np.uint8).reshape(8, 8)
    return g


def up_set(gfx, grid):
    """The RGCN with its tile data replaced by `grid`; nothing else of the entry changes."""
    from nitro import _sections
    p, size, body = _sections(gfx)[b'RAHC']
    dsize = struct.unpack_from('<I', body, 16)[0]
    doff = struct.unpack_from('<I', body, 20)[0]
    start = p + 8 + doff
    out = bytearray(gfx)
    tiles = bytearray(dsize)
    for t in range(dsize // 64):
        tiles[t * 64:(t + 1) * 64] = grid[(t // 32) * 8:(t // 32) * 8 + 8, (t % 32) * 8:(t % 32) * 8 + 8].astype(np.uint8).tobytes()
    out[start:start + dsize] = tiles
    return bytes(out)


def up_table(upcut_bytes):
    import txtcut
    return txtcut.table(upcut_bytes)


_CONT_CACHE = {}


def continuation(grid, E, maxd=48, strict=None):
    """What lies under the pixels E (a set of (x, y)): each pixel continues the straight line the nearest
    pixels outside E on its column (or its row) agree on. Where the column and the row both agree and differ,
    the pixel takes the one that is not the colour of most of its surroundings (a wall running through flat
    ground). -> {(x, y): value}. Raises where neither direction agrees."""
    key = (hashlib.sha1(grid.tobytes()).hexdigest(), hash(frozenset(E)), maxd, hash(frozenset(strict)) if strict is not None else None)
    if key in _CONT_CACHE:
        return dict(_CONT_CACHE[key])
    H, W = grid.shape
    out = {}
    for (x, y) in E:
        try:
            out[(x, y)] = _continue_pixel(grid, E, x, y, maxd)
        except PlanError:
            if strict is None or (x, y) in strict:
                raise
    _CONT_CACHE[key] = dict(out)
    return out


def _continue_pixel(grid, E, x, y, maxd):
    H, W = grid.shape
    c = []
    U = next((int(grid[yy, x]) for yy in range(y - 1, max(-1, y - maxd), -1) if (x, yy) not in E), None)
    D = next((int(grid[yy, x]) for yy in range(y + 1, min(H, y + maxd)) if (x, yy) not in E), None)
    L = next((int(grid[y, xx]) for xx in range(x - 1, max(-1, x - maxd), -1) if (xx, y) not in E), None)
    R = next((int(grid[y, xx]) for xx in range(x + 1, min(W, x + maxd)) if (xx, y) not in E), None)
    if U is not None and U == D:
        c.append(U)
    if L is not None and L == R:
        c.append(L)
    vals = sorted(set(c))
    if len(vals) == 1:
        return vals[0]
    if len(vals) == 2:
        near = collections.Counter(int(grid[yy, xx]) for yy in range(max(0, y - 6), min(H, y + 7))
                                   for xx in range(max(0, x - 6), min(W, x + 7)) if (xx, yy) not in E)
        major = near.most_common(1)[0][0]
        minor = [v for v in vals if v != major]
        if len(minor) != 1:
            raise PlanError('continuation at (%d,%d): %s and %s both lines, neither the surroundings' % (x, y, vals[0], vals[1]))
        return minor[0]
    raise PlanError('continuation at (%d,%d): the pixels round it do not agree on a straight line' % (x, y))


def label8(grid, ink, box, text, skip=()):
    """One of the fan's plan labels: ink pixels (index `ink` inside `box`, minus the rectangles in `skip`),
    its outline ring, and where it stands. -> dict(mask, orth, diag, E, l, r, base, orth_val)."""
    m = ink_mask(grid, ink, box)
    for (a, b, c, d) in skip:
        m = set(p for p in m if not (a <= p[0] <= b and c <= p[1] <= d))
    runs = segment(m, box)
    n = len([c for c in text if c != ' '])
    if len(runs) != n:
        raise PlanError('plan label %r in %s: %d column runs for %d letters' % (text, box, len(runs), n))
    orth, diag = ring_of(m)
    inskip = lambda x, y: any(a <= x <= b and c <= y <= d for (a, b, c, d) in skip)
    vals = collections.Counter(int(grid[y, x]) for x, y in orth if not inskip(x, y))
    if len(vals) != 1:
        raise PlanError('plan label %r in %s: its outline is %s, not one colour' % (text, box, dict(vals)))
    base = collections.Counter(r[3] for r in runs).most_common(1)[0][0]
    return dict(mask=m, orth=orth, diag=diag, E=m | orth | diag, l=min(r[0] for r in runs), r=max(r[1] for r in runs),
                base=base, orth_val=list(vals)[0], ink=ink)


def rect8(box, ink, orth_val, base, l, r):
    """An old label taken off as a whole rectangle (x0, x1, y0, y1): for the title of 40, 80 and 82, whose
    letters cross two walls of the same colour as the ink, so its ink cannot be told from them by colour. The
    walls come back by continuation from the rows above and below the band."""
    x0, x1, y0, y1 = box
    return dict(mask=set(), orth=set(), diag=set(), E=set((x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)),
                l=l, r=r, base=base, orth_val=orth_val, ink=ink)


SLASH_SHA256 = 'a8b0fbee91fad747abb7b173be3638b5e0b29b02c4f4f11a9ad223afc9d7757e'      # of the cut slash (its seven rows of three, joined by '/'), recorded once from the fan's picture


def plan_faces(fan_up):
    """-> the plan face (5 px letters) cut from the fan's own labels in fan_up (upcut_local bytes). Letters its
    labels do not have are derived from its own: L from the stem of P and the bar of H, h from the stem rows
    of l over the arch of n, v, x and Y from rows of V, and the slash cut from the title of upcut_local 40."""
    tab = up_table(fan_up)
    face = Face(4)
    cache = {}
    for e, ink, box, text in PLAN_SOURCES:
        if e not in cache:
            cache[e] = up_grid(tab[e])
        harvest(face, cache[e], box, ink, text, 'upcut_local %d %s' % (e, text))
    g = face.g
    P, H, n, l, y = g['P'][0], g['H'][0], g['n'][0], g['l'][0], g['y'][0]
    face.add('L', tuple([P[4]] * 6 + [H[3]]), g['P'][1], 6, 'derived: stem of P over the bar of H')
    face.add('h', tuple([P[4], P[4]] + list(n)), g['P'][1], 6, 'derived: stem of P over the arch of n')
    V = g['V'][0]
    face.add('v', tuple(V[2:]), g['n'][1], 6, 'derived: the last five rows of V')
    face.add('x', (V[0], V[4], V[6], V[4], V[0]), g['n'][1], 6, 'derived: the top row, the diagonal row and the tip of V, crossed')
    face.add('Y', (V[0], V[1], V[4], V[6], V[6], V[6], V[6]), g['P'][1], 6, 'derived: the top rows and the tip of V over its stem')
    # the slash of the title of 40 / 80 / 82: the fan's own "/" (ink 1 in columns 121 to 123, rows 7 to 13 of upcut_local 40),
    # cut from the picture; nothing else of the title may touch those columns
    sl = cache[40]
    if (sl[7:14, 120] == 1).any() or (sl[7:14, 124] == 1).any():
        raise PlanError("the slash of upcut_local 40's title is not standing alone in columns 121 to 123")
    bits = tuple(''.join('1' if sl[y, x] == 1 else '0' for x in range(121, 124)) for y in range(7, 14))
    if hashlib.sha256('/'.join(bits).encode()).hexdigest() != SLASH_SHA256:
        raise PlanError("the slash of upcut_local 40's title is not the shape this routine was proven on: %r" % (bits,))
    face.add('/', bits, g['P'][1], 4, 'upcut_local 40 title: the slash')
    return face


def relabel8(grid, groups, face, what, keep=(), skip=()):
    """Erase the fan's labels and letter the new ones, on a plan picture.
    groups  [dict(old=[(ink, box, text)], new=[(text, x or None)], anchor='l'|'c'|'r', dx=0, dy=0)]; new line i
            sits on the baseline of old line i (the last old line for any more), its x from the anchor of the
            old block; the style (ink, outline) is the old label's own
    keep    [(ink, box, text)] labels that stay: the new ones may not touch them, and their corners are read too
    skip    rectangles inside a label's box that are not label (a wall the same colour as the ink)
    The corners of the outline take the blend of the outline colour with the ground, read off every label of
    the picture ((ink, outline, ground index) -> corner index, one to one); a corner over a ground no label of
    the picture stands on stops the build.
    -> (new grid, old footprints, painted, one box (x0, y0, x1, y1) round the old and the new label of each group)."""
    olds, kept = [], []
    for gp in groups:
        olds.append((gp, [o if isinstance(o, dict) else label8(grid, o[0], o[1], o[2], skip) for o in gp['old']]))
    for ink, box, text in keep:
        kept.append(label8(grid, ink, box, text, skip))
    E_old = set()
    for gp, fps in olds:
        for fp in fps:
            E_old |= fp['E']
    E_all = set(E_old)
    for fp in kept:
        E_all |= fp['E']
    ground = continuation(grid, E_all, strict=E_old)
    corner = {}
    learn = []
    for gp, _fps in olds:
        lg = [label8(grid, o[0], o[1], o[2], skip) for o in gp.get('learn', ())]
        learn += lg
        for fp in _fps:                    # a rectangle takes its outline colour from the label it stands for
            if fp['orth_val'] is None:
                fp['orth_val'] = lg[0]['orth_val']
    inskip = lambda x, y: any(a <= x <= b and c <= y <= d for (a, b, c, d) in skip)
    for who, fps_ in (('old', [f for _, fps in olds for f in fps] + learn), ('kept', kept)):
        for fp in fps_:
            for (x, y) in fp['diag']:
                if (x, y) not in ground:       # no straight line to read it from
                    continue
                key = (fp['ink'], fp['orth_val'], ground[(x, y)])
                v = int(grid[y, x])
                if who == 'kept':              # labels that stay only add grounds the old ones do not stand on
                    corner.setdefault(key, v)
                elif corner.setdefault(key, v) != v:
                    raise PlanError('%s: corner pixels next to ground %d are both %d and %d' % (what, key[2], corner[key], v))
    new = grid.copy()
    for p in E_old:
        new[p[1], p[0]] = ground[p]
    protect = set()
    for fp in kept:
        protect |= fp['E']
    h, w_ = new.shape
    painted, boxes = [], []
    for gp, fps in olds:
        l = min(fp['l'] for fp in fps)
        r = max(fp['r'] for fp in fps)
        ink, orth_val = fps[0]['ink'], fps[0]['orth_val']
        inkset = set()
        for i, item in enumerate(gp['new']):
            text, x = item[0], item[1]
            ddy = item[2] if len(item) > 2 else 0
            fp = fps[min(i, len(fps) - 1)]
            if x is None:
                wd = text_width(face, text)
                x = {'l': l, 'c': l + ((r - l + 1) - wd) // 2, 'r': r - wd + 1}[gp.get('anchor', 'l')] + gp.get('dx', 0)
            m, _ = layout(face, text, x, fp['base'] + gp.get('dy', 0) + ddy)
            inkset |= m
        o, d = ring_of(inkset)
        for q in inkset | o | d:
            if not (0 <= q[0] < w_ and 0 <= q[1] < h):
                raise PlanError('%s: the new label leaves the picture at %s' % (what, q))
        if (inkset | o | d) & protect:
            raise PlanError('%s: the new label %r touches a label that stays' % (what, gp['new'][0][0]))
        under = set(ground[q] for fp in fps for q in fp['E'] if q in ground)      # what the old label lay on
        for q in inkset | o | d:
            if int(new[q[1], q[0]]) not in under:
                raise PlanError('%s: the new label %r covers (%d,%d), index %d, which the old label did not lie on %s'
                                % (what, gp['new'][0][0], q[0], q[1], new[q[1], q[0]], sorted(under)))
        painted.append((ink, orth_val, inkset, o, d))
        pts = set(inkset | o | d)
        for fp in fps:
            pts |= fp['E']
        boxes.append((min(x for x, _ in pts), min(y for _, y in pts), max(x for x, _ in pts), max(y for _, y in pts)))
    for ink, orth_val, inkset, o, d in painted:
        for q in d:
            gv = int(new[q[1], q[0]])
            if (ink, orth_val, gv) not in corner:
                raise PlanError('%s: no corner colour known for outline %d over ground %d at %s' % (what, orth_val, gv, q))
            new[q[1], q[0]] = corner[(ink, orth_val, gv)]
        for q in o:
            new[q[1], q[0]] = orth_val
        for q in inkset:
            new[q[1], q[0]] = ink
    return new, [fp for _, fps in olds for fp in fps], painted, boxes


DETENTION = [(1, (10, 60, 92, 102), 'Detention'), (1, (17, 53, 103, 113), 'Center')]
TITLE40 = 'Detention Center / Prison Map (Partial)'
TITLE40_WALLS = [(70, 71, 5, 15), (125, 126, 5, 15)]       # the walls of the offices' column run through the title band


def _title36():
    return dict(old=[(1, (10, 70, 5, 16), 'Prison Map')], new=[('Prison Layout', None)], anchor='l', dx=-5)


def _title40():
    # the old title spans x 31..225, ink rows 7..13 (baseline 13), outline white (9), rows 6 and 14 the outline's
    return dict(old=[rect8((29, 230, 6, 14), 1, None, 13, 31, 225)], new=[('Detention Center/Prison Layout (Partial)', 36)],
                learn=[(1, (29, 230, 5, 15), TITLE40)])


def _workshops():
    return [dict(old=[(1, (85, 146, 27, 38), 'Workroom A')], new=[('Workshop A', None)], anchor='l'),
            dict(old=[(1, (152, 214, 27, 38), 'Workroom B')], new=[('Workshop B', None)], anchor='l'),
            dict(old=[(1, (83, 121, 114, 124), 'Hallway')], new=[('Corridor', None)], anchor='c')]


CELLS36 = [(1, (16, 34, 71, 81), 'Cell'), (1, (53, 71, 71, 81), 'Cell'), (1, (90, 108, 71, 81), 'Cell')]
# upcut_local entry -> (groups, labels that stay)
PLAN_EDITS = {
    36: ([_title36()] + _workshops() +
         [dict(old=[(1, (208, 246, 94, 106), 'Special'), (1, (216, 236, 105, 115), 'Cell')],
               new=[('Maximum', None), ('Security', None)], anchor='c')], CELLS36),
    78: ([_title36()] + _workshops(), CELLS36),
}
DETENTION48 = [(1, (4, 54, 10, 20), 'Detention'), (1, (11, 47, 21, 31), 'Center')]
PRISON40 = (1, (217, 250, 74, 84), 'Prison')


def _offices():      # the offices' column: 52 px between its walls, "Office Area" is 56, so two lines
    return dict(old=[(1, (79, 117, 26, 37), 'Offices')], new=[('Office', None, -7), ('Area', None, 3)], anchor='c')


def _yard40():
    return dict(old=[(1, (156, 207, 61, 71), 'Courtyard')], new=[('Yard', None)], anchor='c')


def _passage40():
    # one column right and one row up of the centred place: the placement within 1 px of it that stores smallest
    # (80 and 82 would otherwise be 15 and 22 bytes over the fan's stored size)
    return dict(old=[(1, (110, 172, 120, 131), 'Passageway')], new=[('Connecting Corridor', None)], anchor='c', dx=1, dy=-1)


PLAN_EDITS[40] = ([_title40(), _offices(), _yard40(), _passage40()], DETENTION + [PRISON40])
PLAN_EDITS[80] = ([_title40(), _offices(), _passage40()], DETENTION + [PRISON40])
PLAN_EDITS[82] = ([_title40(), _offices(), _passage40()], DETENTION + [PRISON40])
# the connecting corridor of 48 is a box 88 px wide between its walls ("Connecting Corridor" is 95): two lines
PLAN_EDITS[48] = ([dict(old=[(1, (77, 139, 79, 90), 'Passageway')], new=[('Connecting', None, -5), ('Corridor', None, 5)], anchor='c'),
                   dict(old=[(1, (187, 220, 42, 52), 'Prison')], new=[('Main Prison', None)], anchor='c')], DETENTION48)
PLAN_EDITS[52] = ([dict(old=[(1, (82, 136, 54, 64), 'Courtyard')], new=[('Yard', None)], anchor='c'),
                   dict(old=[(1, (187, 220, 42, 52), 'Prison')], new=[('Main Prison', None)], anchor='c')], DETENTION48)
# 102, the plain plan of the Zodiac Hall (ink 15): Capcom's cut02_004_eng letters the four rooms Wing, the lift
# Elevator (cut02_010_eng: EL), the middle Fountain Hall, the garden Garden. "Security Room" (41 px of ink in a room
# 38 wide), "Reception" (48 in 36) and "Elevator" (41 in 40) do not fit their rooms and stay as the fan had them
# (Secur. / Room, Rec. / Booth); the lift takes Capcom's other word for it, EL.
KEEP102 = [(15, (54, 92, 41, 51), 'Summer'), (15, (166, 200, 41, 51), 'Winter'), (15, (24, 62, 88, 99), 'Spring'),
           (15, (194, 232, 88, 99), 'Autumn'), (15, (104, 152, 76, 86), 'Fountain'), (15, (77, 113, 142, 152), 'Secur.'),
           (15, (81, 107, 152, 162), 'Room'), (15, (150, 173, 142, 152), 'Rec.'), (15, (146, 177, 152, 162), 'Booth')]
PLAN_EDITS[102] = ([dict(old=[(15, (55, 90, 52, 62), 'Palace')], new=[('Wing', None)], anchor='c'),
                    dict(old=[(15, (166, 200, 52, 62), 'Palace')], new=[('Wing', None)], anchor='c'),
                    dict(old=[(15, (24, 62, 99, 109), 'Palace')], new=[('Wing', None)], anchor='c'),
                    dict(old=[(15, (194, 232, 99, 109), 'Palace')], new=[('Wing', None)], anchor='c'),
                    dict(old=[(15, (120, 136, 46, 56), 'EV')], new=[('EL', None)], anchor='c'),
                    dict(old=[(15, (112, 144, 87, 97), 'Patio')], new=[('Hall', None)], anchor='c'),
                    dict(old=[(15, (106, 149, 177, 187), 'Gardens')], new=[('Garden', None)], anchor='c')], KEEP102)
PLAN_ENTRIES = tuple(sorted(PLAN_EDITS))


# Old wording that stays in a picture this build rewrites because drawing the new wording does not fit the fan's
# stored bytes (see PLAN_FIT; all of it goes with LARGER): (picture, word) for tools/plan_detect.py.
KNOWN_LEFT = set()      # none: 36, 78 and 48 are drawn whole under UP_LARGER

# Which groups of PLAN_EDITS[entry] are drawn: the ones whose result still fits the fan's stored bytes (the
# measured sizes are printed by the build). Every group is drawn for the entries in UP_LARGER.
PLAN_FIT = {36: (1, 2, 3), 78: (1, 2, 3), 48: ()}      # the others: every group (indices into PLAN_EDITS[entry][0])


def plan_groups(e):
    groups, keep = PLAN_EDITS[e]
    fit = PLAN_FIT.get(e)
    return [g for i, g in enumerate(groups) if fit is None or i in fit or e in UP_LARGER], keep


def patch_plans(up_bytes, fan_up_bytes, info):
    """-> {entry: new RGCN bytes} for the plan pictures; letters are cut from the fan's own file.
    info['plans'][entry] holds the pixels changed and the boxes (x0, y0, x1, y1) the changes lie in."""
    tab = up_table(up_bytes)
    face = plan_faces(fan_up_bytes)
    out = {}
    for e in PLAN_ENTRIES:
        groups, keep = plan_groups(e)
        if not groups:
            continue
        grid = up_grid(tab[e])
        new, fps, painted, boxes = relabel8(grid, groups, face, 'upcut_local %d' % e, keep,
                                            TITLE40_WALLS if e in (40, 80, 82) else ())
        out[e] = up_set(tab[e], new)
        info.setdefault('plans', {})[e] = dict(px=int((new != grid).sum()), boxes=boxes)
    return out


UP_FAN_SHA256 = {
    102: '4b7b03b1967f1e1d1f35b880ab5fcd96f8fee4072948b40098e3cbb9f1da171c',
    103: '9ac0fa0f51c937e9c11afc73057eace532035c5d37a2dcc7d0b6dc72b5c40785',      # the fan's upcut_local entries (picture and palette) this module rewrites or reads
    36: 'be58664c7e966068487e2593f89d45e3a22c3f36664c098ede5ede2880fb93c9',
    37: 'a27d9c6b95db019d73c62184ebb0ca5b99a6ebd1451821e0382887058ff3fa29',
    40: '011ab3f7bd50d57f9ce9ff23ba0c4b0e0e21ad2219238bd89cee879e8b9858d3',
    41: 'df9ec66114a24cf2e9b64e5ece2549982157983958feb853b2f021d1b087c144',
    48: '2c6f396fb4c3b8fa680470ebe344addddf5d1e8fd990d81374a29954f70b25c2',
    49: '6d7c46a1ad0f586010adc940bce67958bc0266ab61b4d799b081c10e548c656d',
    52: '614a1619bbca07f33c6870309c33acf6060b12c8cbee8134fca1a7a6345bb6e3',
    53: '4d9fe22a49c927c44af567bcfd804b25a6cd036aab1dbbe33366a0920b1c1b4a',
    78: 'a3477160791e450f3b3db414a7d589bc0101189e95dce51deecd1d4ca86d9c59',
    79: 'a7896b1ea0e62b0863c6ed78e37d02d9bcd091f2ac233472dcb4fb05fe70ea97',
    80: '3a3f288bf225269c364f61c222ea4a5b1d154cabc8fbc46a4d6b3d5bbab57449',
    81: '2e0f59b6b1d9124fb04b02a1dff1bd7f94c8abc734b1c09e68be2121dd78fa34',
    82: '5877eb3759a39b5fa47dd6435d46de819c92a584e7689d1c47fe7eeccc649eb1',
    83: '1651b680c02ab353c4a965a2b9e5e6c23258ab6c00d8cc0c8ae95b834757fd19',
}


GALLERY_SHA256 = {      # the fan's leaflet picture and its palette (upcut_local 114, 115), see tools/gallery_art.py
    114: '9df06777557b272d033ba70b86b28b4ba98817caccb0cc6b09b937b389f06c46',
    115: '217ab8e56e8e7efbddfed5534472ad9640e3c0c0887c40030e1cd7238cde7408',
}


BOARD_SHA256 = {      # the fan's information board and its palette (upcut_local 116, 117), see tools/board_temps.py
    116: '0b94bb096e85c2d8f5d411358577fb8b992736ce343fe16c6d7f4b179557483f',
    117: '53296c78cec222f11ae84f994e9fa94ee4abe9f5904d6aacc2a983779d86f71a',
}


def patch_upcut(up_bytes, fan_up_bytes, log=None, dumpdir=None):
    """-> (new upcut_local bytes, info). The plan pictures of the prison and the detention center, in Capcom's
    wording; only the tile data of each RGCN changes (its palette entry and every other entry are the fan's)."""
    log = log or (lambda s: None)
    tab, ftab = up_table(up_bytes), up_table(fan_up_bytes)
    for e, sha in sorted(UP_FAN_SHA256.items()):
        if hashlib.sha256(ftab[e]).hexdigest() != sha:
            raise PlanError("the fan's upcut_local entry %d is not the one this routine was proven on" % e)
        if hashlib.sha256(tab[e]).hexdigest() != sha:
            raise PlanError("upcut_local entry %d is not the fan's" % e)
    info = {}
    repl = patch_plans(up_bytes, fan_up_bytes, info)
    if dumpdir is not None and GALLERY_ENTRY not in repl:
        import gallery_art
        for e_ in (GALLERY_ENTRY, GALLERY_ENTRY + 1):
            if hashlib.sha256(ftab[e_]).hexdigest() != GALLERY_SHA256[e_] or hashlib.sha256(tab[e_]).hexdigest() != GALLERY_SHA256[e_]:
                raise PlanError("upcut_local entry %d is not the fan's" % e_)
        from nitro import nclr
        g114 = up_grid(tab[GALLERY_ENTRY])
        try:
            newgrid = gallery_art.picture(dumpdir, nclr(tab[GALLERY_ENTRY + 1]))
        except gallery_art.GalleryError as ex_:
            raise PlanError(str(ex_))
        repl[GALLERY_ENTRY] = up_set(tab[GALLERY_ENTRY], newgrid)
        info.setdefault('plans', {})[GALLERY_ENTRY] = dict(px=int((newgrid != g114).sum()), boxes=[(0, 0, UP_W - 1, UP_H - 1)])
    if BOARD_ENTRY not in repl:
        import board_temps
        from nitro import nclr
        for e_ in (BOARD_ENTRY, BOARD_ENTRY + 1):
            if hashlib.sha256(ftab[e_]).hexdigest() != BOARD_SHA256[e_] or hashlib.sha256(tab[e_]).hexdigest() != BOARD_SHA256[e_]:
                raise PlanError("upcut_local entry %d is not the fan's" % e_)
        g116 = up_grid(tab[BOARD_ENTRY])
        try:
            newboard = board_temps.patch(g116, nclr(tab[BOARD_ENTRY + 1]))
        except board_temps.BoardError as ex_:
            raise PlanError(str(ex_))
        repl[BOARD_ENTRY] = up_set(tab[BOARD_ENTRY], newboard)
        info.setdefault('plans', {})[BOARD_ENTRY] = dict(px=int((newboard != g116).sum()), boxes=[(100, 72, 169, 135)])
    out, info['stored'] = _commit(up_bytes, repl, 'upcut_local', UP_LARGER)
    log('plans (upcut_local): %s' % ', '.join('%d decoded %d stored %d (was %d)' % (
        e, len(repl[e]), info['stored'][e][1], info['stored'][e][0]) for e in sorted(repl)))
    return out, info


def apply_upcut_to_rom(rom, dumpdir, log=None, any_rom=False):
    """Re-letter the plan pictures inside a ROM image (after the last step that writes upcut_local).
    Returns (rom, changed)."""
    import title_logo
    from choice_strips import rom_file
    log = log or (lambda s: None)
    try:
        with open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'upcut_local.bin'), 'rb') as f:
            fan = f.read()
        new_up, info = patch_upcut(rom_file(rom, 'jpn/upcut_local.bin'), fan, log, dumpdir)
    except (PlanError, RoomNamesError, IOError) as e:
        if not any_rom:
            raise PlanError('%s (pass --any-rom to build without the Capcom wording on the plans)' % e)
        log('plans: NOT redrawn, --any-rom given (%s)' % e)
        return rom, False
    return title_logo.splice(rom, 'jpn/upcut_local.bin', new_up), True


# ---------------------------------------------------------------------------
# class 4: the Zodiac Hall and the contest venue's Fountain Room (idlocal 315, 318, 321, 324, 327)
# ---------------------------------------------------------------------------
# Capcom's captions: "Zodiac Hall - Fountain Room" (sce2_c0_01), "Zodiac Hall - Winter Wing" (sce2_c2_01),
# "Zodiac Hall - Autumn Wing" (sce2_c3_00), "Contest Venue - Fountain Room" (sce2_c0_03); its own plan of
# the hall (cut02_010_eng) letters the four rooms of the fan's "Palace" Summer / Winter / Spring / Autumn Wing
# and the lift "EL". The fan said Zodiac Art Gallery, Palace, Fountain Patio and EV.
CHECK3_4 = lambda x, y: 3 if (x + y) % 2 == 0 else 4        # the dark sectors' checkerboard
DIM = lambda g: Style(12, 3, 3, g)
LIT = Style(7, 3, 3, 5)


def patch_zodiac(idl, faces, info):
    """-> {RGCN entry: new bytes} for idlocal 315, 318, 321, 324 and 327."""
    big, strip, wedge = faces['big'], _strip_face(faces), faces['wedge']
    out = {}
    stats = info.setdefault('zodiac', {})

    # 315: the hall: four wings, the lift, the lit fountain room, and the strip
    B, old, sold = _pc(idl, 315)
    new = old
    for ink, box, newtext, style, ground in (
            (12, (28, 60, 44, 54), 'Wing', DIM(CHECK3_4), CHECK3_4), (7, (95, 125, 44, 54), 'Wing', LIT, 5),
            (7, (109, 142, 73, 83), 'Wing', LIT, 5), (12, (12, 42, 73, 83), 'Wing', DIM(CHECK3_4), CHECK3_4)):
        fp = footprint(new, ink, box, 'Palce', 3)
        new, _, _ = relabel(new, [(ink, box, 'Palce', 3)], ground, [(wedge, style, [(newtext, fp['l'], fp['base'])], (3,))], 'idlocal 315 wing')   # its ring may meet the line above's
    fp = footprint(new, 12, (70, 82, 41, 48), 'EV', (3, 4))
    new, _, _ = relabel(new, [(12, (70, 82, 41, 48), 'EV', (3, 4))], CHECK3_4, [(wedge, DIM(CHECK3_4), [('EL', fp['l'], fp['base'])])],
                        'idlocal 315 lift')
    fp = footprint(new, 9, (52, 100, 76, 86), 'Patio', 12)
    new, _, _ = relabel(new, [(9, (52, 100, 76, 86), 'Patio', 12)], 7, [(big, WHITE, [('Room', fp['l'], fp['base'])])],
                        'idlocal 315 fountain room')
    snew = strip_lines(sold, [((2, 13), 'Zodiac Art Gallery:', 'Zodiac Hall:'), ((14, 24), 'Fountain Patio', 'Fountain Room')],
                       strip, 'idlocal 315 strip')
    stats[315] = dict(px=B.write(0, old, new) + B.write(1, sold, snew))
    out[315] = B.result()

    # 318: the winter wing lit (its lit label and the strip), the fountain room's label on the band below
    B, old, sold = _pc(idl, 318)
    fp = footprint(old, 9, (40, 112, 50, 61), 'Winter Palace', 12)
    f2 = footprint(old, 7, (38, 115, 93, 104), 'Fountain Patio', 3)
    big.space = old_gap(old, 9, (40, 112, 50, 61), 'Winter Palace')
    new, _, _ = relabel(old, [(9, (40, 112, 50, 61), 'Winter Palace', 12)], 7,
                        [(big, WHITE, [('Winter Wing', centred(big, 'Winter Wing', fp['l'], fp['r']), fp['base'])])],
                        'idlocal 318 winter wing')      # centred in the lit box as the fan's 'Winter Palace' was (both centres are 75.5)
    big.space = old_gap(old, 7, (38, 115, 93, 104), 'Fountain Patio')
    new, _, _ = relabel(new, [(7, (38, 115, 93, 104), 'Fountain Patio', 3)], 5,
                        [(big, LIT, [('Fountain Room', centred(big, 'Fountain Room', f2['l'], f2['r']), f2['base'])])], 'idlocal 318 fountain room')
    big.space = 5
    snew = strip_lines(sold, [((2, 13), 'Zodiac Art Gallery:', 'Zodiac Hall:'), ((14, 24), 'Winter Palace', 'Winter Wing')], strip,
                       'idlocal 318 strip')
    stats[318] = dict(px=B.write(0, old, new) + B.write(1, sold, snew))
    out[318] = B.result()

    # 321: the contest venue's fountain room, the four-wedge piece (as room_names left it): the dome's label and the strip
    B, old, sold = _pc(idl, 321)
    fp = footprint(old, 9, (52, 100, 75, 87), 'Patio', 12)
    new, _, _ = relabel(old, [(9, (52, 100, 75, 87), 'Patio', 12)], 7, [(big, WHITE, [('Room', fp['l'], fp['base'])])],
                        'idlocal 321 fountain room')
    fp = footprint(new, 12, (70, 82, 41, 48), 'EV', (3, 4))
    new, _, _ = relabel(new, [(12, (70, 82, 41, 48), 'EV', (3, 4))], CHECK3_4, [(wedge, DIM(CHECK3_4), [('EL', fp['l'], fp['base'])])],
                        'idlocal 321 lift')
    snew, x, z = strip_edit(sold, 'Contest Venue: Fountain Patio', 'Fountain Patio', 'Fountain Room', strip, 'idlocal 321 strip')
    stats[321] = dict(px=B.write(0, old, new) + B.write(1, sold, snew), strip=(x, z))
    out[321] = B.result()

    # 324 and 327: the label under the lit room
    for g in (324, 327):
        B, old, sold = _pc(idl, g)
        f2 = footprint(old, 7, (38, 115, 93, 104), 'Fountain Patio', 3)
        big.space = old_gap(old, 7, (38, 115, 93, 104), 'Fountain Patio')
        new, _, _ = relabel(old, [(7, (38, 115, 93, 104), 'Fountain Patio', 3)], 5,
                            [(big, LIT, [('Fountain Room', centred(big, 'Fountain Room', f2['l'], f2['r']), f2['base'])])],
                            'idlocal %d fountain room' % g)
        big.space = 5
        stats[g] = dict(px=B.write(0, old, new))
        out[g] = B.result()
    return out
# ---------------------------------------------------------------------------
# class 5: Gourd Lake Park (idlocal 282, 285)
# ---------------------------------------------------------------------------
# Capcom's captions: "Gourd Lake - Lakeside Stage" (sce0_c1_0c) and "Gourd Lake - Spectator Area" (sce0_c0_01); the
# fan said "Gourd Lake Park: Stage" and "Audience Area". The President's Plane and its Office (287/288) have no
# caption of Capcom's and stay; so does the turned 'Stage' of 288 (lettered at an angle that exists nowhere else).
def _two_lines(big, style, room, texts, pitch, what, x_of=None):
    """[(text, x, baseline)] for the lines in `texts`, each centred on the columns of the room, the block centred
    on its rows. `room` is a set of pixels (the room's interior)."""
    ix0, ix1 = _xs(room)
    iy0, iy1 = min(y for _, y in room), max(y for _, y in room)
    top = int(np.ceil((iy0 + iy1) / 2.0 - (8 + pitch * (len(texts) - 1)) / 2.0))
    return [(t, centred(big, t, ix0, ix1), top + 7 + i * pitch) for i, t in enumerate(texts)], (ix0, ix1, iy0, iy1)


def patch_gourd(idl, faces, info):
    """-> {RGCN entry: new bytes} for idlocal 282 and 285."""
    big, strip = faces['big'], _strip_face(faces)
    out = {}
    stats = info.setdefault('gourd', {})

    # 282: the stage lit, the audience area under it, and the strip
    B, old, sold = _pc(idl, 282)
    st = footprint(old, 9, (59, 93, 64, 74), 'Stage', 12)
    au = footprint(old, 7, (37, 115, 98, 107), 'Audience Area', 3)
    erased = old.copy()
    for (x, y) in st['E']:
        erased[y, x] = 7
    lit = interior(erased, (45, 55), 7)
    lines, box = _two_lines(big, WHITE, lit, ['Lakeside', 'Stage'], 11, 'idlocal 282')
    new = old.copy()
    for (x, y) in st['E']:
        new[y, x] = 7
    for (x, y) in au['E']:
        new[y, x] = 5
    ink = paint_checked(new, lines, big, WHITE, lit, 'idlocal 282 lit label')
    ink2 = paint_checked(new, [('Spectator Area', centred(big, 'Spectator Area', au['l'], au['r']), au['base'])], big, OLIVE5, None,
                         'idlocal 282 spectator area')
    snew, x, z = strip_edit(sold, 'Gourd Lake Park: Stage', 'Gourd Lake Park: Stage', 'Gourd Lake: Lakeside Stage', strip, 'idlocal 282 strip')
    stats[282] = dict(px=B.write(0, old, new) + B.write(1, sold, snew), strip=(x, z), lit=box, lines=lines)
    out[282] = B.result()

    # 285: the audience area lit, the stage above it (olive), and the two-line strip
    B, old, sold = _pc(idl, 285)
    au = footprint(old, 9, (37, 115, 64, 73), 'Audience Area', 12)
    st = footprint(old, 7, (58, 92, 20, 30), 'Stage', 3)
    new = old.copy()
    for (x, y) in au['E']:
        new[y, x] = 7
    for (x, y) in st['E']:
        new[y, x] = 5
    lit = interior(new, (50, 55), 7)
    ix0, ix1 = _xs(lit)
    iy0, iy1 = min(y for _, y in lit), max(y for _, y in lit)
    paint_checked(new, [('Spectator Area', centred(big, 'Spectator Area', au['l'], au['r']), au['base'])], big, WHITE, lit,
                  'idlocal 285 lit label')
    room = interior(new, (50, 8), 5)
    lines2, box2 = _two_lines(big, OLIVE5, room, ['Lakeside', 'Stage'], 11, 'idlocal 285 stage')
    paint_checked(new, lines2, big, OLIVE5, room, 'idlocal 285 stage')
    snew = strip_lines(sold, [((2, 13), 'Gourd Lake Park:', 'Gourd Lake:'), ((14, 24), 'Audience Area', 'Spectator Area')], strip,
                       'idlocal 285 strip')
    stats[285] = dict(px=B.write(0, old, new) + B.write(1, sold, snew), lit=(ix0, ix1, iy0, iy1), stage=box2, lines2=lines2)
    out[285] = B.result()
    return out
# ---------------------------------------------------------------------------
# class 6: the Zodiac Hall plan's sprite labels (jpn/cutobj_local.bin entry 12)
# ---------------------------------------------------------------------------
# Cell 1 (and 4 to 7, the same tile in five palette banks) is the pink cloud that says "Autumn / Palace"; Capcom's
# cut02_010_eng says Autumn Wing. The letters are the plan face (5 x 7, ink 15, ring 13, corners 10, the cloud's fill 12):
# every letter of the old label is the plan face's own (proven letter for letter by build time), W, i and g come from
# the fan's other plan labels. "Secur. / Room" and "Rec. / Booth" (cells 2, 3) stay: Capcom's Security / Reception are
# wider than the 37 px sprites.
SPRITE12 = dict(entry=12, cell=1, sha='a9ed86d0e3bc2c8f20f13ee863bdfd4f57319ce71a379599048cbbf592a9ded0',
                old=(15, (12, 48, 35, 46), 'Palace'), new='Wing', style=(15, 13, 10, 12), clones=(4, 5, 6, 7))


def patch_sprite12(co_bytes, fan_up_bytes, info=None):
    """-> new jpn/cutobj_local.bin bytes: 'Palace' on the Autumn cloud (entry 12) becomes 'Wing'."""
    spec = SPRITE12
    co = Idlocal(co_bytes)
    e = spec['entry']
    blob = co.blob(e)
    if hashlib.sha256(blob).hexdigest() != spec['sha']:
        raise PlanError("cutobj_local entry %d is not the fan's" % e)
    o = struct.unpack_from('<3I', blob, 0)
    B = Bundle(blob[o[0]:o[1]], blob[o[2]:])
    old, _ = B.grid(spec['cell'])
    ink, box, text = spec['old']
    face = plan_faces(fan_up_bytes)
    # the old label must be spelled in the plan face, letter for letter
    sf = Face(4)
    harvest(sf, old, (11, 46, 25, 34), ink, 'Autumn', 'cutobj_local 12 Autumn')
    harvest(sf, old, box, ink, text, 'cutobj_local 12 ' + text)
    for ch, (bits, top, adv) in sf.g.items():
        if face.g[ch][:2] != (bits, top):
            raise PlanError('cutobj_local 12: the sprite letter %r is not the plan face letter' % ch)
    fp = footprint(old, ink, box, text, (13, 10))
    new = old.copy()
    for (x, y) in fp['E']:
        new[y, x] = spec['style'][3]
    x = centred(face, spec['new'], fp['l'], fp['r'])
    m, _ = layout(face, spec['new'], x, fp['base'])
    paint_ink(new, m, Style(*spec['style']), None, 'cutobj_local 12 label')
    n = B.write(spec['cell'], old, new)
    # the five states draw one tile bank in five palettes: every state must now show the same new label
    for k in spec['clones']:
        g1, _ = B.grid(spec['cell'], True)
        gk, _ = B.grid(k, True)
        if not (g1 == gk).all():
            raise PlanError('cutobj_local 12: cell %d does not show the same picture as cell %d' % (k, spec['cell']))
    if info is not None:
        info['sprite12'] = dict(px=n, label=(x, x + text_width(face, spec['new']) - 1, fp['base']))
    nb = blob[:o[2]] + B.result()
    if len(nb) != len(blob):
        raise PlanError('cutobj_local entry %d changed size' % e)
    out = rebuild(co_bytes, {e: nb}, lz=(e,))
    back = Idlocal(out)
    if back.blob(e) != nb:
        raise PlanError('cutobj_local entry %d does not round-trip' % e)
    ents, fents = _extent_of(out, e), _extent_of(co_bytes, e)
    if ents > fents:
        raise PlanError("cutobj_local entry %d would be stored in %d bytes, over the fan's %d" % (e, ents, fents))
    for i in range(back.n):
        if i != e and back.blob(i) != co.blob(i):
            raise PlanError('cutobj_local entry %d changed and should not have' % i)
    return out


def _extent_of(container_bytes, e):
    """Stored bytes of entry e of an idlocal-style container."""
    idl = Idlocal(container_bytes)
    order = sorted(range(idl.n), key=lambda i: idl.ents[i][0])
    k = order.index(e)
    return (idl.ents[order[k + 1]][0] if k + 1 < idl.n else len(container_bytes)) - idl.ents[e][0]


# ---------------------------------------------------------------------------
# what tools/plan_detect.py looks for: (face, picture file, RGCN entry, cell, box, ink, tokens)
# cut from the fan's ('fan') or the retail Japanese ('jp') idlocal, and the words made of them
# ---------------------------------------------------------------------------
DETECT_SOURCES = [
    ('jp', 'jp', 349, 0, (50, 100, 45, 57), 9, ['執', '務', '室']),
    ('jp', 'jp', 349, 0, (58, 91, 62, 70), 9, ['1', '2', '0', '2', '号']),
    ('jp', 'jp', 349, 0, (58, 92, 90, 100), 3, ['廊', '下']),
    # the fan's big face: every label that spells one of the old words (the fan squeezed some by a pixel)
    ('big', 'fan', 291, 0, (92, 130, 83, 91), 7, list('Hallway')),
    ('big', 'fan', 294, 0, (60, 94, 78, 86), 9, list('Hallway')),
    ('big', 'fan', 294, 0, (63, 89, 55, 62), 7, list('Block')),
    ('big', 'fan', 300, 0, (44, 76, 40, 48), 7, list('roomA')),
    ('big', 'fan', 306, 0, (42, 74, 54, 61), 9, list('roomA')),
    ('big', 'fan', 309, 0, (74, 110, 65, 75), 9, list('Special')),
    ('big', 'fan', 312, 0, (75, 107, 54, 61), 9, list('Court-')),
    ('big', 'fan', 312, 0, (75, 98, 65, 73), 9, list('yard')),
    # the strip face: the old names as the strips spell them
    ('strip', 'fan', 294, 1, None, 4, list('DetentionCenter:Hallway')),
    ('strip', 'fan', 306, 1, None, 4, list('Prison:WorkroomA')),
    ('strip', 'fan', 309, 1, None, 4, list('Prison:SpecialCell')),
    ('strip', 'fan', 312, 1, None, 4, list('Prison:Courtyard')),
    # the Zodiac Hall and the Fountain Room
    ('wedge', 'fan', 315, 0, (95, 125, 44, 54), 7, ['Pa', 'l', 'a', 'c', 'e']),
    ('wedge', 'fan', 315, 0, (70, 82, 41, 48), 12, ['E', 'V']),
    ('big', 'fan', 315, 0, (52, 100, 76, 86), 9, list('Patio')),
    ('big', 'fan', 318, 0, (40, 112, 50, 61), 9, list('WinterPalace')),
    ('big', 'fan', 324, 0, (38, 115, 93, 104), 7, list('FountainPatio')),
    ('strip', 'fan', 315, 1, (0, 95, 2, 13), 4, list('ZodiacArtGallery:')),
    ('strip', 'fan', 315, 1, (0, 95, 14, 24), 4, list('FountainPatio')),
    ('strip', 'fan', 318, 1, (0, 95, 14, 24), 4, list('WinterPalace')),
    # Gourd Lake Park: the fan's Audience Area and Park
    ('big', 'fan', 285, 0, (37, 115, 64, 73), 9, list('AudienceArea')),
    ('strip', 'fan', 282, 1, None, 4, list('GourdLakePark:Stage')),
    ('strip', 'fan', 285, 1, (0, 95, 14, 24), 4, list('AudienceArea')),
    # the plan face of upcut_local (box x0 x1 y0 y1, ink 1), from the fan's file
    ('plan', 'fanup', 102, None, (55, 90, 52, 62), 15, list('Palace')),
    ('plan', 'fanup', 102, None, (112, 144, 87, 97), 15, list('Patio')),
    ('plan', 'fanup', 102, None, (120, 136, 46, 56), 15, list('EV')),
    ('plan', 'fanup', 102, None, (106, 149, 177, 187), 15, list('Gardens')),
    ('plan', 'fanup', 36, None, (10, 70, 5, 16), 1, list('PrisonMap')),
    ('plan', 'fanup', 36, None, (85, 146, 27, 38), 1, list('WorkroomA')),
    ('plan', 'fanup', 36, None, (83, 121, 114, 124), 1, list('Hallway')),
    ('plan', 'fanup', 36, None, (208, 246, 94, 106), 1, list('Special')),
    ('plan', 'fanup', 40, None, (79, 117, 26, 37), 1, list('Offices')),
    ('plan', 'fanup', 40, None, (156, 207, 61, 71), 1, list('Courtyard')),
    ('plan', 'fanup', 40, None, (110, 172, 120, 131), 1, list('Passageway')),
]
# a Japanese glyph is a word of its own (the retail label spaces them 8 px apart); the digits of the
# retail "1202" are the very shapes the new label uses and are not searched for
DETECT_WORDS = [('jp', g, [g]) for g in ('執', '務', '室', '号', '廊', '下')] + [
    ('big', 'Hallway', list('Hallway')), ('big', 'Block', list('Block')), ('big', 'room', list('room')), ('big', 'Special', list('Special')),
    ('big', 'Court-', list('Court-')), ('big', 'yard', list('yard')),
    ('strip', 'Hallway', list('Hallway')), ('strip', 'Workroom', list('Workroom')),
    ('strip', 'Special', list('Special')), ('strip', 'Courtyard', list('Courtyard')),
    ('wedge', 'Palace', ['Pa', 'l', 'a', 'c', 'e']), ('wedge', 'EV', ['E', 'V']), ('big', 'Patio', list('Patio')),
    ('big', 'Palace', list('Palace')), ('strip', 'Gallery', list('Gallery')), ('strip', 'Patio', list('Patio')),
    ('strip', 'Palace', list('Palace')),
    ('big', 'Audience', list('Audience')), ('strip', 'Audience', list('Audience')), ('strip', 'Park', list('Park')),
    ('plan', 'Palace', list('Palace')), ('plan', 'Patio', list('Patio')), ('plan', 'EV', list('EV')), ('plan', 'Gardens', list('Gardens')),
    ('plan', 'Map', list('Map')), ('plan', 'Workroom', list('Workroom')), ('plan', 'Hallway', list('Hallway')),
    ('plan', 'Special', list('Special')), ('plan', 'Offices', list('Offices')), ('plan', 'Courtyard', list('Courtyard')),
    ('plan', 'Passageway', list('Passageway')),
]


# A word of the new wording that contains a run of the old words' letters: the 'Special' template (S p e c i a l, the old
# 309 label) fits the first seven letters of Gourd Lake's new 'Spectator Area' (S p e c t a t, i and l against t) on the
# piece 282, the piece 285 and its strip. These three hits are the new label, not the old one (plan_detect lists them).
DETECT_IGNORE = {('idlocal 282 c0', 'Special'), ('idlocal 285 c0', 'Special'), ('idlocal 285 c1', 'Special')}


# ---------------------------------------------------------------------------
# the patch over a whole idlocal container
# ---------------------------------------------------------------------------
# decoded sha256 of the fan's entries this module reads letters from or rewrites
FAN_SHA256 = {
    281: '216906eaaf31cb16692ef9473fb0b1c04f9abf7266a5806d7453555ddf1d59b4',
    282: '180a8ad8580b2d64ae2499e5a833fd3884a99274039409c2e7fdbe8c572aad31',
    284: 'dd0c04c0d6ee9b21e766b98416c69e46c4267aa26e43e4ed47570285c331ffea',
    285: 'd398aa62c281f01c8f72bbcfa798048cb8ceee1e7d1a19ad76e7b4909509722b',
    287: '216906eaaf31cb16692ef9473fb0b1c04f9abf7266a5806d7453555ddf1d59b4',
    288: 'af747fa048447ead1f9c68121dbe9d93623f2ec9302e4df11479f61116dd429f',
    290: 'dd0c04c0d6ee9b21e766b98416c69e46c4267aa26e43e4ed47570285c331ffea',
    291: 'bc2b2aaa6fd413a6b34ff0f1be489908beff06b71927b9dcb400dd337204e878',
    293: '44b12d55582979f0dd5e103f09329ef81192316112f3b53e09ceab47eb928c7e',
    294: '8edc4a51ca4e00be2d8c9bfaf7cbf3a94565f54004bc82498c4aa527c077a09c',
    296: '44b12d55582979f0dd5e103f09329ef81192316112f3b53e09ceab47eb928c7e',
    297: '30878dd9d5d4aca40ef347f83e183aecc70fd58229853dd928874419577b931c',
    299: '38cebe376873a9b31ef6556b3e4b7d99ff67dca1315e7d928f0b1868bb59db6c',
    300: 'dde364190d6cc10313e56520078339ab0090bc89f50727bad6c74e67b7f3a2d6',
    302: '38cebe376873a9b31ef6556b3e4b7d99ff67dca1315e7d928f0b1868bb59db6c',
    303: 'ffe27d3cbccf82f3b1ceb68823f5ae61e245985cc9ac7d745f6482f33dfb0d88',
    305: 'ffbe460fe4221b78df60a3caceb6de8688670a9097f5380adc898b4da7f2fd0e',
    306: '46496d74c57349bf5f9194460e3179cbea944428ff729484328f9d38ec7ac0a8',
    308: '62f472176821952c13dfdab538301a54371645ffdd6dbfe7912177d6c88b9d8f',
    309: 'adb920dfdbd0a7caaa7c8d47373e6f447ae6a238794507f51e6401219e40041b',
    311: '09ece0e48fbfaec2c4df3001656d7772d5a4d2906bdbc4d757ed6e2b5fc43ab3',
    312: '07d61c7b3844fc51655c9797d28f5dc0caf32213ee7d9c3404649ec790a25522',
    314: 'a78ac800d9d6e7c6fc88b48938a3f21a2ee6fc82d6d798040eee8908b361faa2',
    315: 'd9d578002929e55927de255da5f0f54d945718894b484f96f34ef0ebb72c51a6',
    317: 'b8d1bfaad3678801514bb2080c12fda8831049f73fd44e38c26bb0844cfe2d8e',
    318: '02ee437d8df1c6b30b703dff791dd15e1a68270f1718e7a8eb2a8c0478fde11f',
    320: '3202ec0db83ea97761786e857402430d709f8d40d2de5ad6e43fc4c3b1e2827a',
    321: 'c407c9c43aa123d0f97fc530bc539ef3e773b0663dfe192e7d83e0749d4052c1',
    323: 'e02e89b25221e782b914c4c1ad75c0eba01960ef26e15c15d8f72dc0d9931258',
    324: 'e13ef2756a92c7b7633d825b66942c706fc32c24f83b2be72dee96f22beeca9d',
    326: 'e02e89b25221e782b914c4c1ad75c0eba01960ef26e15c15d8f72dc0d9931258',
    327: '93dcf394c43643335a6ca116dc9d0535bdbe1e1b833b06449e52bcced719d6bc',
    330: 'dc15030240db842edc366b9391401c5b53c21a9abb6da6d9f5052b5da437b84e',
    331: '8099ead468231f7ef30229397e79d337d38332290a01e27cf0fc8ca6f974b197',
    346: '2eca51d59dfb74744ef8f911cbf8b27b9491f6a4cd0cad1d329935b30c6ff1b5',
    348: '0ad309e8f5f5b264e87002599384bc5bbba7b48aede0bea473170b02f61f7958',
    349: 'c26af728e2e4fc8072864c8084f0eedaeebc2091e601078ce6eec62cb8bc019d',
    351: 'd2e63bb7a426f4b4dab5eb6825d0b23e7c1c37fa5f244eed96db66b0773b499a',
    352: 'bbf19f3e3b406672ee4f4f0bbb3de4cfb8b6d9f76f7e0370fad0437193d43caf',
    354: 'dc15030240db842edc366b9391401c5b53c21a9abb6da6d9f5052b5da437b84e',
}

# decoded sha256 of idlocal 321, 324 and 327 as tools/room_names.py leaves them (the contest venue pieces the Zodiac class re-letters)
ROOM_NAMES_SHA256 = {
    321: 'd20067397bb730e343bec503bc107b953efcbcff123693bf278ccc4bb6bc0c32',
    324: 'b21b5f5709d5cd91335fdd3567f977a471d69d3f15c3673e172506e88026bdf7',
    327: 'ca2b16c42682597bebe21ccf97040ba2ffd8544ab62bb117bc84773373cecc8a',
}

# the entries each picture class rewrites (idlocal RGCN numbers); bufcheck check (p) reads this table
CLASS_ENTRIES = {'1202': (349,), 'prison': (291, 294, 297, 300, 303, 306, 309, 312), 'zodiac': (315, 318, 321, 324, 327), 'gourd': (282, 285)}   # 309 only with LARGER
ACTIVE = ('1202', 'prison', 'zodiac', 'gourd', 'sprite')
# Entries that may be stored in MORE bytes than the fan's entry, up to the literal-only form of their decoded
# size (the bound idlocal 172 and the 119 redrawn strips already ship under). The decoded picture goes into an
# exact-size buffer; the stored slot is only read into a temporary buffer of its own size that is freed straight
# after, so a bigger slot costs transient heap and nothing else (bufcheck bounds the slot, not the decodable prefix). 309 (Special Cell to Maximum Security,
# 1,268 stored against the fan's 1,088) is listed: without it the piece would say Hallway and Special Cell beside
# pieces that say Corridor and a script that says "Prison - Maximum Security". The same switch would draw the
# rest of what does not fit (303's room label, the titles of the plans 36 and 78); bufcheck.PLAN_LARGER mirrors it.
LARGER = (282, 285, 303, 309)
# The same for the plan pictures of jpn/upcut_local.bin: entries 36, 78 (the prison plan: title Prison Layout, the Maximum Security
# room) and 48 (Connecting Corridor, Main Prison) are stored bigger than the fan's entry, decoded size identical. A trace of the
# loaders shows these entries stream through the file system's decompressor into a fixed 0x2F000 block that sees only the
# decoded size (49,200), the stored bytes pass through a 0x200 window; bufcheck.PLAN_UP_LARGER mirrors this list.
UP_LARGER = (36, 48, 78)


def literal_bound(size):
    return size + (size + 7) // 8 + 4


def _content(idl, e):
    b = idl.blob(e)
    size = idl.ents[e][1]
    return b if size & 0x80000000 else b[:size]


def _commit(container_bytes, repl, what, larger=None):
    """The container with `repl` ({entry: decoded bytes}) stored as real LZ11 streams in place. Raises unless
    every replaced entry decodes back to what was given at the fan's size, fits in the stored bytes it had (or
    the literal-only bound for the entries in LARGER), and nothing else changed. -> (bytes, {entry: (was, now)})."""
    idl = Idlocal(container_bytes)
    out = rebuild(container_bytes, repl, lz=tuple(sorted(repl)))
    back = Idlocal(out)
    order = sorted(range(idl.n), key=lambda i: idl.ents[i][0])
    border = sorted(range(back.n), key=lambda i: back.ents[i][0])
    stored = {}
    for e in sorted(repl):
        if back.blob(e) != repl[e] or len(back.blob(e)) != len(idl.blob(e)):
            raise PlanError('%s entry %d does not round-trip or changed size' % (what, e))
        k, kb = order.index(e), border.index(e)
        was = (idl.ents[order[k + 1]][0] if k + 1 < idl.n else len(container_bytes)) - idl.ents[e][0]
        now = (back.ents[border[kb + 1]][0] if kb + 1 < back.n else len(out)) - back.ents[e][0]
        stored[e] = (was, now)
        bound = literal_bound(len(repl[e])) if e in (LARGER if larger is None else larger) else was
        if now > bound:
            raise PlanError("%s entry %d would be stored in %d bytes, over its bound %d (the fan's entry holds %d)"
                            % (what, e, now, bound, was))
    for e in range(idl.n):
        if e not in repl and _content(back, e) != _content(idl, e):
            raise PlanError('%s entry %d changed and should not have' % (what, e))
    return out, stored


def patch_idlocal(idl_bytes, fan_idl_bytes, classes=ACTIVE, log=None):
    """-> (new idlocal bytes, info). Letters come from the fan's own idlocal; the entries
    rewritten are read from `idl_bytes` (the container as the build holds it) and must be the
    fan's. Raises PlanError on anything the routine was not proven on."""
    log = log or (lambda s: None)
    idl, fan = Idlocal(idl_bytes), Idlocal(fan_idl_bytes)
    for e, sha in sorted(FAN_SHA256.items()):
        if sha is None:
            continue
        have = hashlib.sha256(fan.blob(e)).hexdigest()
        if have != sha:
            raise PlanError('the fan\'s idlocal entry %d has sha256 %s..., not the one this routine was proven on' % (e, have[:12]))
    faces = build_faces(fan)
    info = {}
    repl = {}
    if '1202' in classes:
        for e in (349, 351):
            if hashlib.sha256(idl.blob(e)).hexdigest() != FAN_SHA256[e]:
                raise PlanError('idlocal entry %d is not the fan\'s' % e)
        repl[349] = patch_1202(idl, faces, info)
    if 'prison' in classes:
        for g in CLASS_ENTRIES['prison']:
            for e in (g, RECN_OF[g]):
                if idl.blob(e) != fan.blob(e):
                    raise PlanError("idlocal entry %d is not the fan's" % e)
        repl.update(patch_prison(idl, faces, info))
    if 'zodiac' in classes:
        for g in (315, 318):
            for e in (g, RECN_OF[g]):
                if idl.blob(e) != fan.blob(e):
                    raise PlanError("idlocal entry %d is not the fan's" % e)
        for g in (321, 324, 327):       # the contest venue pieces are lettered over what tools/room_names.py wrote: that must be it
            if hashlib.sha256(idl.blob(g)).hexdigest() != ROOM_NAMES_SHA256[g]:
                raise PlanError('idlocal entry %d is not what tools/room_names.py writes' % g)
            if idl.blob(RECN_OF[g]) != fan.blob(RECN_OF[g]):
                raise PlanError("idlocal entry %d is not the fan's" % RECN_OF[g])
        repl.update(patch_zodiac(idl, faces, info))
    if 'gourd' in classes:
        for g in CLASS_ENTRIES['gourd']:
            for e in (g, RECN_OF[g]):
                if idl.blob(e) != fan.blob(e):
                    raise PlanError("idlocal entry %d is not the fan's" % e)
        repl.update(patch_gourd(idl, faces, info))
    if not repl:
        return idl_bytes, info
    out, info['stored'] = _commit(idl_bytes, repl, 'idlocal')
    log('map pieces and plans (idlocal): %s' % ', '.join('%d decoded %d stored %d (was %d)' % (
        e, len(repl[e]), info['stored'][e][1], info['stored'][e][0]) for e in sorted(repl)))
    return out, info


def apply_to_rom(rom, dumpdir, log=None, any_rom=False, classes=ACTIVE):
    """Re-letter the pictures inside a ROM image. Returns (rom, changed)."""
    import title_logo
    from choice_strips import rom_file
    log = log or (lambda s: None)
    fan_path = os.path.join(dumpdir, 'ds_fan', 'jpn', 'idlocal.bin')
    try:
        with open(fan_path, 'rb') as f:
            fan = f.read()
        new_id, info = patch_idlocal(rom_file(rom, 'jpn/idlocal.bin'), fan, classes, log)
    except (PlanError, RoomNamesError, IOError) as e:
        if not any_rom:
            raise PlanError('%s (pass --any-rom to build without the Capcom wording on the map pieces)' % e)
        log('map pieces and plans: NOT redrawn, --any-rom given (%s)' % e)
        return rom, False
    rom = title_logo.splice(rom, 'jpn/idlocal.bin', new_id)
    if 'sprite' in classes:
        try:
            with open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'upcut_local.bin'), 'rb') as f:
                fan_up = f.read()
            new_co = patch_sprite12(rom_file(rom, 'jpn/cutobj_local.bin'), fan_up)
        except (PlanError, RoomNamesError, IOError) as e:
            if not any_rom:
                raise PlanError('%s (pass --any-rom to build without the Capcom wording on the map pieces)' % e)
            log('Zodiac Hall plan sprite: NOT redrawn, --any-rom given (%s)' % e)
            return rom, True
        rom = title_logo.splice(rom, 'jpn/cutobj_local.bin', new_co)
        log('Zodiac Hall plan sprite (cutobj_local 12): Autumn Palace -> Autumn Wing')
    return rom, True
