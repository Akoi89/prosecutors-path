# -*- coding: utf-8 -*-
"""Item pictures: is the fan's old wording gone from every picture tools/item_pics.py re-letters, and is
nothing outside the box it declares different from the fan's?

For each picture registered in tools/item_pics.py (jpn/upcut_local.bin pictures, com/idcom.bin and
com/logic_keyword.bin icons) the built ROM's picture is compared with the fan's:

  1. every pixel that differs is inside the box the module says it wipes (`old`);
  2. inside that box the luminance pattern of the built picture is NOT the fan's (normalised
     cross-correlation below NCC_MAX): the old lettering, which is what makes that pattern, is gone;
     a 'blank' picture (the old marking wiped and nothing drawn) must be a single index in the box;
  3. the palette entry is the fan's.

The same check run on the fan ROM itself must fail (the old wording is still there); that negative
control runs every time, so a detector that stops detecting is noticed.

    python audits/audit_item_pics.py [rom.nds] [fan_rom.nds]
"""
import os as _os
import sys as _sys

_REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.join(_REPO, 'tools'))

import hashlib
import numpy as np

NCC_MAX = 0.80


def _default_built():
    p = _os.path.join(_REPO, 'out', 'GK2 (Official English, DS port).nds')
    if _os.path.exists(p):
        return p
    cand = [f for f in _os.listdir(_os.path.join(_REPO, 'out'))
            if f.lower().endswith('.nds')] if _os.path.isdir(_os.path.join(_REPO, 'out')) else []
    if len(cand) == 1:
        return _os.path.join(_REPO, 'out', cand[0])
    raise SystemExit('no built ROM in %s - run a build first, or pass one as the first argument'
                     % _os.path.join(_REPO, 'out'))


def _default_fan():
    import locate
    rom, _ = locate.find_fan_rom([_REPO, _os.path.dirname(_REPO), _os.getcwd()])
    if not rom:
        raise SystemExit('could not find your AAI2 Final v2 ROM - pass it as the second argument')
    return rom


def _ncc(a, b):
    a = a - a.mean()
    b = b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return 1.0 if d == 0 else float((a * b).sum() / d)


class AuditFailure(Exception):
    pass


_SEEN = []


def _see(what):
    """Note that a picture is checked. Every problem message about it starts with `what + ':'`, which is how the negative
    control tells which pictures a run flagged."""
    _SEEN.append(what)


def _lum(rgb):
    return np.asarray(rgb, np.float64) @ np.array([0.299, 0.587, 0.114])


def _region_checks(what, bgrid, fgrid, bpal, fpal, spec, problems):
    ox0, oy0, ox1, oy1 = spec['old']
    if bgrid.shape != fgrid.shape:
        problems.append('%s: picture is %r, the fan\'s %r' % (what, bgrid.shape, fgrid.shape))
        return
    diff = bgrid != fgrid
    ys, xs = np.where(diff)
    outside = [(int(x), int(y)) for x, y in zip(xs, ys) if not (ox0 <= x < ox1 and oy0 <= y < oy1)]
    if outside:
        problems.append('%s: %d changed pixels outside the declared box %r, first %r' % (what, len(outside), spec['old'], outside[0]))
    if bpal != fpal:
        problems.append('%s: palette is not the fan\'s' % what)
    bl = _lum(np.array(bpal)[bgrid[oy0:oy1, ox0:ox1]])
    fl = _lum(np.array(fpal)[fgrid[oy0:oy1, ox0:ox1]])
    if spec.get('mode') == 'blank':
        if len(np.unique(bgrid[oy0:oy1, ox0:ox1])) != 1:
            problems.append('%s: the wiped box is not one flat index' % what)
    elif _ncc(bl, fl) >= NCC_MAX:
        problems.append('%s: the box still reads as the fan\'s lettering (NCC %.2f >= %.2f)' % (what, _ncc(bl, fl), NCC_MAX))


