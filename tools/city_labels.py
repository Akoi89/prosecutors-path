# -*- coding: utf-8 -*-
"""Capcom's wording on the labels of the city map and on the room label of the cross-section pictures.

The fan lettered the city map (jpn/upcut_local.bin 264 and 280) with names of its own: "Earl Bright City
Hall", "Dawn Waste Center", "Twilight Station", "Sunset Ave", "Dawning St", "Dusk Waste Management", "Prime
Mall", "Rising Sun Park" and, on 280, "Sunshine Warehouse". Capcom's English map (cut04_010_eng) names the same places "Sunrise Hall",
"Daybreak Dump", "Sunset Station", "Dusk Street", "Dawn Street", "Sundown Sanitation Plant", "Day's End Mall" and
"Mornington Park", and on its second map (cut04_03e_eng, the DS map 280) "Sunshine Depot" for the fan's "Sunshine
Warehouse"; Capcom's script says "The Sundown Sanitation Plant." The cross-section pictures
(jpn/upcut_local.bin 244, 246, 278) name the room on the 50th floor "P.I.C. Meeting Room"; Capcom's picture
(cut04_03a_eng) calls it "Committee Chamber" (its tag reads "50th FL -"), and the place strip jpn/idlocal.bin 328
reads "Bigg Building: Committee Chamber" in the fan's strip face.

At build time, from the fan's own picture and Capcom's own textures (extracted by tools/bigg_ground.py):
  * each old label (the ink of the fan's small map face, its white halo and soft corners: one pass of growth
    of the ink) is erased: the ground under it comes from Capcom's map, as for the tower's label
    (tools/bigg_ground.py), and a visible pixel that depends on a Capcom pixel that no language shows takes the
    value the picture itself has on both sides of it in its row or column, if it has one;
  * the new text is set in the same face, centred where the old label was, on the same baselines (a label
    with another number of lines is centred on the old block), ink, one pixel halo and soft corners as the
    fan has them; the vertical road name is the face turned a quarter clockwise;
  * the cross-section room label sits on a flat band: the old text and its halo are erased to the band's
    colour and the new text is centred on the old text's centre; "50F" stays;
  * the strip's tail is re-set in the strip face, with a b and an h that are the face's own letters
    rearranged (p turned over, n with the stem of l);
  * the highlight patches the game lays over the map (jpn/cutobj_local.bin 18) get the same labels
    (tools/city_patches.py).
Every old label is counted and measured before it is touched (ink pixels and box), every changed pixel must
lie in an erase mask or in a new label, and no new label may touch lettering that stays.
"""
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import room_names as rn
import bigg_ground as bgd
import bigg_building as bb
import input_hashes as ih
from room_names import ring_of, ink_mask, layout


class CityError(ValueError):
    pass


INK, HALO = 0, 28

