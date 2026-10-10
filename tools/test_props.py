# -*- coding: utf-8 -*-
"""Tests for tools/props.py and tools/props_detect.py. Run from the port folder after a build:
    python tools/test_props.py <built rom> [dump folder]

Shows the redraw is deterministic, then requires a refusal (an exception) for each broken input:
a picture that is not the fan's, a missing extracted window, a Capcom window that does not register
(the picture moved by two pixels, and a blank texture), lettering whose words are not where the table
says, and the detector run on the fan's own containers (old lettering present).
"""
import os, sys, shutil, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import props, props_core as pc, props_detect
from bufcheck import rom_file
from props_core import PropsError
from nitro import nclr


def must_raise(name, fn, kinds=(PropsError,), *, expect):
    """fn must raise one of kinds, and its message must contain expect (it failed for that reason)."""
    try:
        fn()
    except kinds as e:
        if expect not in str(e):
            raise SystemExit('FAILED: %s raised for another reason: %s' % (name, str(e).split('\n')[0][:200]))
        print('  RAISED  %-52s %s' % (name, str(e).split('\n')[0][:150]))
        return
    raise SystemExit('FAILED: %s was accepted' % name)


def fan_picture(dumpdir, p):
    d = open(os.path.join(dumpdir, 'ds_fan', *p['cont'].split('/')), 'rb').read()
    g, _ = props.read_grid(props.entry_decoded(d, p['entry'])[0])
    pal = nclr(props.entry_decoded(d, p['pal'])[0])
    return d, g, pal


# ---------------------------------------------------------------- band plants (the detector's own test)
# The fan's decoded pixels are copied into the decoded BUILT picture over a band (one sixth of a line of the
# old word along its length, one line at a time for a word on several lines, at every band position), over
# every 1-, 2- and 3-row strip inside the old word's extent, and over each single pixel of the old word the
# build changed; each result is judged by the detector's own check functions and both its rules.

def segs(proj, gap=2):
    out, start, last = [], None, None
    for i, v in enumerate(proj):
        if v:
            if start is None:
                start = i
            elif i - last > gap + 1:
                out.append((start, last + 1))
                start = i
            last = i
    if start is not None:
        out.append((start, last + 1))
    return out


# signs whose words run down the picture (banners): bands along rows; the others along columns
VERTICAL = {'cotton_mapbg54', 'cotton_mapbg56', 'cotton_mapbg60', 'cotton_upcut406', 'cotton_upcutlocal206',
            'cotton_upcutlocal234'}


def lines(counts):
    """[(a, b)] lines of text from the per-row (or per-column) mask counts: runs at or over a quarter of the
    busiest, runs one apart merged, each line reaching halfway to its neighbours."""
    nz = np.nonzero(counts)[0]
    core = counts >= 0.25 * counts.max()
    runs = segs(core, gap=1)
    out = []
    for i, (a, b) in enumerate(runs):
        lo = nz.min() if i == 0 else (runs[i - 1][1] + a) // 2
        hi = nz.max() + 1 if i == len(runs) - 1 else (b + runs[i + 1][0] + 1) // 2
        out.append((lo, hi))
    return out


def grid_bands(m, boxes, vertical=False):
    """[(label, region bool)]: per sign box, per line of the word in it, six bands along the line."""
    out = []
    for bi, box in enumerate(boxes):
        inb = props_detect._boxmask(m.shape, [box])
        mb = m & inb
        if not mb.any():
            continue
        horiz = not vertical
        for li, (a, b) in enumerate(lines(mb.sum(1) if horiz else mb.sum(0))):
            sub = np.zeros_like(mb)
            if horiz:
                sub[a:b] = mb[a:b]
                ax = np.nonzero(sub)[1]
            else:
                sub[:, a:b] = mb[:, a:b]
                ax = np.nonzero(sub)[0]
            if not len(ax):
                continue
            edges = np.linspace(ax.min(), ax.max() + 1, 7).round().astype(int)
            for i in range(6):
                r = np.zeros_like(mb)
                if horiz:
                    r[a:b, edges[i]:edges[i + 1]] = True
                else:
                    r[edges[i]:edges[i + 1], a:b] = True
                out.append(('box%d line%d band%d' % (bi, li, i), r & inb))
    return out