def check(rom, fan_rom, classes=None):
    """-> list of problems (empty when every registered picture is re-lettered and nothing else moved)."""
    import choice_strips as cs
    import idcom_icons as I
    import item_pics as P
    from nitro import nclr
    problems = []
    del _SEEN[:]
    up_b, up_f = cs.Idlocal(cs.rom_file(rom, P.UPCUT)), cs.Idlocal(cs.rom_file(fan_rom, P.UPCUT))
    for e, spec in sorted(P.UPCUT_PICS.items()):
        if classes and spec['cls'] not in classes:
            continue
        what = 'upcut_local entry %d' % e
        _see(what)
        if hashlib.sha256(up_f.blob(e)).hexdigest() != spec['sha']:
            problems.append('%s: the fan ROM is not the fan\'s' % what)
            continue
        _region_checks(what, P.pic_grid(up_b.blob(e)), P.pic_grid(up_f.blob(e)),
                       nclr(up_b.blob(e + 1)), nclr(up_f.blob(e + 1)), spec, problems)
    import choice_strips
    flat = dict(P.ICON_PICS)
    for k, v in P.SIBLING_PICS.items():
        flat[k] = dict(v, old=v['box'])
    for (cont, e), spec in sorted(flat.items()):
        if classes and spec['cls'] not in classes:
            continue
        what = '%s entry %d' % (cont, e)
        _see(what)
        cb, cf = cs.rom_file(rom, cont), cs.rom_file(fan_rom, cont)
        eb, _n = I.entry_decoded(cb, e)
        ef, _n = I.entry_decoded(cf, e)
        pb, _n = I.entry_decoded(cb, spec['pal'])
        pf, _n = I.entry_decoded(cf, spec['pal'])
        if hashlib.sha256(ef).hexdigest() != spec['sha']:
            problems.append('%s: the fan ROM is not the fan\'s' % what)
            continue
        _region_checks(what, np.array(cs.grid(eb), np.uint8), np.array(cs.grid(ef), np.uint8),
                       nclr(pb), nclr(pf), spec, problems)
    problems += check_swaps(up_b, up_f, classes)
    problems += check_bubbles(up_b, up_f, classes)
    problems += check_banners(up_b, up_f, classes)
    problems += check_newspapers(up_b, up_f, classes)
    problems += check_keycard_log(up_b, up_f, classes)
    problems += check_button(rom, fan_rom)
    problems += check_icons(rom, fan_rom, classes)
    problems += check_newsicons(rom, fan_rom, classes)
    return problems


