# -*- coding: utf-8 -*-
"""Tests for tools/newspaper.py (item_pics class 'newspaper', upcut_local entries 2, 6 and 20, and class 'newsicon', idcom icon 137).
Run from the port folder:
    python tools/test_newspaper.py [dump folder]

Needs dump/ds_fan/jpn/upcut_local.bin, dump/ds_fan/com/idcom.bin and the Collection textures cut00_003(_eng), cut00_005(_eng) under
dump/title/items/ and itm00_002_00_l_eng under dump/title/idcom/ (a build without --skip-extract makes them). Checks that the page is redrawn in exactly the declared boxes, that the
result is deterministic, that the picture keeps the fan's decoded size and a stored size no larger than the fan's, that
every guard (the fan's entry and palette, Capcom's texture, the baked patch's own hash and the fan pixels it was made
over, the declared boxes) raises on a foreign input, and that a patch can be swapped by packing a new one.
Raises on any failure.
"""
import os
import sys
import importlib
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
import item_pics as P
import newspaper as N
import choice_strips as cs
from lz11 import decompress
from nitro import nclr

ENTRY = 2
EXPECT = {'masthead': 1772, 'tag': 506, 'headline': 3114}
EXPECT_PATCH = 2223
EXPECT_TOTAL = 7615
# the other pages: entry -> (changed pixels per piece, changed pixels in the last patch box or None, total)
OTHERS = {6: ({'masthead': 2403}, None, 2403), 20: ({}, 2035, 2035)}
ICON_EXPECT = {'masthead': 146, 'headline': 195}      # idcom 137: changed pixels per box, 341 in all


def must_raise(name, fn, expect):
    try:
        fn()
    except P.ItemError as e:
        if expect not in str(e):
            raise SystemExit('FAILED: %s raised for another reason (wanted %r): %s' % (name, expect, e))
        print('  RAISED  %-52s %s' % (name, str(e)[:90]))
        return
    raise SystemExit('FAILED: %s was accepted' % name)


def check(cond, what):
    if not cond:
        raise SystemExit('FAILED: ' + what)
    print('  ok      ' + what)


