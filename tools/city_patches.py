# -*- coding: utf-8 -*-
"""The highlight patches of the city map (jpn/cutobj_local.bin entry 18) with Capcom's wording.

When the player points at a place on the city map the game lays a patch over the map: the block in orange with its
label on top. The fan's patches carry the fan's names ("Dawn Waste Center", "Dusk Waste Management", "Sunshine Warehouse"
twice); the map under them now carries Capcom's ("Daybreak Dump", "Sundown Sanitation Plant", "Sunshine Depot",
tools/city_labels.py), and Capcom's
own script names the plant: "The Sundown Sanitation Plant." A patch must show the same label as the map under it,
pixel for pixel, so each patch gets the map's new label (the same layout) seen through the patch's rectangle.

The patch is the block's footprint on the map, recoloured (the orange fill, a darker outline, a light edge on
some sides) and transparent everywhere else; Capcom's own patch is another drawing, so the shape under the old
label is not Capcom's to give. It is inferred from the patch itself and from the map:
  1. which of the hidden pixels are block and which are transparent: the pixels of the patch's visible ring that
     look most like the hidden one on the map (the ground the map has there, colour and distance) vote;
  2. what index a hidden block or edge pixel has: the nearest visible pixel whose 5x5 neighbourhood of block /
     transparent is the same as its own (then 3x3), so that an outline stays an outline on the side it was on;
  3. old lettering that lies just outside the ring (a soft pixel between two letters) is erased with it.
The new label is the map's, clipped to the patch's rectangle, in the patch's own colours; its soft corners only
where there is ground under them (a patch is transparent where it has no block).
"""
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bigg_ground as bgd
import bigg_building as bb
import city_labels as cl
import marker_letters as ml
import input_hashes as ih
import gfx_views as gv
from choice_strips import Idlocal, rebuild, rom_file
from room_names import ring_of


class PatchError(ValueError):
    pass


ENTRY = 18
INK_IDX, HALO_IDX = 1, 15
CORNER_SHARE = cl.CORNER_WHITE_SHARE
VOTE_K, VOTE_LAMBDA = 9, 6.0       # hidden pixel: the 9 visible ring pixels closest in map colour and place vote, a pixel of distance counts 6 colour units squared
MAX_MISMATCH = 4                   # a hidden pixel's exemplar may differ in this weighted number of its 25 neighbours
MAX_PLAIN = 100                     # at most this many hidden pixels of a patch may have a worse exemplar
MASK_PASSES = 2                    # the fan's patch labels have soft pixels two pixels from the ink (inside a counter, between letters)
SPECK_REACH = 4                    # old lettering this near the ring but not in it (a soft pixel between two letters) goes too
# name, rectangle on the sheet (x, y, w, h), palette bank, the map label it carries, where the patch's own coordinates
# meet the map's (map = patch + offset), the map pictures it overlays
PATCHES = [
    dict(name='Dawn Waste Center', rect=(0, 0, 64, 64), bank=1, label='waste center', offset=(184, 32), maps=(264, 280)),
    dict(name='Dusk Waste Management', rect=(64, 0, 64, 32), bank=1, label='waste mgmt', offset=(-3, 136), maps=(264, 280)),
    dict(name='Sunshine Warehouse (grey)', rect=(128, 0, 64, 32), bank=2, label='warehouse', offset=(192, 80), maps=(280,)),
    dict(name='Sunshine Warehouse (orange)', rect=(128, 32, 64, 32), bank=1, label='warehouse', offset=(192, 80), maps=(280,)),
]
SHEET = (192, 256)                  # the part of the sheet that holds the patches (rows, columns)


def _dilate(m, n=1):
    return bgd.dilate3(m, n)


def _canvas(E):
    """The sheet's patch rows as one grid of combined palette indices (index + 16 * bank), 0 where nothing is drawn."""
    g = np.zeros(SHEET, np.int32)
    idx = E.idx[:SHEET[0], :SHEET[1]]
    bank = E.bank[:SHEET[0], :SHEET[1]]
    sel = idx >= 0
    g[sel] = idx[sel] + 16 * bank[sel]
    return g