def check_swaps(up_b, up_f, classes=None):
    """The upcut_local pictures redrawn whole from Capcom's texture (item_pics.UPCUT_SWAPS): every changed pixel
    is inside the declared box, the palette is the fan's, and inside the box the picture is closer to Capcom's own
    texture (area-averaged into the picture's grid) than the fan's old pixels were."""
    import item_pics as P
    from nitro import nclr
    problems = []
    dump = _os.path.join(_REPO, 'dump')
    reg = P.load_reg()
    swaps = dict(P.UPCUT_SWAPS)
    for e, v in P.UPCUT_LOCALS.items():
        swaps[e] = dict(v, old=v['box'], extra=P.patch_bounds(v['patches']) if v.get('patches') else [])
    for e, spec in sorted(swaps.items()):
        if classes and spec['cls'] not in classes:
            continue
        what = 'upcut_local entry %d' % e
        _see(what)
        if hashlib.sha256(up_f.blob(e)).hexdigest() != spec['sha']:
            problems.append("%s: the fan ROM is not the fan's" % what)
            continue
        gb, gf = P.pic_grid(up_b.blob(e)), P.pic_grid(up_f.blob(e))
        pb, pf = nclr(up_b.blob(e + 1)), nclr(up_f.blob(e + 1))
        x0, y0, x1, y1 = spec['old']
        ys, xs = np.where(gb != gf)
        extra = spec.get('extra', [])
        out = [(int(x), int(y)) for x, y in zip(xs, ys)
               if not (x0 <= x < x1 and y0 <= y < y1) and not any(a <= x < c and b <= y < d for a, b, c, d in extra)]
        if out:
            problems.append('%s: %d changed pixels outside the declared boxes %r + %r, first %r' % (what, len(out), spec['old'], extra, out[0]))
        if pb != pf:
            problems.append("%s: palette is not the fan's" % what)
        try:
            tex = P.load_texture(dump, spec['texture'])
        except P.ItemError as ex:
            problems.append('%s: %s' % (what, ex))
            continue
        h, w = gf.shape
        want = _lum(P.resample(tex, reg[str(e)]['reg'] if str(e) in reg else P.CROP_REG, w, h))[y0:y1, x0:x1]
        a = _ncc(_lum(np.array(pb)[gb[y0:y1, x0:x1]]), want)
        b = _ncc(_lum(np.array(pf)[gf[y0:y1, x0:x1]]), want)
        if not a > b + 0.03:
            problems.append("%s: the box is not closer to Capcom's picture (NCC %.2f) than to the fan's (%.2f)" % (what, a, b))
        for pl in (spec.get('patches') or ()):
            # a painted plaque: the box holds exactly the words of its spec in the ink colour, every column of the face is
            # one even colour apart from the words, and the top bevel row is lighter than the face under it
            d = pl.get('draw')
            if not d:
                continue
            bx0, by0, bx1, by1 = d['box']
            bev = d.get('bevel', 2)
            pal = np.array(pb, np.float64)
            ink = P._snap_pal(pal, P.PLAQUE_INK)
            want = P.plaque_text(d)
            got = {(int(x), int(y)) for y, x in zip(*np.where(gb[by0:by1, bx0:bx1] == ink))}
            got = {(x + bx0, y + by0) for x, y in got}
            if got != want:
                problems.append("%s: the plaque %r does not hold exactly the words %r (%d px differ)" % (what, d['box'], d['lines'], len(got ^ want)))
            for x in range(bx0 + 2, bx1 - 1):
                col = {int(gb[y, x]) for y in range(by0 + bev, by1 - 1) if (x, y) not in want}
                if len(col) != 1:
                    problems.append("%s: plaque %r column %d is not one even colour (%d indices)" % (what, d['box'], x, len(col)))
                    break
            lf = _lum(pal[gb[by0 + bev:by1 - 1, bx0 + 2:bx1 - 1]])
            lb = _lum(pal[gb[by0:by0 + 1, bx0 + 2:bx1 - 1]])
            if not lb.mean() > np.median(lf) + 2:
                problems.append("%s: plaque %r: the top bevel is not lighter than the face" % (what, d['box']))
    return problems


def check_bubbles(up_b, up_f, classes=None):
    """Speech bubbles re-lettered by item_pics.BUBBLES: the palette is the fan's, nothing outside the bubble body changed,
    the body holds exactly the lines of the spec in the ink colour on the bubble's yellow, and one pixel of yellow
    surrounds every letter."""
    import item_pics as P
    from nitro import nclr
    problems = []
    for e, spec in sorted(P.BUBBLES.items()):
        if classes and spec['cls'] not in classes:
            continue
        what = 'upcut_local entry %d (bubble)' % e
        _see(what)
        if hashlib.sha256(up_f.blob(e)).hexdigest() != spec['sha']:
            problems.append("%s: the fan ROM is not the fan's" % what)
            continue
        gb, gf = P.pic_grid(up_b.blob(e)), P.pic_grid(up_f.blob(e))
        pb, pf = nclr(up_b.blob(e + 1)), nclr(up_f.blob(e + 1))
        if pb != pf:
            problems.append("%s: palette is not the fan's" % what)
        wipe, _yel = P._bubble_geometry(gf, pf, spec)
        ys, xs = np.where(gb != gf)
        out = [(int(x), int(y)) for x, y in zip(xs, ys) if not wipe[y, x]]
        if out:
            problems.append('%s: %d changed pixels outside the bubble body, first %r' % (what, len(out), out[0]))
        text = P.bubble_text(spec)
        _new, ink = P.paint_bubble(gf, pf, spec)
        got = {(int(x), int(y)) for y, x in zip(*np.where(wipe & (gb == ink)))}
        if got != text:
            problems.append('%s: the lettering is not exactly the lines %r (%d px differ)' % (what, spec['lines'], len(got ^ text)))
        rest = wipe & ~np.isin(np.arange(gb.size).reshape(gb.shape), [y * gb.shape[1] + x for x, y in text])
        if (gb[rest] != spec['yellow']).any():
            problems.append('%s: the body is not clean yellow around the lettering' % what)
        for (x, y) in text:
            if not all(wipe[y + b, x + a] for a in (-1, 0, 1) for b in (-1, 0, 1)):
                problems.append('%s: a letter pixel (%d, %d) touches the bubble edge' % (what, x, y))
                break
    return problems