def _strips(m, boxes, vertical):
    """[(label, region)]: every 1-, 2- and 3-row strip (columns for a word running down a banner) at every offset
    inside the old word's extent in each box."""
    out = []
    for bi, box in enumerate(boxes):
        inb = props_detect._boxmask(m.shape, [box])
        mb = m & inb
        if not mb.any():
            continue
        ys, xs = np.nonzero(mb)
        lo, hi = (xs.min(), xs.max() + 1) if vertical else (ys.min(), ys.max() + 1)
        for h in (1, 2, 3):
            for s in range(lo, hi - h + 1):
                r = np.zeros_like(mb)
                if vertical:
                    r[:, s:s + h] = True
                else:
                    r[s:s + h] = True
                out.append(('box%d strip%d@%d' % (bi, h, s), r & inb))
    return out


def plants(rom, D):
    """per sign: [(kind, label, flagged, changed old-lettering pixels restored)]: the fan's decoded pixels copied
    into the decoded BUILT picture over each band, each 1/2/3-row strip and each single changed pixel of the
    old word, judged by the detector's own check functions and its two rules (props_detect.flagged); flagged
    None for a band or strip holding no old pixel the build changed (skipped)."""
    get = lambda c: rom_file(rom, c)
    import props
    res = {}
    for name in props_detect.SIGNS:
        c = props_detect.SIGNS[name][0]
        fan_c, jp_c, new_c = props_detect._read(D, 'ds_fan', c), props_detect._read(D, 'ds_jp', c), get(c)
        g, m = props_detect.sign_mask(name, fan_c, jp_c, D)
        n0 = props.read_grid(props.entry_decoded(new_c, props_detect.SIGNS[name][1])[0])[0]
        changed = m & (n0 != g)
        boxes = props_detect.SIGNS[name][3]
        regions = [('band', l, r) for l, r in grid_bands(m, boxes, name in VERTICAL)]
        regions += [('strip', l, r) for l, r in _strips(m, boxes, name in VERTICAL)]
        rows = []
        for kind, lab, r in regions:
            k = int((changed & r).sum())
            if not k:
                rows.append((kind, lab, None, 0))
                continue
            kept, nm, exact = props_detect.check_sign(name, fan_c, jp_c, new_c, D, edit=lambda g_, n_, r=r: np.where(r, g_, n_))
            rows.append((kind, lab, props_detect.flagged(name, kept, exact), k))
        for y, x in zip(*np.nonzero(changed)):
            def one(g_, n_, y=y, x=x):
                n2 = n_.copy()
                n2[y, x] = g_[y, x]
                return n2
            kept, nm, exact = props_detect.check_sign(name, fan_c, jp_c, new_c, D, edit=one)
            rows.append(('pixel', '(%d,%d)' % (x, y), props_detect.flagged(name, kept, exact), 1))
        res[name] = rows
    bc = 'com/bustup.bin'
    for e in sorted(props_detect.NURSE):
        name = 'nurse_bustup%d' % e
        fan_c, jp_c, new_c = props_detect._read(D, 'ds_fan', bc), props_detect._read(D, 'ds_jp', bc), get(bc)
        from nitro import nclr
        f = np.frombuffer(props.entry_decoded(fan_c, e)[0], np.uint8)
        n0 = np.frombuffer(props.entry_decoded(new_c, e)[0], np.uint8)
        pal = np.array(nclr(props.entry_decoded(fan_c, props_detect.NURSE[e][0])[0]), np.float64)
        m, xs, ys = props_detect.nurse_mask(e, props.entry_decoded(fan_c, e)[0], props.entry_decoded(jp_c, e)[0], pal)
        ch = n0[m] != f[m]
        sels = []
        edges = np.linspace(xs.min(), xs.max() + 1, 7).round().astype(int)
        for i in range(6):
            sels.append(('band', 'x band%d' % i, (xs >= edges[i]) & (xs < edges[i + 1])))
        for h in (1, 2, 3):
            for s in range(ys.min(), ys.max() + 2 - h):
                sels.append(('strip', 'y strip%d@%d' % (h, s), (ys >= s) & (ys < s + h)))
        for i in np.nonzero(ch)[0]:
            one = np.zeros(len(m), bool)
            one[i] = True
            sels.append(('pixel', 'byte %d' % m[i], one))
        rows = []
        for kind, lab, sel in sels:
            k = int((ch & sel).sum())
            if not k:
                rows.append((kind, lab, None, 0))
                continue

            def edit(f_, n_, m_, xs_, sel=sel):
                n2 = n_.copy()
                n2[m_[sel]] = f_[m_[sel]]
                return n2
            kept, nm, exact = props_detect.check_nurse(e, fan_c, jp_c, new_c, edit=edit)
            rows.append((kind, lab, props_detect.flagged(name, kept, exact), k))
        res[name] = rows
    ic = 'com/idcom.bin'
    import choice_strips as cs
    for e in sorted(props_detect.ICONS):
        for part in ('red', 'dark'):
            name = 'nurse_idcom%d_%s' % (e, part)
            fan_c, jp_c, new_c = props_detect._read(D, 'ds_fan', ic), props_detect._read(D, 'ds_jp', ic), get(ic)
            g, m = props_detect.icon_mask(e, fan_c, jp_c, part)
            n0 = np.array(cs.grid(props.entry_decoded(new_c, e)[0]))
            changed = m & (n0 != g)
            box = [props_detect.ICONS[e][1]]
            regions = [('band', l, r) for l, r in grid_bands(m, box)] + [('strip', l, r) for l, r in _strips(m, box, False)]
            rows = []
            for kind, lab, r in regions:
                k = int((changed & r).sum())
                if not k:
                    rows.append((kind, lab, None, 0))
                    continue
                kept, nm, exact = props_detect.check_icon(e, fan_c, jp_c, new_c, part, edit=lambda g_, n_, r=r: np.where(r, g_, n_))
                rows.append((kind, lab, props_detect.flagged(name, kept, exact), k))
            for y, x in zip(*np.nonzero(changed)):
                def one(g_, n_, y=y, x=x):
                    n2 = n_.copy()
                    n2[y, x] = g_[y, x]
                    return n2
                kept, nm, exact = props_detect.check_icon(e, fan_c, jp_c, new_c, part, edit=one)
                rows.append(('pixel', '(%d,%d)' % (x, y), props_detect.flagged(name, kept, exact), 1))
            res[name] = rows
    return res