# One entry per label of the fan's map: the window its ink is searched in (x0, x1, y0, y1), its ink pixels and ink box
# (x0, x1, y0, y1) as the fan has them, the baselines of its lines (rows of the face: a line's letters stand on it; None for
# the vertical road name), Capcom's lines, and the maps it is on.
MAP_LABELS = [
    dict(name='city hall', old='Earl Bright / City Hall', window=(130, 192, 28, 52), ink=207, box=(135, 188, 32, 48),
         base=(38, 48), new=['Sunrise Hall'], maps=(264, 280)),
    dict(name='waste center', old='Dawn Waste / Center', window=(183, 243, 56, 78), ink=192, box=(186, 240, 59, 75),
         base=(65, 75), new=['Daybreak', 'Dump'], maps=(264, 280)),
    dict(name='station', old='Twilight / Station', window=(26, 66, 58, 82), ink=161, box=(29, 63, 62, 79),
         base=(69, 79), new=['Sunset', 'Station'], maps=(264, 280)),
    dict(name='dawning', old='Dawning St', window=(3, 58, 105, 120), ink=115, box=(5, 56, 109, 116),
         base=(115,), new=['Dawn Street'], maps=(264, 280)),
    dict(name='waste mgmt', old='Dusk Waste / Management', window=(0, 63, 135, 160), ink=253, box=(3, 60, 139, 156),
         base=(145, 155), new=['Sundown', 'Sanitation', 'Plant'], maps=(264, 280)),
    dict(name='prime mall', old='Prime / Mall', window=(85, 114, 140, 164), ink=102, box=(88, 111, 144, 160),
         base=(150, 160), new=["Day's End", 'Mall'], maps=(264, 280)),
    dict(name='park', old='Rising / Sun Park', window=(128, 176, 150, 174), ink=155, box=(132, 172, 154, 170),
         base=(160, 170), new=['Mornington', 'Park'], maps=(264, 280)),
    dict(name='sunset ave', old='Sunset Ave (vertical)', window=(70, 80, 15, 75), ink=113, box=(72, 78, 18, 72),
         base=None, new='Dusk Street', maps=(264, 280)),
    dict(name='warehouse', old='Sunshine / Warehouse', window=(198, 255, 88, 112), ink=208, box=(202, 252, 92, 108),
         base=(98, 108), new=['Sunshine', 'Depot'], maps=(280,)),
]
# lettering of the map that stays: (window, ink pixels, name, maps)
KEPT = [((205, 255, 24, 48), 169, 'Sunshine Harbor', (264, 280)), ((194, 243, 150, 174), 180, 'Sunshine Coliseum', (264, 280))]
MAP_ENTRIES = (264, 280)
CORNER_WHITE_SHARE = bb.CORNER_WHITE_SHARE
FAR_TOL = 0.5                   # a visible pixel may take at most this share of its footprint from Capcom pixels that no language shows
FAR_MAX = 60                    # and at most this many such pixels may be visible on one map (after the picture's own rows and columns bridged what they could)
DILATE = 1                      # the fan's label is its ink, a one pixel halo and soft corner pixels: exactly one pass of 3x3 growth of the ink


def _dilate(m, n):
    return bgd.dilate3(m, n)


def _old_ink(g, L):
    ink = ink_mask(g, INK, L['window'])
    xs = [p[0] for p in ink]
    ys = [p[1] for p in ink]
    box = (min(xs), max(xs), min(ys), max(ys)) if ink else None
    if len(ink) != L['ink'] or box != L['box']:
        raise CityError('%s: the old label has %d ink pixels in %r, expected %d in %r'
                        % (L['old'], len(ink), box, L['ink'], L['box']))
    return ink


def _label_mask(g, ink):
    """The old label's erase mask: the ink and the ring round it (DILATE pass of 3x3 growth); every pixel of its
    orthogonal ring must be the halo value, as the fan has it."""
    orth0, _d0 = ring_of(ink)
    bad = [q for q in orth0 if 0 <= q[1] < g.shape[0] and 0 <= q[0] < g.shape[1] and g[q[1], q[0]] != HALO]
    if bad:
        raise CityError("%d pixels of the old label's orthogonal ring are not the halo (first %s)" % (len(bad), bad[:3]))
    m = np.zeros(g.shape, bool)
    for (x, y) in ink:
        m[y, x] = True
    return _dilate(m, DILATE)