def check_banners(up_b, up_f, classes=None):
    """Replaced banners (item_pics.BANNERS): the palette is the fan's, only the restored box and the bar rows changed, no
    pixel of the fan's red banner colour is left in the restored box, each bar row is one colour apart from the headline,
    and the headline is exactly the spec's text in the ink colour."""
    import item_pics as P
    from nitro import nclr
    problems = []
    dump = _os.path.join(_REPO, 'dump')
    for e, spec in sorted(P.BANNERS.items()):
        if classes and spec['cls'] not in classes:
            continue
        what = 'upcut_local entry %d (banner)' % e
        _see(what)
        if hashlib.sha256(up_f.blob(e)).hexdigest() != spec['sha']:
            problems.append("%s: the fan ROM is not the fan's" % what)
            continue
        gb, gf = P.pic_grid(up_b.blob(e)), P.pic_grid(up_f.blob(e))
        pb, pf = nclr(up_b.blob(e + 1)), nclr(up_f.blob(e + 1))
        if pb != pf:
            problems.append("%s: palette is not the fan's" % what)
        m = P.banner_regions(spec, gf.shape[1], gf.shape[0])
        ys, xs = np.where(gb != gf)
        out = [(int(x), int(y)) for x, y in zip(xs, ys) if not m[y, x]]
        if out:
            problems.append('%s: %d changed pixels outside the banner regions, first %r' % (what, len(out), out[0]))
        pal = np.array(pb, np.float64)
        x0, y0, x1, y1 = spec['restore']
        rgb = pal[gb[y0:y1, x0:x1]]
        red = ((rgb[..., 0] > 190) & (rgb[..., 1] < 70) & (rgb[..., 2] < 70)).sum()
        if red:
            problems.append("%s: %d pixels of the fan's red banner are left in the restored box" % (what, red))
        try:
            tex = P.load_texture(dump, spec['texture'])
        except P.ItemError as ex:
            problems.append('%s: %s' % (what, ex))
            continue
        small = P.resample(tex, P.CROP_REG, gf.shape[1], gf.shape[0])
        _bar, rows = P._bar_rows(small, spec)
        text = P.banner_text(spec, rows, gf.shape[1])
        ink = P._snap_pal(pal, (245.0, 245.0, 245.0))
        ty = [y for _x, y in text]
        band = (gb[min(ty):max(ty) + 1] == ink)
        got = {(int(x), int(y) + min(ty)) for y, x in zip(*np.where(band))}
        if got != text:
            problems.append('%s: the headline is not exactly %r (%d px differ)' % (what, spec['text'], len(got ^ text)))
        for y in range(spec['bar'][0], spec['bar'][1]):
            cols = {int(gb[y, x]) for x in range(gb.shape[1]) if (x, y) not in text}
            if len(cols) != 1:
                problems.append('%s: bar row %d is not one colour (%d indices)' % (what, y, len(cols)))
                break
    return problems