def main(argv):
    dump = argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(HERE), 'dump')
    fan_up = open(os.path.join(dump, 'ds_fan', 'jpn', 'upcut_local.bin'), 'rb').read()
    idl = cs.Idlocal(fan_up)
    gfx, palb = P._content(idl, ENTRY), P._content(idl, ENTRY + 1)
    grid = P.pic_grid(gfx)
    pal = np.array(nclr(palb), np.float64)
    spec = P.NEWSPAPERS[ENTRY]
    tex = P.load_texture(dump, spec['texture'])

    print('the morphology the lettering is cut with')
    check(N.ellipse_kernel(5) == [(-2, 0), (-1, 2), (0, 2), (1, 2), (2, 0)], 'the 5 x 5 ellipse is the plus-with-corners-cut shape')
    x = np.zeros((20, 20), np.float32)
    x[10, 10] = 1
    d = N.dilate_ellipse(x, 5)
    check(int(d.sum()) == 17 and d[8, 10] == 1 and d[8, 8] == 0, 'a dot dilated by the 5 x 5 ellipse covers its 17 pixels')
    check(np.array_equal(N.close_ellipse(d, 5), N.close_ellipse(N.close_ellipse(d, 5), 5)), 'closing is idempotent')
    m = np.zeros((9, 9), bool)
    m[4, 4] = True
    check(int(N.grow(m, 2).sum()) == 25 and not N.grow(m, 1)[1, 1], 'grow(2) of a dot is 5 x 5, grow(1) 3 x 3')

    print('the redraw')
    new = N.paint_news(grid, pal, tex, spec)
    check(new.shape == grid.shape and new.dtype == np.uint8, 'same shape and dtype as the fan\'s grid')
    check(np.array_equal(new, N.paint_news(grid, pal, tex, spec)), 'two runs give the same pixels')
    diff = new != grid
    boxes = {pc['name']: pc['box'] for pc in spec['pieces']}
    got = {k: int(diff[b[1]:b[3], b[0]:b[2]].sum()) for k, b in boxes.items()}
    check(got == EXPECT, 'changed pixels per piece %r' % (got,))
    pb = N.boxes_of(spec)[-1]
    check(int(diff[pb[1]:pb[3], pb[0]:pb[2]].sum()) == EXPECT_PATCH, 'the patch box %r changes %d pixels (got %d)' % (pb, EXPECT_PATCH, int(diff[pb[1]:pb[3], pb[0]:pb[2]].sum())))
    check(int(diff.sum()) == EXPECT_TOTAL, '%d pixels change in total (got %d)' % (EXPECT_TOTAL, int(diff.sum())))
    keep = np.ones_like(diff)
    for b in N.boxes_of(spec):
        keep[b[1]:b[3], b[0]:b[2]] = False
    check(np.array_equal(new[keep], grid[keep]), 'every pixel outside the named boxes is the fan\'s')
    check(int(new.max()) < len(pal) and int(new.min()) > 0, 'all indices are in the palette and index 0 is unused')

    print('the container')
    out, res = P.patch_upcut(fan_up, fan_up, None, ('newspaper',), dump)
    dec, stored, fstored, px = res[ENTRY]
    check(list(res) == sorted(P.NEWSPAPERS), 'exactly the newspaper pages %r are rewritten' % (sorted(P.NEWSPAPERS),))
    check(dec == len(gfx), 'decoded size is the fan\'s (%d)' % dec)
    check(stored <= fstored, 'stored %d bytes, the fan\'s entry holds %d' % (stored, fstored))
    check(px == EXPECT_TOTAL, 'the container reports %d changed pixels' % px)
    back = cs.Idlocal(out)
    check(P._content(back, ENTRY + 1) == palb, 'the palette entry is untouched')
    check(np.array_equal(P.pic_grid(P._content(back, ENTRY)), new), 'the entry reads back as painted')
    check(len(decompress(out[P._extents_of(out)[ENTRY][0]:P._extents_of(out)[ENTRY][1]])) == len(gfx), 'the stored stream is real LZ11 of that size')

    print('the guards')
    other = bytearray(gfx)
    other[-100] ^= 1
    fake = cs.rebuild(fan_up, {ENTRY: bytes(other)}, lz=(ENTRY,))
    must_raise('a foreign graphics entry', lambda: P.patch_upcut(fake, fan_up, None, ('newspaper',), dump), "is not the fan's picture")
    bad = bytearray(palb)
    bad[-3] ^= 1
    fake = cs.rebuild(fan_up, {ENTRY + 1: bytes(bad)}, lz=(ENTRY + 1,))
    must_raise('a foreign palette entry', lambda: P.patch_upcut(fake, fan_up, None, ('newspaper',), dump), "is not the fan's picture")
    odd = grid.copy()
    odd[80, 20] = 1 if odd[80, 20] != 1 else 2
    must_raise('a picture whose patch box is not the fan\'s pixels', lambda: N.paint_news(odd, pal, tex, spec), 'different picture')
    other_tex = tex.copy()
    other_tex[300:310, 400:410] = 0
    must_raise('a texture of another Collection build', lambda: _load_changed(dump, spec['texture'], other_tex), 'is not the Collection build')
    narrow = dict(spec, pieces=tuple(dict(pc, box=(pc['box'][0], pc['box'][1], pc['box'][2], 70)) if pc['name'] == 'headline' else pc
                                     for pc in spec['pieces']))
    narrow_diff = (N.paint_news(grid, pal, tex, narrow) != grid)
    check(not narrow_diff[70:75].any() and narrow_diff[60:70].any(), 'a headline box ending at row 70 leaves rows 70 to 74 the fan\'s (changes are clipped to the box)')
    taller = dict(spec, pieces=tuple(dict(pc, box=(6, 40, 253, 80), mask=dict(pc['mask'], box=(6, 40, 253, 80))) if pc['name'] == 'headline' else pc for pc in spec['pieces']))
    must_raise('a box taller than the rows the paper is rebuilt for', lambda: N.paint_news(grid, pal, tex, taller),
               'reaches outside the rows')

    print('swapping the patch')
    with tempfile.TemporaryDirectory() as td:
        sys.path.insert(0, td)
        try:
            x0, y0, x1, y1 = N.boxes_of(spec)[-1]
            mine = new.copy()
            mine[y0:y1, x0:x1] = 7
            N.pack(mine, (x0, y0, x1, y1), grid, os.path.join(td, 'newspaper_patch_test.py'))
            swapped = N.paint_news(grid, pal, tex, dict(spec, patches=('newspaper_patch_test',)))
            check(bool((swapped[y0:y1, x0:x1] == 7).all()), 'a packed patch replaces the box')
            outside = np.ones_like(swapped, bool)
            outside[y0:y1, x0:x1] = False
            check(np.array_equal(swapped[outside], new[outside]), 'and nothing outside it moves')
            mod = importlib.import_module('newspaper_patch_test')
            mod.SHA = '0' * 64
            must_raise('a patch whose data does not match its sha', lambda: N.paint_news(grid, pal, tex, dict(spec, patches=('newspaper_patch_test',))),
                       'own sha256')
        finally:
            sys.path.remove(td)
            sys.modules.pop('newspaper_patch_test', None)
    others(dump, fan_up, idl)
    icon(dump)
    print('\nnewspaper tests passed')
    return 0