def new_label(face, L, ink_box):
    """The new label's ink pixels, one set per line, centred on the old label (horizontal: its ink columns' centre
    and the old baselines; vertical: the old ink's columns and its rows' centre).
    -> list of (text, pixels, (x0, x1))."""
    x0, x1, y0, y1 = ink_box
    out = []
    if L['base'] is None:                                           # the vertical label: the face turned a quarter clockwise
        text = L['new']
        pts, _ = layout(face, text, 0, 0)
        rot = set((-y, x) for x, y in pts)
        rx = [p[0] for p in rot]
        ry = [p[1] for p in rot]
        cy = (y0 + y1) / 2.0
        tx = x0 - min(rx)
        ty = int(round(cy - (min(ry) + max(ry)) / 2.0))
        shifted = set((x + tx, y + ty) for x, y in rot)
        xs = [p[0] for p in shifted]
        return [(text, shifted, (min(xs), max(xs)))]
    cx = (x0 + x1) / 2.0
    n = len(L['new'])
    mid = sum(L['base']) / float(len(L['base']))
    if n == len(L['base']):
        bases = list(L['base'])
    elif n == 1:
        bases = [int(mid) + (1 if len(L['base']) == 2 else 0)]
    elif n == 3 and len(L['base']) == 2:
        m = int(mid)
        bases = [m - 10, m, m + 10]
    else:
        raise CityError('%s: no rule for %d lines on %d old baselines' % (L['old'], n, len(L['base'])))
    for text, b in zip(L['new'], bases):
        w = rn.text_width(face, text)
        left = int(round(cx - (w - 1) / 2.0 - 0.01))
        pts, (a, z) = layout(face, text, left, b)
        out.append((text, pts, (a, z)))
    return out


def relabel_map(g, pal, entry, face, textures, info):
    """-> new index grid of a city map."""
    if g.shape != (192, 256):
        raise CityError('city map %d is %r, expected 192x256' % (entry, g.shape))
    labels = [L for L in MAP_LABELS if entry in L['maps']]
    masks, placed, label_px, painted = {}, {}, set(), []
    for L in labels:
        for ch in (L['new'] if isinstance(L['new'], str) else ''.join(L['new'])):
            if ch != ' ' and ch not in face:
                raise CityError("the face has no %r (for %r)" % (ch, L['new']))
        ink = _old_ink(g, L)
        masks[L['name']] = _label_mask(g, ink)
        lines = new_label(face, L, L['box'])
        placed[L['name']] = lines
        for text, pts, _ in lines:
            orth, diag = ring_of(pts)
            label_px |= pts | orth | diag
            painted.append(pts)
    mask = np.zeros(g.shape, bool)
    for m in masks.values():
        mask |= m
    # nothing of the old lettering may be left just outside the masks
    near = _dilate(mask, 2) & ~mask
    left = [(int(x), int(y)) for y, x in zip(*np.nonzero(near & ((g == INK) | (g == HALO))))]
    if left:
        raise CityError('city map %d: %d ink or halo pixels of old lettering lie just outside the erase masks (first %s)'
                        % (entry, len(left), left[:3]))
    # lettering that stays: it must not be touched and must not serve as ground for anything
    keep_px = np.zeros(g.shape, bool)
    for window, n, name, on in KEPT:
        if entry not in on:
            continue
        ink = ink_mask(g, INK, window)
        if len(ink) != n:
            raise CityError('%s: %d ink pixels, expected %d' % (name, len(ink), n))
        for (x, y) in ink:
            keep_px[y, x] = True
    tower = np.zeros(g.shape, bool)                                   # the tower's own label (tools/bigg_building.py)
    for y, x in zip(*np.nonzero(g[96:128, 70:130] == INK)):
        tower[96 + y, 70 + x] = True
    stays = _dilate(keep_px | tower, 3)
    for (x, y) in label_px:
        if 0 <= y < g.shape[0] and 0 <= x < g.shape[1] and stays[y, x] and not mask[y, x]:
            raise CityError('a new label touches lettering that stays at (%d, %d)' % (x, y))
    keep = mask.copy()
    for (x, y) in label_px:
        if 0 <= y < keep.shape[0] and 0 <= x < keep.shape[1]:
            keep[y, x] = False
    try:
        new, ginfo = bgd.derive(g, pal, mask, keep, None, textures, use_arch=False, ring_exclude=stays, bridge=True,
                                far_tol=FAR_TOL)
    except bgd.GroundError as e:
        raise CityError('city map %d: %s' % (entry, e))
    ginfo.pop('stage_ds', None)
    if ginfo['n_grown_touching'] > FAR_MAX:
        raise CityError('city map %d: %d visible pixels still depend on grown Capcom pixels (at most %d accepted)'
                        % (entry, ginfo['n_grown_touching'], FAR_MAX))
    ground_only = new.copy()                                          # the map without any label of the old or the new set
    for pts in painted:
        bb.paint_map_label(new, pts, pal, INK, HALO)
    changed = set((int(x), int(y)) for y, x in zip(*np.nonzero(new != g)))
    want = set((int(x), int(y)) for y, x in zip(*np.nonzero(mask)))
    stray = changed - want - label_px
    if stray:
        raise CityError('city map %d: %d pixels changed outside the erase masks and the new labels' % (entry, len(stray)))
    info[entry] = dict(labels={k: [(t, a, z) for t, _p, (a, z) in v] for k, v in placed.items()}, mask=int(mask.sum()),
                       changed=len(changed), ground=ginfo, ground_only=ground_only, pal=pal)
    return new