def check_newspapers(up_b, up_f, classes=None):
    """Newspaper pages (item_pics.NEWSPAPERS, tools/newspaper.py): the palette is the fan's, nothing outside the declared boxes
    (each piece's box and each baked patch's box) differs from the fan's, inside every box the luminance pattern is no longer
    the fan's (the old lettering is gone), and the picture is exactly what newspaper.paint_news draws on the fan's picture
    from Capcom's texture."""
    import item_pics as P
    import newspaper as N
    from nitro import nclr
    problems = []
    dump = _os.path.join(_REPO, 'dump')
    for e, spec in sorted(P.NEWSPAPERS.items()):
        if classes and spec['cls'] not in classes:
            continue
        what = 'upcut_local entry %d (newspaper)' % e
        _see(what)
        if hashlib.sha256(P._content(up_f, e)).hexdigest() != spec['sha']:
            problems.append("%s: the fan ROM is not the fan's" % what)
            continue
        gb, gf = P.pic_grid(up_b.blob(e)), P.pic_grid(up_f.blob(e))
        pb, pf = nclr(up_b.blob(e + 1)), nclr(up_f.blob(e + 1))
        if pb != pf:
            problems.append("%s: palette is not the fan's" % what)
        boxes = N.boxes_of(spec)
        ys, xs = np.where(gb != gf)
        out = [(int(x), int(y)) for x, y in zip(xs, ys) if not any(a <= x < c and b <= y < d for a, b, c, d in boxes)]
        if out:
            problems.append('%s: %d changed pixels outside the declared boxes %r, first %r' % (what, len(out), boxes, out[0]))
        pal = np.array(pf, np.float64)
        for (x0, y0, x1, y1) in boxes:
            n = _ncc(_lum(pal[gb[y0:y1, x0:x1]]), _lum(pal[gf[y0:y1, x0:x1]]))
            if n >= NCC_MAX:
                problems.append("%s: the box %r still reads as the fan's lettering (NCC %.2f >= %.2f)" % (what, (x0, y0, x1, y1), n, NCC_MAX))
        try:
            tex = P.load_texture(dump, spec['texture']) if spec['texture'] else None
        except P.ItemError as ex:
            problems.append('%s: %s' % (what, ex))
            continue
        try:
            want = N.paint_news(gf, pal, tex, spec)
        except P.ItemError as ex:
            problems.append('%s: %s' % (what, ex))
            continue
        if not np.array_equal(gb, want):
            problems.append('%s: the picture differs from what newspaper.py draws at %d pixels' % (what, int((gb != want).sum())))
    return problems


# the fan's keycard log pictures (jpn/upcut_local.bin 210 and 242, redrawn by tools/cg_names.py): sha256 of the graphics and the
# palette entry
KEYCARD_LOG_FAN = {
    210: ('bb2e9454290a2e020422de2442e115ff2de45f23afd71af4742bbe15ce2a8b29',
          '13cf240dbab2e6e287caf16908f3c8d934ff9b5f26436896993260498d2fadb5'),
    242: ('d7eaa94b4cda895f73ce96ac906b38f850fcc18c39adca0a39252cb3ab48038c',
          '13cf240dbab2e6e287caf16908f3c8d934ff9b5f26436896993260498d2fadb5'),
}


def check_keycard_log(up_b, up_f, classes=None):
    """The keycard log tables (upcut_local 210 and 242): the built picture is exactly what tools/cg_names.py draws on the fan's
    picture (Capcom's layout and wording), the palette is the fan's, nothing below the table's name rows differs but the moved
    column line (x 136 to 156), and the old column heads are gone."""
    import cg_names as C
    import item_pics as P
    from nitro import nclr
    problems = []
    if classes and 'keycard' not in classes:
        return problems
    faces = C.make_faces()
    for e, (gsha, psha) in sorted(KEYCARD_LOG_FAN.items()):
        what = 'upcut_local entry %d (keycard log)' % e
        _see(what)
        fg, fp = P._content(up_f, e), P._content(up_f, e + 1)
        if hashlib.sha256(fg).hexdigest() != gsha or hashlib.sha256(fp).hexdigest() != psha:
            problems.append("%s: the fan ROM is not the fan's" % what)
            continue
        bg, bp = P._content(up_b, e), P._content(up_b, e + 1)
        if bp != fp:
            problems.append("%s: palette is not the fan's" % what)
        want = C.apply_entry(fg, nclr(fp), C.EDITS[e], faces, [], e)
        if bg != want:
            problems.append("%s: the picture is not the keycard log as cg_names draws it (Keycard Log heading, User ID / Time of Use / "
                            "User Name, the Capcom names)" % what)
        gb, gf = P.pic_grid(bg), P.pic_grid(fg)
        ys, xs = np.where(gb != gf)
        out = [(int(x), int(y)) for x, y in zip(xs, ys) if not (5 <= y < 90 or x in (136, 156))]
        if out:
            problems.append('%s: %d changed pixels below the name rows other than the moved column line, first %r' % (what, len(out), out[0]))
        pal = np.array(nclr(bp))
        if _ncc(_lum(pal[gb[31:49, 9:246]]), _lum(pal[gf[31:49, 9:246]])) >= NCC_MAX:
            problems.append("%s: the column heads still read as the fan's" % what)
    return problems