def others(dump, fan_up, idl):
    """Entries 6 (the lettering drawn from Capcom's texture, paper by the `median` kind) and 20 (one baked block, no texture)."""
    for entry, (per_piece, patch_px, total) in sorted(OTHERS.items()):
        print('entry %d' % entry)
        spec = P.NEWSPAPERS[entry]
        gfx, palb = P._content(idl, entry), P._content(idl, entry + 1)
        grid = P.pic_grid(gfx)
        pal = np.array(nclr(palb), np.float64)
        tex = P.load_texture(dump, spec['texture']) if spec['texture'] else None
        new = N.paint_news(grid, pal, tex, spec)
        check(np.array_equal(new, N.paint_news(grid, pal, tex, spec)), 'two runs give the same pixels')
        diff = new != grid
        got = {pc['name']: int(diff[pc['box'][1]:pc['box'][3], pc['box'][0]:pc['box'][2]].sum()) for pc in spec['pieces']}
        check(got == per_piece, 'changed pixels per piece %r' % (got,))
        if patch_px is not None:
            pb = N.boxes_of(spec)[-1]
            check(int(diff[pb[1]:pb[3], pb[0]:pb[2]].sum()) == patch_px, 'the patch box %r changes %d pixels' % (pb, patch_px))
        check(int(diff.sum()) == total, '%d pixels change in total (got %d)' % (total, int(diff.sum())))
        keep = np.ones_like(diff)
        for b in N.boxes_of(spec):
            keep[b[1]:b[3], b[0]:b[2]] = False
        check(np.array_equal(new[keep], grid[keep]), 'every pixel outside the named boxes is the fan\'s')
        check(int(new.max()) < len(pal) and int(new.min()) > 0, 'all indices are in the palette and index 0 is unused')
        out, res = P.patch_upcut(fan_up, fan_up, None, ('newspaper',), dump)
        dec, stored, fstored, px = res[entry]
        check(dec == len(gfx) and stored <= fstored, 'decoded %d like the fan, stored %d of the fan\'s %d' % (dec, stored, fstored))
        back = cs.Idlocal(out)
        check(P._content(back, entry + 1) == palb and np.array_equal(P.pic_grid(P._content(back, entry)), new),
              'the palette is untouched and the entry reads back as painted')
        other = bytearray(gfx)
        other[-100] ^= 1
        fake = cs.rebuild(fan_up, {entry: bytes(other)}, lz=(entry,))
        must_raise('a foreign graphics entry', lambda: P.patch_upcut(fake, fan_up, None, ('newspaper',), dump), "is not the fan's picture")
        if spec.get('patches'):
            b = N.boxes_of(spec)[-1]
            odd = grid.copy()
            odd[b[1] + 5, b[0] + 5] = 1 if odd[b[1] + 5, b[0] + 5] != 1 else 2
            must_raise('a picture whose patch box is not the fan\'s pixels', lambda: N.paint_news(odd, pal, tex, spec), 'different picture')
        else:
            other_tex = tex.copy()
            other_tex[300:310, 400:410] = 0
            must_raise('a texture of another Collection build', lambda: _load_changed(dump, spec['texture'], other_tex), 'is not the Collection build')