# ---------------------------------------------------------------------------
# the room label of the cross-section pictures (jpn/upcut_local.bin 244, 246, 278)
# ---------------------------------------------------------------------------
ROOM_OLD, ROOM_NEW = 'P.I.C. Meeting Room', 'Committee Chamber'
ROOM_STYLE = rn.Style(1, 6, 8, 3)          # ink 1, orthogonal halo 6, corner pixels 8, the band's own ground 3
# entry -> (window of the old text, its ink pixels, ink box, baseline); the "50F" tag at its left stays
ROOMS = {
    244: dict(window=(78, 178, 86, 102), ink=192, box=(83, 172, 91, 98), base=97),
    246: dict(window=(78, 178, 120, 136), ink=192, box=(83, 172, 125, 132), base=131),
    278: dict(window=(127, 227, 126, 142), ink=192, box=(131, 220, 131, 138), base=137),
}


def relabel_room(g, entry, face, info):
    """-> new index grid of a cross-section picture with Capcom's room name."""
    spec = ROOMS[entry]
    for ch in ROOM_NEW:
        if ch != ' ' and ch not in face:
            raise CityError("the face has no %r (for %r)" % (ch, ROOM_NEW))
    ink = ink_mask(g, 1, spec['window'])
    xs = [p[0] for p in ink]
    ys = [p[1] for p in ink]
    box = (min(xs), max(xs), min(ys), max(ys)) if ink else None
    if len(ink) != spec['ink'] or box != spec['box']:
        raise CityError('cross-section %d: the old room label has %d ink pixels in %r, expected %d in %r'
                        % (entry, len(ink), box, spec['ink'], spec['box']))
    orth, diag = ring_of(ink)
    bad = [q for q in orth if g[q[1], q[0]] != ROOM_STYLE.halo] + [q for q in diag if g[q[1], q[0]] != ROOM_STYLE.halo2]
    if bad:
        raise CityError('cross-section %d: %d ring pixels of the old room label are not its halo (first %s)' % (entry, len(bad), bad[:3]))
    cover = ink | orth | diag
    rect = [(x, y) for y in range(box[2] - 3, box[3] + 4) for x in range(box[0] - 3, box[1] + 4) if (x, y) not in cover]
    off = [(x, y, int(g[y, x])) for x, y in rect if g[y, x] != ROOM_STYLE.ground]
    if off:
        raise CityError('cross-section %d: the band under the old room label is not flat (%d pixels, first %s)' % (entry, len(off), off[:3]))
    new = g.copy()
    for (x, y) in cover:
        new[y, x] = ROOM_STYLE.ground
    w = rn.text_width(face, ROOM_NEW)
    left = int(round((box[0] + box[1]) / 2.0 - (w - 1) / 2.0 - 0.01))
    pts, (a, z) = layout(face, ROOM_NEW, left, spec['base'])
    rn.paint(new, pts, ROOM_STYLE)
    changed = set((int(x), int(y)) for y, x in zip(*np.nonzero(new != g)))
    o2, d2 = ring_of(pts)
    stray = changed - cover - (pts | o2 | d2)
    if stray:
        raise CityError('cross-section %d: %d pixels changed outside the old and the new label' % (entry, len(stray)))
    info[entry] = dict(old=(box[0], box[1]), new=(a, z), base=spec['base'], width_old=box[1] - box[0] + 1, width_new=z - a + 1)
    return new