def check_icons(rom, fan_rom, classes=None):
    """The icons idcom_icons.py redraws locally (ICONS entries with a `local` box): the box holds Capcom's lettering,
    not the fan's. Every pixel that differs from the fan's is inside the box; the box's luminance pattern is closer to
    Capcom's own texture (area-averaged into the icon grid) than to the fan's old pixels; the palette is the fan's."""
    import choice_strips as cs
    import idcom_icons as I
    from nitro import nclr
    problems = []
    dump = _os.path.join(_REPO, 'dump')
    cb, cf = cs.rom_file(rom, I.CONTAINER), cs.rom_file(fan_rom, I.CONTAINER)
    import icon_labels
    icon_labels.harvest({k: np.array(cs.grid(I.entry_decoded(cf, k)[0]), np.uint8) for k in icon_labels.HARVEST})
    for e, spec in sorted(I.ICONS.items()):
        lc = spec.get('local')
        if spec.get('title'):
            lc = dict(box=spec['title']['box'], title=True)
        if spec.get('words'):
            # pixel lettering: the box is every word's erase box plus the rows its letters reach
            import icon_labels
            bx = [w['erase'] for w in spec['words']]
            for w in spec['words']:
                if w['text']:
                    wid = icon_labels.word_bitmap(w['text'], 1, w.get('face'))[1]
                    bx.append((w['x'], w['y'], w['x'] + wid, w['y'] + (4 if w.get('face') else 9)))
            lc = dict(box=(min(b[0] for b in bx), min(b[1] for b in bx), max(b[2] for b in bx), max(b[3] for b in bx)), words=True)
        if spec.get('sibling'):
            lc = dict(box=spec['sibling']['box'], sibling=True)
        if not lc:
            continue
        what = '%s entry %d' % (I.CONTAINER, e)
        _see(what)
        eb, _n = I.entry_decoded(cb, e)
        ef, _n = I.entry_decoded(cf, e)
        pb, _n = I.entry_decoded(cb, spec['pal'])
        pf, _n = I.entry_decoded(cf, spec['pal'])
        if hashlib.sha256(ef).hexdigest() != spec['sha']:
            problems.append("%s: the fan ROM is not the fan's" % what)
            continue
        gb, gf = np.array(cs.grid(eb), np.uint8), np.array(cs.grid(ef), np.uint8)
        x0, y0, x1, y1 = lc['box']
        outside = [(int(x), int(y)) for y, x in zip(*np.where(gb != gf)) if not (x0 <= x < x1 and y0 <= y < y1)]
        if outside:
            problems.append('%s: %d changed pixels outside the declared box %r, first %r' % (what, len(outside), lc['box'], outside[0]))
        if nclr(pb) != nclr(pf):
            problems.append("%s: palette is not the fan's" % what)
        if lc.get('sibling'):
            # the small twin of an icon takes its picture from the big one (the keycard): the old lettering is gone
            if _ncc(_lum(np.array(nclr(pb))[gb[y0:y1, x0:x1]]), _lum(np.array(nclr(pf))[gf[y0:y1, x0:x1]])) >= NCC_MAX:
                problems.append("%s: the box still reads as the fan's lettering" % what)
            continue
        if lc.get('title'):
            # a pale title on a cover: the old title is gone (the box no longer reads as the fan's pixels), the new
            # lettering is PALE (its brightest pixels are well above the ground and at least as light as the fan's own
            # title ink), and the cleared band holds no pixel the fan's ground does not use
            nb, nf = _lum(np.array(nclr(pb))[gb[y0:y1, x0:x1]]), _lum(np.array(nclr(pf))[gf[y0:y1, x0:x1]])
            if _ncc(nb, nf) >= NCC_MAX:
                problems.append("%s: the box still reads as the fan's lettering" % what)
            ground = float(_lum(np.array(nclr(pb))[spec['title']['ground']]))
            if nb.max() < ground + 90 or nb.max() < nf.max() - 1:
                problems.append("%s: the title is not pale (brightest %.0f, ground %.0f, fan's %.0f)" % (what, nb.max(), ground, nf.max()))
            continue
        if lc.get('words'):
            # the old word is gone: the box no longer reads as the fan's pixels
            if _ncc(_lum(np.array(nclr(pb))[gb[y0:y1, x0:x1]]), _lum(np.array(nclr(pf))[gf[y0:y1, x0:x1]])) >= NCC_MAX:
                problems.append("%s: the box still reads as the fan's lettering" % what)
            if spec.get('small'):
                # small print of Capcom's own word: the box is closer to Capcom's word (area-averaged) than to the fan's
                tex = _os.path.join(dump, 'title', 'idcom', spec['eng'] + '.png')
                if not _os.path.isfile(tex):
                    problems.append("%s: Capcom's texture %s is not in the dump, cannot compare" % (what, spec['eng']))
                    continue
                from PIL import Image
                t = np.asarray(Image.open(tex).convert('RGB'), np.float64)
                sx0, sy0, sx1, sy1 = spec['small']['src']
                dx0, dy0, dx1, dy1 = spec['small']['dst']
                lum = Image.fromarray((t @ np.array([0.299, 0.587, 0.114])).astype(np.float32), mode='F')
                want = np.asarray(lum.resize((dx1 - dx0, dy1 - dy0), Image.BOX, box=(sx0, sy0, sx1, sy1)), np.float64)
                newl = _lum(np.array(nclr(pb))[gb[dy0:dy1, dx0:dx1]])
                oldl = _lum(np.array(nclr(pf))[gf[dy0:dy1, dx0:dx1]])
                a, b = _ncc(newl, want), _ncc(oldl, want)
                if not a > b + 0.03:
                    problems.append("%s: the small print is not closer to Capcom's word (NCC %.2f) than to the fan's (%.2f)" % (what, a, b))
            continue
        tex = _os.path.join(dump, 'title', 'idcom', spec['eng'] + '.png')
        if not _os.path.isfile(tex):
            problems.append("%s: Capcom's texture %s is not in the dump, cannot compare" % (what, spec['eng']))
            continue
        from PIL import Image
        t = np.asarray(Image.open(tex).convert('RGB'), np.float64)
        import json
        reg = json.load(open(_os.path.join(_REPO, 'tools', 'idcom_icons_reg.json')))[str(e)]['reg']
        want = _lum(I.resample(I.tone(t, spec.get('bg')), reg, spec['size']))[y0:y1, x0:x1]
        newl = _lum(np.array(nclr(pb))[gb[y0:y1, x0:x1]])
        oldl = _lum(np.array(nclr(pf))[gf[y0:y1, x0:x1]])
        a, b = _ncc(newl, want), _ncc(oldl, want)
        if not a > b + 0.03:
            problems.append("%s: the box is not closer to Capcom's lettering (NCC %.2f) than to the fan's (%.2f)" % (what, a, b))
    return problems