def icon(dump):
    """Idcom icon 137, the newspaper icon (class 'newsicon')."""
    import idcom_icons as I
    print('icon 137')
    ic = open(os.path.join(dump, 'ds_fan', 'com', 'idcom.bin'), 'rb').read()
    spec = P.ICON_PICS[(P.IDCOM, 137)]
    ent, _n = I.entry_decoded(ic, 137)
    palb, _n = I.entry_decoded(ic, spec['pal'])
    grid = np.array(cs.grid(ent), np.uint8)
    pal = np.array(nclr(palb), np.float64)
    tex = I.load_texture(dump, spec['texture'])
    new = N.paint_icon(grid, pal, tex, spec)
    check(np.array_equal(new, N.paint_icon(grid, pal, tex, spec)), 'two runs give the same pixels')
    diff = new != grid
    got = {pc['name']: int(diff[pc['box'][1]:pc['box'][3], pc['box'][0]:pc['box'][2]].sum()) for pc in spec['pieces']}
    check(got == ICON_EXPECT and int(diff.sum()) == sum(ICON_EXPECT.values()), 'changed pixels per box %r, %d in all' % (got, int(diff.sum())))
    keep = np.ones_like(diff)
    for pc in spec['pieces']:
        b = pc['box']
        keep[b[1]:b[3], b[0]:b[2]] = False
    check(np.array_equal(new[keep], grid[keep]), 'every pixel outside the two boxes is the fan\'s')
    check(int(new.min()) > 0 and int(new.max()) < len(pal), 'indices are in the 16-colour palette and index 0 is unused')
    out, res = P.patch_icons(ic, P.IDCOM, None, ('newsicon',), None, dump)
    dec, stored, fstored, px = res[137]
    check(list(res) == [137] and px == 341, 'only icon 137 is rewritten, %d pixels' % px)
    check(dec == len(ent) and stored <= fstored, 'decoded %d like the fan, stored %d of the fan\'s %d' % (dec, stored, fstored))
    check(I.entry_decoded(out, 136)[0] == palb and np.array_equal(np.array(cs.grid(I.entry_decoded(out, 137)[0]), np.uint8), new),
          'the palette entry is untouched and the icon reads back as painted')
    check(len(out) == len(ic), 'the container keeps the fan\'s size (written in place)')
    bad = bytearray(ent)
    bad[-50] ^= 1
    t = I.table(ic)
    ext = I.extents(t, len(ic))
    from lz11 import compress
    fake = bytearray(ic)
    s = compress(bytes(bad))
    a, b = ext[137]
    fake[a:b] = s + b'\0' * (b - a - len(s))
    must_raise('a foreign icon', lambda: P.patch_icons(bytes(fake), P.IDCOM, None, ('newsicon',), None, dump), "is not the fan's")
    must_raise('no dump folder', lambda: P.patch_icons(ic, P.IDCOM, None, ('newsicon',), None, None), 'no dump folder')
    # a texture of another Collection build must be an ItemError (not idcom_icons.IconError), so --any-rom logs "NOT redrawn"
    # instead of crashing the build: change the icon's texture by one bit in a temp dump folder and run apply_to_rom on it
    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        arr = np.array(tex).astype(np.uint8)
        arr[150, 150, 0] ^= 1
        os.makedirs(I.cache_dir(td))
        Image.fromarray(arr).save(os.path.join(I.cache_dir(td), spec['texture'] + '.png'))
        must_raise('an icon texture changed by one bit', lambda: P.patch_icons(ic, P.IDCOM, None, ('newsicon',), None, td),
                   'is not the Collection build')
        os.makedirs(os.path.join(td, 'ds_fan', 'jpn'))
        with open(os.path.join(td, 'ds_fan', 'jpn', 'upcut_local.bin'), 'wb') as f:
            f.write(open(os.path.join(dump, 'ds_fan', 'jpn', 'upcut_local.bin'), 'rb').read())
        saved = (P._load_cov, cs.rom_file)
        P._load_cov = lambda d: None                       # the weight texture is not what is under test
        cs.rom_file = lambda rom, name: ic
        lines = []
        try:
            rom, done = P.apply_to_rom(b'rom', td, log=lines.append, any_rom=True, classes=('newsicon',))
            check(done is False and rom == b'rom' and any('NOT redrawn' in s for s in lines),
                  'with --any-rom that texture logs "NOT redrawn" and leaves the ROM alone (%s)' % (lines[0][:70] if lines else 'no log'))
            try:
                P.apply_to_rom(b'rom', td, log=lines.append, any_rom=False, classes=('newsicon',))
            except P.ItemError as ex:
                check('--any-rom' in str(ex), 'without --any-rom it stops with an ItemError that names the flag')
            else:
                raise SystemExit('FAILED: a changed icon texture was accepted without --any-rom')
        finally:
            P._load_cov, cs.rom_file = saved


def _load_changed(dump, name, arr):
    """load_texture on a copy of the cached PNG with some pixels changed (written to a temp folder)."""
    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, *P.CACHE))
        Image.fromarray(arr.astype(np.uint8)).save(os.path.join(td, *P.CACHE, name + '.png'))
        return P.load_texture(td, name)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