# ---------------------------------------------------------------------------
# the place strip of the 50th floor (jpn/idlocal.bin 328)
# ---------------------------------------------------------------------------
STRIP_ENTRY, STRIP_PAIR = 328, 326
STRIP_NEW = 'Committee Chamber'
STRIP_TAIL = dict(first_x=67, last_x=138)                            # columns of the old tail "P.I.C. Meeting Rm." after the tower's name
STRIP_OLD_TAIL_INK = 177                                             # its ink pixels


def strip_face(face):
    """The strip face has no b and no h. Both are the face's own letters rearranged: b is its p turned upside down
    (which is also its d turned round), h is its n with the stem of the l carried up two rows."""
    for ch in 'pdn':
        if ch not in face:
            raise CityError("the strip face has no %r: no b or h can be built" % ch)
    p_bits, p_top, _ = face.g['p']
    d_bits, d_top, d_adv = face.g['d']
    n_bits, n_top, n_adv = face.g['n']
    b_bits = tuple(reversed(p_bits))
    if b_bits != tuple(r[::-1] for r in d_bits):
        raise CityError("the strip face's p turned over is not its d turned round: no b can be built")
    h_bits = ('1' + '0' * (len(n_bits[0]) - 1),) * (len(d_bits) - len(n_bits)) + tuple(n_bits)
    if len(h_bits) != len(d_bits) or h_bits[0][0] != '1' or n_bits[0][0] != '1':
        raise CityError("the strip face's n cannot be carried up into an h")
    face.g['b'] = (b_bits, d_top, d_adv)
    face.src['b'] = [('composite', "p turned upside down (= d turned round), strip face")]
    face.g['h'] = (h_bits, d_top, n_adv)
    face.src['h'] = [('composite', "n with the stem of l carried up two rows, strip face")]
    return face


def relabel_strip(B, face, info):
    """The tail of the 50th floor strip, "P.I.C. Meeting Rm.", becomes "Committee Chamber" (same x, same baseline,
    the strip face, its shadow rule). Returns bytes written (pixels)."""
    a0, _ = B.grid(1)
    box = (0, a0.shape[1] - 1, 0, 15)
    m = ink_mask(a0, bb.STRIP_INK, box)
    runs = rn.segment(m, box)
    colon = [i for i, r in enumerate(runs) if i >= 8 and r[1] == r[0] and len(r[4]) <= 4]
    if not colon:
        raise CityError('strip %d: no colon found' % STRIP_ENTRY)
    c = colon[0]
    tail = runs[c + 1:]
    tail_ink = sum(len(r[4]) for r in tail)
    if not tail or tail[0][0] != STRIP_TAIL['first_x'] or tail[-1][1] != STRIP_TAIL['last_x'] or tail_ink != STRIP_OLD_TAIL_INK:
        raise CityError('strip %d: the old tail is %d ink pixels from x %s to %s, expected %d from %d to %d' % (
            STRIP_ENTRY, tail_ink, tail[0][0] if tail else None, tail[-1][1] if tail else None, STRIP_OLD_TAIL_INK,
            STRIP_TAIL['first_x'], STRIP_TAIL['last_x']))
    base = bb.line_base(runs)
    for ch in STRIP_NEW:
        if ch != ' ' and ch not in face:
            raise CityError("the strip face has no %r" % ch)
    new = a0.copy()
    tx0 = tail[0][0]
    new[0:16, tx0:] = 0
    pts, (a, z) = layout(face, STRIP_NEW, tx0, base)
    if z + 2 > a0.shape[1] - 1:
        raise CityError('strip %d: the new tail ends at column %d of %d' % (STRIP_ENTRY, z, a0.shape[1]))
    rn.paint_strip(new, pts)
    n = B.write(1, a0, new)
    info[STRIP_ENTRY] = dict(old=(tx0, tail[-1][1]), new=(a, z), base=base, width_old=tail[-1][1] - tx0 + 1, width_new=z - a + 1, written=n)
    return n