def check_newsicons(rom, fan_rom, classes=None):
    """Newspaper icons (item_pics ICON_PICS entries of class 'newsicon', tools/newspaper.py paint_icon): the palette is the fan's,
    only the declared boxes differ from the fan's, and inside each box the picture is exactly what paint_icon draws from
    Capcom's texture on the fan's icon (the old lettering is gone and the new is Capcom's)."""
    import choice_strips as cs
    import idcom_icons as I
    import item_pics as P
    import newspaper as N
    from nitro import nclr
    problems = []
    dump = _os.path.join(_REPO, 'dump')
    for (cont, e), spec in sorted(P.ICON_PICS.items()):
        if spec['cls'] != 'newsicon' or (classes and 'newsicon' not in classes):
            continue
        what = '%s entry %d (newspaper icon)' % (cont, e)
        _see(what)
        cb, cf = cs.rom_file(rom, cont), cs.rom_file(fan_rom, cont)
        eb, _n = I.entry_decoded(cb, e)
        ef, _n = I.entry_decoded(cf, e)
        pb, _n = I.entry_decoded(cb, spec['pal'])
        pf, _n = I.entry_decoded(cf, spec['pal'])
        if hashlib.sha256(ef).hexdigest() != spec['sha']:
            problems.append("%s: the fan ROM is not the fan's" % what)
            continue
        if nclr(pb) != nclr(pf):
            problems.append("%s: palette is not the fan's" % what)
        gb, gf = np.array(cs.grid(eb), np.uint8), np.array(cs.grid(ef), np.uint8)
        boxes = [pc['box'] for pc in spec['pieces']]
        out = [(int(x), int(y)) for y, x in zip(*np.where(gb != gf)) if not any(a <= x < c and b <= y < d for a, b, c, d in boxes)]
        if out:
            problems.append('%s: %d changed pixels outside the declared boxes %r, first %r' % (what, len(out), boxes, out[0]))
        pal = np.array(nclr(pf), np.float64)
        for (x0, y0, x1, y1) in boxes:
            n = _ncc(_lum(pal[gb[y0:y1, x0:x1]]), _lum(pal[gf[y0:y1, x0:x1]]))
            if n >= NCC_MAX:
                problems.append("%s: the box %r still reads as the fan's lettering (NCC %.2f >= %.2f)" % (what, (x0, y0, x1, y1), n, NCC_MAX))
        try:
            want = N.paint_icon(gf, pal, I.load_texture(dump, spec['texture']), spec)
        except (P.ItemError, I.IconError) as ex:
            problems.append('%s: %s' % (what, ex))
            continue
        if not np.array_equal(gb, want):
            problems.append('%s: the icon differs from what newspaper.py draws at %d pixels' % (what, int((gb != want).sum())))
    return problems