def _regularise(C, mask, rect):
    """The hidden pixels' class (block / transparent) made one solid block: a 3x3 majority twice (only hidden
    pixels move), then only the largest block stays and a hole inside it is filled (hidden pixels only)."""
    C = C.copy()
    for _ in range(2):
        p = np.pad(C.astype(np.int32), 1)
        cnt = sum(p[1 + dy:1 + dy + C.shape[0], 1 + dx:1 + dx + C.shape[1]] for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        maj = cnt >= 5
        C = np.where(mask, maj, C)
    # components of the block (8-connected) inside the rectangle
    lab = np.zeros(C.shape, np.int32)
    comps = []
    for y, x in zip(*np.nonzero(C & rect)):
        if lab[y, x]:
            continue
        n = len(comps) + 1
        stack = [(y, x)]
        lab[y, x] = n
        cells = []
        while stack:
            cy, cx = stack.pop()
            cells.append((cy, cx))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = cy + dy, cx + dx
                    if 0 <= yy < C.shape[0] and 0 <= xx < C.shape[1] and C[yy, xx] and rect[yy, xx] and not lab[yy, xx]:
                        lab[yy, xx] = n
                        stack.append((yy, xx))
        comps.append(cells)
    if not comps:
        raise PatchError('the patch has no block')
    big = max(range(len(comps)), key=lambda i: len(comps[i]))
    for i, cells in enumerate(comps):
        if i != big:
            for (y, x) in cells:
                if mask[y, x]:
                    C[y, x] = False
    # holes: transparent pixels that the outside cannot reach (4-connected, through the rectangle)
    outside = np.zeros(C.shape, bool)
    stack = [(y, x) for y, x in zip(*np.nonzero(rect & ~C)) if y in (np.nonzero(rect)[0].min(), np.nonzero(rect)[0].max())
             or x in (np.nonzero(rect)[1].min(), np.nonzero(rect)[1].max())]
    for y, x in stack:
        outside[y, x] = True
    while stack:
        cy, cx = stack.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            yy, xx = cy + dy, cx + dx
            if 0 <= yy < C.shape[0] and 0 <= xx < C.shape[1] and rect[yy, xx] and not C[yy, xx] and not outside[yy, xx]:
                outside[yy, xx] = True
                stack.append((yy, xx))
    holes = rect & ~C & ~outside & mask
    C[holes] = True
    return C


def reconstruct(g0, rect, mask, D, info):
    """The ground under an old label. g0: combined index grid of the sheet, rect: the patch's rectangle, mask: the
    old label's erase mask, D: the map's colour at every sheet pixel of the patch (float). -> new grid (g0 with the
    mask filled)."""
    new = g0.copy()
    ring = rect & ~mask & _dilate(mask, 14)
    ry, rx = np.nonzero(ring)
    RF, RC = D[ry, rx], (g0[ry, rx] % 16 != 0)
    C = (g0 % 16 != 0)
    ys, xs = np.nonzero(mask)
    for yy, xx in zip(ys, xs):
        cost = ((RF - D[yy, xx]) ** 2).sum(1) + VOTE_LAMBDA * ((ry - yy) ** 2 + (rx - xx) ** 2)
        order = np.argsort(cost, kind='stable')[:VOTE_K]
        C[yy, xx] = RC[order].sum() * 2 > len(order)
    C = _regularise(C, mask, rect)
    known = rect & ~mask
    ky, kx = np.nonzero(known)
    padC = np.pad(C, 4)

    def win(yv, xv, r):
        return padC[yv + 4 - r:yv + 4 + r + 1, xv + 4 - r:xv + 4 + r + 1]
    stat = collections.Counter()
    # exemplar: the visible pixel whose 5x5 block / transparent neighbourhood differs least from the hidden pixel's
    # (the pixel itself must agree; a mismatch in the inner 3x3 counts 4, in the outer ring 1), nearest on a tie
    wts = np.array([4 if abs(dy) <= 1 and abs(dx) <= 1 else 1 for dy in range(-2, 3) for dx in range(-2, 3)], np.int32)
    centre = 12
    KW = np.array([padC[ky[i] + 2:ky[i] + 7, kx[i] + 2:kx[i] + 7].ravel() for i in range(len(ky))])
    kidx = g0[ky, kx]
    for yy, xx in zip(ys, xs):
        wp = padC[yy + 2:yy + 7, xx + 2:xx + 7].ravel()
        mism = ((KW != wp[None, :]) * wts[None, :]).sum(1)
        mism = np.where(KW[:, centre] != wp[centre], 10 ** 6, mism)
        d2 = (ky - yy) ** 2 + (kx - xx) ** 2
        score = mism * 1000 + np.minimum(d2, 999)
        i = int(np.argmin(score))
        if mism[i] >= 10 ** 6:
            raise PatchError('no visible pixel of the patch is of the class of the hidden pixel (%d, %d)' % (xx, yy))
        new[yy, xx] = kidx[i]
        stat[int(min(mism[i], 9))] += 1
    if sum(v for k, v in stat.items() if k > MAX_MISMATCH) > MAX_PLAIN:
        raise PatchError('%d hidden pixels have no visible pixel with a similar surrounding (more than %d of the 25 pixels weighted differ)'
                         % (sum(v for k, v in stat.items() if k > MAX_MISMATCH), MAX_MISMATCH))
    # a hidden pixel that came out opaque with no opaque neighbour is a speck, not a block
    lone = []
    for yy, xx in zip(ys, xs):
        if new[yy, xx] % 16 != 0:
            nb = sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy or dx) and 0 <= yy + dy < new.shape[0]
                     and 0 <= xx + dx < new.shape[1] and new[yy + dy, xx + dx] % 16 != 0)
            if nb <= 1:
                lone.append((yy, xx))
    for (yy, xx) in lone:
        new[yy, xx] = (g0[ky[0], kx[0]] // 16) * 16
    info['lone'] = len(lone)
    info['exemplar'] = dict(stat)
    info['class_opaque'] = int(C[mask].sum())
    return new


def patch_entry(blobs, parts, face, ground_maps, old_inks, info):
    """-> (new entry bytes, (old canvas, new canvas, palette)). blobs: the decoded entries of jpn/cutobj_local.bin;
    ground_maps: {map entry: (index grid of the map with no label, palette)}; old_inks: {map label name: its ink pixels
    on the fan's map}."""
    blob = blobs[ENTRY]
    E = ml.Entry(blob, parts)
    _, pal = gv.palette_of(blobs, ENTRY, 'after')
    pal = list(pal) + [(255, 0, 255)] * (256 - len(pal))
    g0 = _canvas(E)
    new = g0.copy()
    plan = []
    for P in PATCHES:
        x, y, w, h = P['rect']
        bank = P['bank']
        L = [l for l in cl.MAP_LABELS if l['name'] == P['label']][0]
        sub, subb = E.idx[y:y + h, x:x + w], E.bank[y:y + h, x:x + w]
        ink = set((int(xx) + x, int(yy) + y) for yy, xx in zip(*np.nonzero((sub == INK_IDX) & (subb == bank))))
        ox, oy = P['offset']
        as_map = set((a - x + ox, b - y + oy) for a, b in ink)
        if as_map != old_inks[P['label']]:
            raise PatchError("%s: the patch's old label is not the map's old label %r (%d against %d ink pixels)"
                             % (P['name'], L['old'], len(ink), len(old_inks[P['label']])))
        rect = np.zeros(SHEET, bool)
        rect[y:y + h, x:x + w] = True
        m = np.zeros(SHEET, bool)
        ink_m = np.zeros(SHEET, bool)
        for (a, b) in ink:
            m[b, a] = True
            ink_m[b, a] = True
        m = _dilate(m, MASK_PASSES) & rect        # the patch is a rectangle of the sheet: what leaves it is the map's
        # soft pixels of the old lettering just outside its ring: opaque, with at most one opaque neighbour that is not label
        near = _dilate(ink_m, SPECK_REACH) & rect & ~m & (g0 % 16 != 0)
        specks = []
        for yy, xx in zip(*np.nonzero(near)):
            nb = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if (dy or dx) and 0 <= yy + dy < SHEET[0] and 0 <= xx + dx < SHEET[1] and g0[yy + dy, xx + dx] % 16 != 0 \
                            and not m[yy + dy, xx + dx]:
                        nb += 1
            if nb <= 1:
                specks.append((int(xx), int(yy)))
        for (a, b) in specks:
            m[b, a] = True
        lines = cl.new_label(face, L, L['box'])
        ink_new, ring_o, ring_d = set(), set(), set()
        for text, pts, _ in lines:
            o, d = ring_of(pts)
            ink_new |= pts
            ring_o |= o
            ring_d |= d

        def to_sheet(pset, x=x, y=y, w=w, h=h, ox=ox, oy=oy):
            out = set()
            for (a, b) in pset:
                q = (a - ox + x, b - oy + y)
                if x <= q[0] < x + w and y <= q[1] < y + h:
                    out.add(q)
            return out
        plan.append(dict(P=P, rect=rect, mask=m, specks=specks, ink=to_sheet(ink_new), orth=to_sheet(ring_o - ink_new),
                         diag=to_sheet(ring_d - ring_o - ink_new), label=L, lines=lines))
    results = {}
    for q in plan:
        P, m, rect = q['P'], q['mask'], q['rect']
        bank = P['bank']
        x, y, w, h = P['rect']
        ox, oy = P['offset']
        have = [e for e in P['maps'] if e in ground_maps]
        if not have:
            raise PatchError('%s: no map ground to read the block from (maps %s)' % (P['name'], P['maps']))
        e = have[0]
        gmap, pm = ground_maps[e]
        pmf = np.array(pm, np.float64)
        D = np.zeros(SHEET + (3,), np.float64)
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                my, mx = yy - y + oy, xx - x + ox
                if 0 <= my < 192 and 0 <= mx < 256:
                    D[yy, xx] = pmf[gmap[my, mx]]
        rinfo = {}
        rec = reconstruct(g0, rect, m, D, rinfo)
        new[m] = rec[m]
        label_px = q['ink'] | q['orth'] | q['diag']
        # the label: ink, halo, and soft corners (0.6 white + 0.4 ground) only where there is ground under them
        bank_cols = [pal[16 * bank + i] for i in range(16)]
        white = np.array(bank_cols[HALO_IDX], np.float64)
        for (a, b) in q['diag']:
            under = int(new[b, a]) % 16
            if under == 0:
                continue
            blend = CORNER_SHARE * white + (1 - CORNER_SHARE) * np.array(bank_cols[under], np.float64)
            cand = [(float(((np.array(bank_cols[i], np.float64) - blend) ** 2).sum()), i) for i in range(1, 16)]
            new[b, a] = 16 * bank + min(cand)[1]
        for (a, b) in q['orth']:
            new[b, a] = 16 * bank + HALO_IDX
        for (a, b) in q['ink']:
            new[b, a] = 16 * bank + INK_IDX
        changed = set((int(a), int(b)) for b, a in zip(*np.nonzero(new != g0)) if rect[b, a])
        stray = changed - set((int(a), int(b)) for b, a in zip(*np.nonzero(m))) - label_px
        if stray:
            raise PatchError('%s: %d pixels changed outside the erase mask and the new label' % (P['name'], len(stray)))
        sel = new[rect]
        if ((sel // 16)[(sel % 16) != 0] != bank).any():
            raise PatchError('%s: a pixel took a colour of another palette bank' % P['name'])
        results[P['name']] = dict(mask=int(m.sum()), specks=len(q['specks']), label=len(label_px), reconstruct=rinfo,
                                  lines=[(t, a, z) for t, _p, (a, z) in q['lines']])
    written = []
    for b, a in zip(*np.nonzero(new != g0)):
        E.write_pixel(int(a), int(b), int(new[b, a]) % 16)
        written.append((int(a), int(b)))
    cells, total = ml.check_cells(E, written)
    nb = blob[:E.o[2]] + E.B.result()
    if len(nb) != len(blob):
        raise PatchError('entry %d changed size' % ENTRY)
    info.update(patches=results, written=len(written), cells=cells, cell_pixels=total)
    return nb, (g0, new, pal)


def patch_cutobj(co_bytes, dumpdir, face, ground_maps, fan_maps):
    """-> (new cutobj_local bytes, info, (old canvas, new canvas, palette)). ground_maps: {map entry: (grid with no
    label, palette)} from tools/city_labels.py; fan_maps: the fan's index grids of the city maps."""
    co = Idlocal(co_bytes)
    blobs = [co.blob(e) if co.ents[e][0] else b'' for e in range(co.n)]
    if ih.GUARD_INPUTS and ih.sha(blobs[ENTRY]) != ih.CUTOBJ_18_SHA256:
        raise PatchError("jpn/cutobj_local.bin entry %d is not the fan's" % ENTRY)
    _atlas, parts = ml.load_capcom(dumpdir, ml.NAMES[ENTRY])
    old_inks = {}
    for L in cl.MAP_LABELS:
        if L['name'] in ('waste center', 'waste mgmt'):
            old_inks[L['name']] = cl._old_ink(fan_maps[264], L)
        if L['name'] == 'warehouse':
            old_inks[L['name']] = cl._old_ink(fan_maps[280], L)
    info = {}
    nb, canvases = patch_entry(blobs, parts, face, ground_maps, old_inks, info)
    out = rebuild(co_bytes, {ENTRY: nb}, lz=(ENTRY,))
    back = Idlocal(out)
    info['stored'] = bb._stored_check(co, co_bytes, back, out, {ENTRY: nb}, 'cutobj_local')
    for e in range(co.n):
        if e != ENTRY and bb._content(back, e) != bb._content(co, e):
            raise PatchError('cutobj_local entry %d changed and should not have' % e)
    return out, info, canvases