# ---------------------------------------------------------------------------
# the ROM
# ---------------------------------------------------------------------------
def patch_upcut(upcut_bytes, fan_upcut_bytes, dumpdir, face, textures=None):
    """-> (new upcut_local bytes, info). Entries 264 and 280 (the city map) and 244, 246 and 278 (the room label)."""
    import gfx_views as gv
    from nitro import nclr
    from choice_strips import Idlocal, rebuild
    idl, fan = Idlocal(upcut_bytes), Idlocal(fan_upcut_bytes)
    if ih.GUARD_INPUTS:
        for e, shas in sorted(ih.CITY_UPCUT_SHA256.items()):
            if ih.sha(fan.blob(e)) != shas[0]:
                raise CityError("the fan's upcut_local entry %d is not the one this routine was proven on" % e)
            if ih.sha(idl.blob(e)) not in shas:
                raise CityError('upcut_local entry %d is not what the Bigg Building step leaves' % e)
    if textures is None:                       # map 264 is cut04_010, map 280 (the one with the depot) is cut04_03e
        textures = {264: bgd.load_textures(dumpdir, 1), 280: bgd.load_textures(dumpdir, 2)}
    elif not isinstance(textures, dict):
        textures = {e: textures for e in MAP_ENTRIES}
    info, repl = {}, {}
    for e in MAP_ENTRIES:
        pal = nclr(idl.blob(e + 1))
        pal = pal + [(255, 0, 255)] * (256 - len(pal))
        blob = idl.blob(e)
        g = gv.raw_grid(blob)
        new = relabel_map(g, pal, e, face, textures[e], info.setdefault('map', {}))
        repl[e], n = bb.raw_write(blob, g, new)
        info.setdefault('written', {})[e] = n
    for e in sorted(ROOMS):
        blob = idl.blob(e)
        g = gv.raw_grid(blob)
        new = relabel_room(g, e, face, info.setdefault('room', {}))
        repl[e], n = bb.raw_write(blob, g, new)
        info.setdefault('written', {})[e] = n
    out = rebuild(upcut_bytes, repl, lz=tuple(sorted(repl)))
    back = Idlocal(out)
    info['stored'] = bb._stored_check(fan, fan_upcut_bytes, back, out, repl, 'upcut_local')
    for e in range(idl.n):
        if e not in repl and bb._content(back, e) != bb._content(idl, e):
            raise CityError('upcut_local entry %d changed and should not have' % e)
    return out, info


