# -*- coding: utf-8 -*-
"""Tests for tools/marker_letters.py (Capcom's letters in the round character markers of jpn/cutobj_local.bin).
    python tools/test_marker_letters.py <fan rom> [dump folder]

Reads the fan's jpn/cutobj_local.bin and the 13 textures and cell lists under dump/title/bigg_markers/.
Checks that the pass is deterministic, changes exactly the markers EXPECTED names, leaves every other marker
pixel for pixel as it was, writes exactly the letter the pass decided on, and that it refuses inputs that do
not match (a texture swapped for another entry's, a cell list with a cell missing, an OBJ without a Capcom
rectangle, a missing file, a different base ROM). Prints each refusal; raises if anything that should be
refused is accepted.
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import marker_letters as ml
import input_hashes as ih
from choice_strips import Idlocal, rom_file


def must_raise(name, fn, expect):
    """fn must raise; its message must contain `expect` (so a test meant for one guard cannot pass because another
    guard fired first)."""
    try:
        fn()
    except (ml.MarkerError, SystemExit) as e:
        if expect not in str(e):
            raise SystemExit('FAILED: %s raised for another reason (wanted %r): %s' % (name, expect, e))
        print('  RAISED  %-52s %s' % (name, str(e)[:110]))
        return
    raise SystemExit('FAILED: %s was accepted' % name)


def copy_markers(dump, tmp):
    """A scratch dump folder that holds only the marker textures and cell lists."""
    dst = os.path.join(tmp, 'dump')
    shutil.copytree(ml.cache_dir(dump), ml.cache_dir(dst))
    return dst


def main():
    fan = open(sys.argv[1], 'rb').read()
    dump = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dump')
    co = rom_file(fan, 'jpn/cutobj_local.bin')
    missing = [p for p in ml.required(dump) if not os.path.isfile(p)]
    if missing:
        raise SystemExit('missing: %s' % missing[0])
    old_blob2 = Idlocal(co).blob(2)
    print('clean run')
    new, report, per = ml.patch_cutobj(co, dump)
    new2, report2, _ = ml.patch_cutobj(co, dump)
    if new != new2 or report != report2:
        raise SystemExit('FAILED: two runs differ')
    got = ml.changed_markers(per)
    if got != ml.EXPECTED:
        raise SystemExit('FAILED: changed markers %r, expected %r' % (got, ml.EXPECTED))
    print('  deterministic; markers changed per entry:', got)
    print('  per entry:', ', '.join('%d: %d tile px, %d cells, %d cell px' % (e, r['tile_pixels'], r['cells_changed'], r['cell_pixels'])
                                    for e, r in sorted(report.items())))
    # every marker pixel: untouched unless the marker is one that changes, and then exactly the decided letter
    old_idl, new_idl = Idlocal(co), Idlocal(new)
    n_same = n_changed = 0
    for e, name in sorted(ml.NAMES.items()):
        atlas, parts = ml.load_capcom(dump, name)
        Eo = ml.Entry(old_idl.blob(e), parts)
        En = ml.Entry(new_idl.blob(e), parts)
        covered = np.zeros(Eo.idx.shape, bool)
        for m in per[e]:
            x0, x1, y0, y1 = m['box']
            sl = (slice(y0, y1 + 1), slice(x0, x1 + 1))
            covered[sl] = True
            if m['kind'] not in ('differs', 'piece'):
                if not (Eo.idx[sl] == En.idx[sl]).all() or not (Eo.bank[sl] == En.bank[sl]).all():
                    raise SystemExit('FAILED: entry %d marker %d (%s) changed' % (e, m['i'], m['kind']))
                n_same += 1
                continue
            n_changed += 1
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    o, n = int(Eo.idx[y, x]), int(En.idx[y, x])
                    want = o
                    if (x, y) in m['glyph']:
                        want = m['white_idx']
                    elif (x, y) in m['ds_letter']:
                        want = m['fill']
                    if n != want:
                        raise SystemExit('FAILED: entry %d marker %d pixel (%d,%d) is %d, expected %d' % (e, m['i'], x, y, n, want))
        # outside every circle the sheet is the fan's
        if not (Eo.idx[~covered] == En.idx[~covered]).all():
            raise SystemExit('FAILED: entry %d sheet changed outside the circles' % e)
    print('  %d markers left as they were (pixel for pixel), %d changed exactly as decided, sheets unchanged outside the circles' % (n_same, n_changed))
    # entries that are not marker entries are the fan's bytes
    for e in range(old_idl.n):
        if e not in ml.EXPECTED and old_idl.ents[e] != new_idl.ents[e] and old_idl.blob(e) != new_idl.blob(e):
            raise SystemExit('FAILED: entry %d changed' % e)
    print('  no other entry changed')

    print('refusals (the geometry guards, with the hash guards off)')
    ih.GUARD_INPUTS = False
    tmp = tempfile.mkdtemp(prefix='marker_test_')
    try:
        def swapped():
            d = copy_markers(dump, tmp + '/a')
            c = ml.cache_dir(d)
            shutil.copyfile(os.path.join(c, ml.NAMES[8] + '_eng.png'), os.path.join(c, ml.NAMES[2] + '_eng.png'))
            return d
        d = swapped()
        must_raise('texture of entry 2 replaced by entry 8\'s', lambda: ml.apply_to_rom(fan, d), 'no piece found')

        def flipped():
            from PIL import Image
            d = copy_markers(dump, tmp + '/b')
            p = os.path.join(ml.cache_dir(d), ml.NAMES[22] + '_eng.png')
            Image.open(p).transpose(Image.FLIP_TOP_BOTTOM).save(p)
            return d
        d = flipped()
        must_raise('texture of entry 22 upside down', lambda: ml.apply_to_rom(fan, d), 'the markers to change are')

        def blank():
            from PIL import Image
            d = copy_markers(dump, tmp + '/c')
            p = os.path.join(ml.cache_dir(d), ml.NAMES[16] + '_eng.png')
            Image.new('RGBA', (1440, 2880), (0, 0, 0, 0)).save(p)
            return d
        d = blank()
        must_raise('texture of entry 16 blank', lambda: ml.apply_to_rom(fan, d), 'the markers to change are')

        def small():
            from PIL import Image
            d = copy_markers(dump, tmp + '/d')
            p = os.path.join(ml.cache_dir(d), ml.NAMES[20] + '_eng.png')
            Image.open(p).resize((720, 1440)).save(p)
            return d
        d = small()
        must_raise('texture of entry 20 at half size', lambda: ml.apply_to_rom(fan, d), 'expected 1440x2880')

        def nofile():
            d = copy_markers(dump, tmp + '/e')
            os.remove(os.path.join(ml.cache_dir(d), ml.NAMES[24] + '_cells.json'))
            return d
        d = nofile()
        must_raise('cell list of entry 24 missing', lambda: ml.apply_to_rom(fan, d), 'is missing')

        def fewer():
            d = copy_markers(dump, tmp + '/f')
            p = os.path.join(ml.cache_dir(d), ml.NAMES[22] + '_cells.json')
            cells = json.load(open(p))
            json.dump(cells[:-1], open(p, 'w'))
            return d
        d = fewer()
        must_raise('cell list of entry 22 has a cell fewer', lambda: ml.apply_to_rom(fan, d), 'cell list has')

        def moved():
            d = copy_markers(dump, tmp + '/g')
            p = os.path.join(ml.cache_dir(d), ml.NAMES[22] + '_cells.json')
            cells = json.load(open(p))
            done = False
            for parts in cells:                      # one part that draws the B sprite loses its Capcom rectangle
                for q in parts:
                    if q['SrcX'] == 0 and q['SrcY'] == 0 and q['Width'] == 16 and not done:
                        q['DestX'], done = q['DestX'] + 1, True
            json.dump(cells, open(p, 'w'))
            return d
        d = moved()
        must_raise('an OBJ of the B sprite without a Capcom rectangle', lambda: ml.apply_to_rom(fan, d),
                   'that have no Capcom rectangle')

        def shared():
            d = copy_markers(dump, tmp + '/h')
            p = os.path.join(ml.cache_dir(d), ml.NAMES[22] + '_cells.json')
            cells = json.load(open(p))
            done = False
            for parts in cells:                      # one cell draws the B sprite from another rectangle of the atlas
                for q in parts:
                    if q['SrcX'] == 0 and q['SrcY'] == 0 and q['Width'] == 16 and not done:
                        q['SrcX'], done = 24, True
            json.dump(cells, open(p, 'w'))
            return d
        d = shared()
        must_raise('the B tile drawn for two different Capcom rectangles', lambda: ml.apply_to_rom(fan, d),
                   'different Capcom rectangles')
        must_raise('bundle folder without the textures', lambda: ml.apply_to_rom(fan, os.path.join(tmp, 'nothing')), 'is missing')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        ih.GUARD_INPUTS = True

    print('hash guards')
    tmp = tempfile.mkdtemp(prefix='marker_test_')
    try:
        from PIL import Image
        d = copy_markers(dump, tmp + '/p')
        pth = os.path.join(ml.cache_dir(d), ml.NAMES[24] + '_eng.png')
        im = np.asarray(Image.open(pth).convert('RGBA')).copy()
        im[2000, 700, 0] ^= 1
        Image.fromarray(im).save(pth)
        must_raise('atlas of entry 24 with one value changed', lambda: ml.apply_to_rom(fan, d), 'is not the Collection picture')
        d = copy_markers(dump, tmp + '/q')
        pth = os.path.join(ml.cache_dir(d), ml.NAMES[22] + '_cells.json')
        cells = json.load(open(pth))
        cells[0][0]['SrcX'] += 1
        json.dump(cells, open(pth, 'w'))
        must_raise('cell list of entry 22 with one value changed', lambda: ml.apply_to_rom(fan, d), 'is not the Collection picture')
        odd = bytearray(old_blob2)
        odd[-1] ^= 1
        from choice_strips import rebuild
        must_raise('fan entry 2 with one byte changed', lambda: ml.patch_cutobj(rebuild(co, {2: bytes(odd)}, lz=(2,)), dump),
                   "is not the fan's")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # --any-rom: the same inputs are tolerated as "not redrawn" and return the ROM untouched
    d = None
    tmp = tempfile.mkdtemp(prefix='marker_test_')
    try:
        d = copy_markers(dump, tmp)
        c = ml.cache_dir(d)
        shutil.copyfile(os.path.join(c, ml.NAMES[8] + '_eng.png'), os.path.join(c, ml.NAMES[2] + '_eng.png'))
        rom, changed = ml.apply_to_rom(fan, d, any_rom=True)
        if changed or rom != fan:
            raise SystemExit('FAILED: --any-rom changed the ROM')
        print('  --any-rom: a texture that does not match leaves the ROM untouched')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # the glyph stage on its own: a letter that is not a letter
    must_raise('glyph from an empty circle', lambda: ml.derive_glyph(np.zeros((111, 112)), dict(x=0, y=0, w=112, h=111), (0, 19, 4, 23)),
               'no letter in the circle')
    print('all refusals raised, clean run passed')


if __name__ == '__main__':
    main()