def check_button(rom, fan_rom):
    """The partner card's button (tools/menu_button.py, idlocal 357 cell 10): the built cell is exactly the fan's with the old
    words replaced by Capcom's, laid out from the face cut out of the fan's own button; nothing outside the words' rows differs
    and the old words are not what is drawn."""
    import choice_strips as cs
    import menu_button as M
    import room_names as rn
    import json, io
    problems = []
    _see('menu button')
    dump = _os.path.join(_REPO, 'dump')
    try:
        loc = json.load(io.open(_os.path.join(dump, 'loc_en.json'), encoding='utf-8'))
        lines = M.capcom_lines(loc)
    except (OSError, M.ButtonError) as ex:
        return ['menu button: %s' % ex]
    ib, ifan = cs.Idlocal(cs.rom_file(rom, M.IDLOCAL)), cs.Idlocal(cs.rom_file(fan_rom, M.IDLOCAL))
    if hashlib.sha256(ifan.blob(M.TILES)).hexdigest() != M.FAN_SHA256[M.TILES]:
        return ["menu button: the fan ROM is not the fan's"]
    gf, _o = rn.Bundle(ifan.blob(M.CELLS), ifan.blob(M.TILES)).grid(M.CELL)
    gb, _o = rn.Bundle(ib.blob(M.CELLS), ib.blob(M.TILES)).grid(M.CELL)
    face, spans = M.build_face(gf)
    want, _dropped = M.new_grid(face, spans, gf, lines)
    if not np.array_equal(gb, want):
        n = int((gb != want).sum())
        problems.append("menu button: the built cell differs from Capcom's words in the fan's face at %d pixels" % n)
    ys, xs = np.where(gb != gf)
    out = [(int(x), int(y)) for x, y in zip(xs, ys) if not (10 <= x < 70 and 47 <= y < 65)]
    if out:
        problems.append("menu button: %d changed pixels outside the words' rows, first %r" % (len(out), out[0]))
    return problems


def main(argv):
    rom_path = argv[1] if len(argv) > 1 else _default_built()
    fan_path = argv[2] if len(argv) > 2 else _default_fan()
    rom = open(rom_path, 'rb').read()
    fan = open(fan_path, 'rb').read()
    problems = check(rom, fan)
    checked = list(dict.fromkeys(_SEEN))
    if problems:
        for p in problems:
            print('FAIL', p)
        print('audit_item_pics: %d problem(s)' % len(problems))
        return 1
    print('audit_item_pics: %d pictures re-lettered, nothing outside their boxes differs from the fan' % len(checked))
    control = check(fan, fan)
    seen = list(dict.fromkeys(_SEEN))
    if seen != checked:
        print('FAIL negative control walked %d pictures, the real run %d' % (len(seen), len(checked)))
        return 1
    flagged = [k for k in checked if any(p.startswith(k + ':') for p in control)]
    unflagged = [k for k in checked if k not in flagged]
    print('negative control: the fan ROM is flagged for %d of %d pictures (the old wording is still in it)' % (len(flagged), len(checked)))
    if unflagged:
        for k in unflagged:
            print('FAIL negative control does not flag %s' % k)
        return 1
    return 0


if __name__ == '__main__':
    _sys.exit(main(_sys.argv))