def main(rom_path, dumpdir='dump'):
    print('determinism: every picture redrawn twice')
    for p in props.PICTURES:
        _d, g, pal = fan_picture(dumpdir, p)
        a = props.redraw(p, g, pal, dumpdir)
        b = props.redraw(p, g, pal, dumpdir)
        if not np.array_equal(a, b):
            raise SystemExit('FAILED: %s is not deterministic' % p['name'])
        print('  %-24s %d pixels changed, same both times' % (p['name'], int((a != g).sum())))
    p0 = props.PICTURES[0]
    d, g, pal = fan_picture(dumpdir, p0)
    print('refusals')
    # a picture that is not the fan's (one pixel changed before the redraw)
    import lz11
    t = props.table(d)
    ext = props.extents(t, len(d))
    dec = props.entry_decoded(d, p0['entry'])[0]
    g2 = g.copy()
    g2[0, 0] ^= 1
    st = lz11.compress(props.write_grid(dec, g2))
    a, b = ext[p0['entry']]
    bad = bytearray(d)
    bad[a:b] = st + bytes(b - a - len(st))
    must_raise('%s: picture one pixel off the fan\'s' % p0['cont'],
               lambda: props.patch_container(p0['cont'], bytes(bad), dumpdir), expect="is not the fan's picture")
    # a missing extracted window
    tmp = tempfile.mkdtemp()
    try:
        must_raise('extracted window missing', lambda: props.redraw(p0, g, pal, tmp),
                   expect='is missing; run the build once without --skip-extract')
        # the DS picture moved by two pixels against Capcom's window: registration must refuse
        must_raise('DS picture moved two pixels right', lambda: props.redraw(p0, np.roll(g, 2, 1), pal, dumpdir),
                   expect="does not register onto the DS picture")
        must_raise('DS picture moved two pixels down', lambda: props.redraw(p0, np.roll(g, 2, 0), pal, dumpdir),
                   expect="does not register onto the DS picture")
        src = props.cache_dir(dumpdir)
        os.makedirs(props.cache_dir(tmp))
        # a blank English texture: no lettering where the table says
        for k in props.LETTERING:
            L = props.LETTERING[k]
            x0, y0, x1, y1 = L['box']
            lb = (x0 - 32, y0 - 32, x1 + 32, y1 + 32)
            for l in props.LANGS:
                shutil.copy(os.path.join(src, props.crop_name(L['canvas'], lb, l)), props.cache_dir(tmp))
            props.lettering_alpha(tmp, k)          # the copied crops pass
            jp = os.path.join(src, props.crop_name(L['canvas'], lb, ''))
            shutil.copy(jp, os.path.join(props.cache_dir(tmp), props.crop_name(L['canvas'], lb, '_eng')))
            # the pixel-hash guard would refuse this Japanese-as-English crop first (the "collection crop refusals"
            # below test that); step it aside so the check the name says, "English picture differs from the
            # Japanese one in every word", is the one that raises
            guard = props.check_crop
            props.check_crop = lambda _name, a: a
            try:
                must_raise('lettering %s: English texture without lettering' % k, lambda: props.lettering_alpha(tmp, k),
                           expect='is the same in the English and Japanese pictures')
            finally:
                props.check_crop = guard
        # a row fill whose inner columns miss the face: refused, not filled from nothing
        for p in [q for q in props.PICTURES if q.get('row_fill')][:1]:
            _d, gq, palq = fan_picture(dumpdir, p)
            xs = [x for x, _y in p['face']]
            q = dict(p, row_fill=(max(xs) + 3, max(xs) + 6))
            must_raise('%s: row fill outside the face' % p['name'], lambda: props.redraw(q, gq, palq, dumpdir),
                       expect='has no inner face column')
        # an unknown fill mode: refused, not silently voted
        for p in [q for q in props.PICTURES if q.get('fill')][:1]:
            _d, gq, palq = fan_picture(dumpdir, p)
            q = dict(p, fill='nearst')
            must_raise('%s: unknown fill mode' % p['name'], lambda: props.redraw(q, gq, palq, dumpdir),
                       expect="unknown fill 'nearst'")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('detector')
    print(props_detect.run(rom_path, dumpdir))
    # the control: the detector on the fan's own containers (the base ROM's) must flag every sign
    for line in props_detect.control(dumpdir):
        print('  ' + line)
    # plants on the built ROM: every band, row strip and single pixel that restores old lettering the build
    # changed must be flagged, on every sign; bands and strips with none are counted as skipped
    rom_b = open(rom_path, 'rb').read()
    res = plants(rom_b, dumpdir)
    if sorted(res) != sorted(props_detect.LIMITS):
        raise SystemExit('FAILED: the plants did not cover every sign')
    for name, rows in res.items():
        parts = []
        for kind in ('band', 'strip', 'pixel'):
            rk = [r for r in rows if r[0] == kind]
            planted = [r for r in rk if r[2] is not None]
            bad = [r for r in planted if not r[2]]
            if bad or (kind != 'pixel' and not planted):
                raise SystemExit('FAILED: %s %s plants pass: %s' % (name, kind, bad[:3] or 'none planted'))
            parts.append('%s %d flagged / %d skipped' % (kind, len(planted), len(rk) - len(planted)))
        print('  %-24s %s' % (name, ', '.join(parts)))
    # the icons' dark Safety put back whole, the red 1st! left removed: flagged
    import choice_strips as cs
    from bufcheck import rom_file as _rf
    for e in sorted(props_detect.ICONS):
        name = 'nurse_idcom%d_dark' % e
        fc = props_detect._read(dumpdir, 'ds_fan', 'com/idcom.bin')
        jc = props_detect._read(dumpdir, 'ds_jp', 'com/idcom.bin')
        g, m = props_detect.icon_mask(e, fc, jc, 'dark')
        kept, n, exact = props_detect.check_icon(e, fc, jc, _rf(rom_b, 'com/idcom.bin'), 'dark',
                                                 edit=lambda g_, n_, m=m: np.where(m, g_, n_))
        if not props_detect.flagged(name, kept, exact):
            raise SystemExit('FAILED: %s with the dark Safety put back passes (%.4f)' % (name, kept))
        print('  %-24s dark Safety put back, red removed: %.4f, flagged' % (name, kept))
    # and it must not take its lettering from the code it checks
    import inspect
    src = inspect.getsource(props_detect)
    for word in ('props.redraw', 'props_bust', 'info['):
        if word in src.split('def _boxmask')[1]:
            raise SystemExit('FAILED: the detector calls %s' % word)
    # Collection crops that are not the ones fitted: every English crop replaced by the German one, and the
    # nurse's atlas parts shifted by 6 and by 17 pixels, must be refused by the pixel hash
    import props_bust as pbu
    print('collection crop refusals')
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(props.cache_dir(dumpdir), props.cache_dir(tmp))
        for n in os.listdir(props.cache_dir(tmp)):
            if n.endswith('_eng.png'):
                shutil.copy(os.path.join(props.cache_dir(tmp), n[:-8] + '_ger.png'), os.path.join(props.cache_dir(tmp), n))
        for name in ('permit_upcut408', 'plaque_upcut400', 'circus_mapbg30'):
            p = [q for q in props.PICTURES if q['name'] == name][0]
            _d, gq, palq = fan_picture(dumpdir, p)
            must_raise('%s with the German crops as English' % name, lambda: props.redraw(p, gq, palq, tmp),
                       expect='pixel hash differs')
        fan_b0 = open(os.path.join(dumpdir, 'ds_fan', 'com', 'bustup.bin'), 'rb').read()
        g264 = pbu.GROUPS[264][0]
        name = pbu.crop_name(g264[1], g264[2], pbu.hd_box(g264))
        for dx in (6, 17):
            shutil.rmtree(pbu.cache_dir(tmp), ignore_errors=True)
            shutil.copytree(pbu.cache_dir(dumpdir), pbu.cache_dir(tmp))
            pth = os.path.join(pbu.cache_dir(tmp), name)
            a = np.asarray(Image.open(pth).convert('RGBA'))
            Image.fromarray(np.roll(a, dx, axis=1), 'RGBA').save(pth)
            must_raise('nurse atlas part of bustup 264 shifted %d px' % dx, lambda: pbu.patch_container(fan_b0, tmp),
                       expect='pixel hash differs')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # the nurse's cap (tools/props_bust.py)
    print('nurse cap refusals')
    fan_b = open(os.path.join(dumpdir, 'ds_fan', 'com', 'bustup.bin'), 'rb').read()
    fan_i = open(os.path.join(dumpdir, 'ds_fan', 'com', 'idcom.bin'), 'rb').read()
    t = props.table(fan_b)
    ext = props.extents(t, len(fan_b))
    dec = props.entry_decoded(fan_b, 264)[0]
    cells, mapping, start, tiles = pbu.parts(dec)
    bad = bytearray(dec)
    bad[start + int(np.nonzero(tiles)[0][0])] ^= 1
    st = lz11.compress(bytes(bad))
    a, b = ext[264]
    badc = bytearray(fan_b)
    badc[a:b] = st + bytes(b - a - len(st))
    must_raise('bustup 264 one tile byte off the fan\'s', lambda: pbu.patch_container(bytes(badc), dumpdir),
               expect="is not the fan's sprite")
    saved = pbu.GROUPS[264]
    try:
        pbu.GROUPS[264] = saved[:1]
        must_raise('bustup 264 with a cell no group lists', lambda: pbu.patch_container(fan_b, dumpdir),
                   expect='the groups do not list each of its 17 cells once')
        pbu.GROUPS[264] = [(saved[0][0],) + tuple(saved[0][1:3]) + (saved[0][3] + 3.0, saved[0][4]) + (saved[0][5],)] + saved[1:]
        must_raise('bustup 264 atlas moved three pixels (no crop for it)', lambda: pbu.patch_container(fan_b, dumpdir),
                   expect='chrBust21b_000_eng_o6_472_-18_889_326.png is missing')
    finally:
        pbu.GROUPS[264] = saved
    tmp = tempfile.mkdtemp()
    try:
        must_raise('nurse atlas crops missing', lambda: pbu.patch_container(fan_b, tmp),
                   expect='chrBust21b_000_eng_o6_455_-18_872_326.png is missing')
        must_raise('nurse icon texture missing', lambda: pbu.patch_icons(fan_i, tmp),
                   expect='cast21d_00_l_eng_flipped.png is missing')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('all refusals raised')


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:3]))