def patch_idlocal(idl_bytes, fan_idl_bytes):
    """-> (new idlocal bytes, info). Entry 328, the tail of the 50th floor strip."""
    from choice_strips import Idlocal, rebuild
    idl, fan = Idlocal(idl_bytes), Idlocal(fan_idl_bytes)
    if ih.GUARD_INPUTS:
        for e, shas in sorted(ih.CITY_IDLOCAL_SHA256.items()):
            if ih.sha(fan.blob(e)) != shas[0]:
                raise CityError("the fan's idlocal entry %d is not the one this routine was proven on" % e)
            if ih.sha(idl.blob(e)) not in shas:
                raise CityError('idlocal entry %d is not what the Bigg Building step leaves' % e)
    faces = bb.faces_for(rn.Source(fan))
    face = strip_face(faces['strip'])
    B = rn.Bundle(idl.blob(bb.PAIRS[STRIP_ENTRY]), idl.blob(STRIP_ENTRY))
    a0, _ = B.grid(1)
    box = (0, a0.shape[1] - 1, 0, 15)
    runs = rn.segment(ink_mask(a0, bb.STRIP_INK, box), box)
    face.space = runs[4][0] - runs[3][1] - 2             # the strip's own word space: between "Bigg" and "Building"
    info = {}
    relabel_strip(B, face, info)
    repl = {STRIP_ENTRY: B.result()}
    out = rebuild(idl_bytes, repl, lz=(STRIP_ENTRY,))
    back = Idlocal(out)
    info['stored'] = bb._stored_check(fan, fan_idl_bytes, back, out, repl, 'idlocal')
    for e in range(idl.n):
        if e != STRIP_ENTRY and bb._content(back, e) != bb._content(idl, e):
            raise CityError('idlocal entry %d changed and should not have' % e)
    info['face'] = {c: face.src[c] for c in 'bh'}
    return out, info


def apply_to_rom(rom, dumpdir, log=None, any_rom=False):
    """Capcom's labels on the city map and its highlight patches, the cross-section room label and the 50th floor
    strip: returns (rom, changed). Run after tools/bigg_building.py (it works on the pictures that step writes)."""
    import title_logo
    import city_patches as cp
    import marker_letters as ml
    import gfx_views as gv
    from choice_strips import Idlocal, rom_file
    log = log or (lambda s: None)
    try:
        face = bb.map_face_fixed()
        fan_up = open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'upcut_local.bin'), 'rb').read()
        fan_id = open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'idlocal.bin'), 'rb').read()
        new_up, uinfo = patch_upcut(rom_file(rom, 'jpn/upcut_local.bin'), fan_up, dumpdir, face)
        new_id, iinfo = patch_idlocal(rom_file(rom, 'jpn/idlocal.bin'), fan_id)
        fan_idl = Idlocal(fan_up)
        fan_maps = {e: gv.raw_grid(fan_idl.blob(e)) for e in MAP_ENTRIES}
        ground = {e: (uinfo['map'][e]['ground_only'], uinfo['map'][e]['pal']) for e in MAP_ENTRIES}
        new_co, cinfo, _canv = cp.patch_cutobj(rom_file(rom, 'jpn/cutobj_local.bin'), dumpdir, face, ground, fan_maps)
    except (CityError, bgd.GroundError, bb.BiggError, rn.RoomNamesError, cp.PatchError, ml.MarkerError) as e:
        if not any_rom:
            raise CityError('%s (pass --any-rom to build without the city labels)' % e)
        log('city labels: NOT redrawn, --any-rom given (%s)' % e)
        return rom, False
    for e in sorted(uinfo['stored']):
        log('city labels (upcut_local %d): written %d px, stored %d (was %d)' % (e, uinfo['written'][e], uinfo['stored'][e][0], uinfo['stored'][e][1]))
    log('city labels (idlocal %d): tail %s -> %s, stored %d (was %d)' % (
        STRIP_ENTRY, iinfo[STRIP_ENTRY]['old'], iinfo[STRIP_ENTRY]['new'], iinfo['stored'][STRIP_ENTRY][0], iinfo['stored'][STRIP_ENTRY][1]))
    log('city labels (cutobj_local %d, highlight patches): %d tile pixels, %d cells differ by %d pixels, stored %d (was %d)' % (
        cp.ENTRY, cinfo['written'], cinfo['cells'], cinfo['cell_pixels'], cinfo['stored'][cp.ENTRY][0], cinfo['stored'][cp.ENTRY][1]))
    rom = title_logo.splice(rom, 'jpn/upcut_local.bin', new_up)
    rom = title_logo.splice(rom, 'jpn/idlocal.bin', new_id)
    rom = title_logo.splice(rom, 'jpn/cutobj_local.bin', new_co)
    return rom, True
