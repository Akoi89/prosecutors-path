# -*- coding: utf-8 -*-
"""Tests for tools/city_labels.py (Capcom's wording on the city map, the cross-section room label and the 50th floor strip).
    python tools/test_city_labels.py <fan rom> [dump folder]

The input of step 7f is made here: the fan's ROM with the room names and the Bigg Building step applied (what the
build holds when step 7f starts), so the test does not depend on any built ROM. (The old form, a built ROM first and
the fan's ROM second, is still accepted; the built ROM is not read, since a ROM from after step 7f cannot be used.) Checks that the pass
is deterministic, writes only inside the erase masks and the new lettering, keeps the lettering that stays, and
that it refuses a picture whose old labels are not the fan's, textures that do not register, a flat band that is
not flat, a face that lacks a letter, and (with --any-rom) leaves the ROM untouched. Prints each refusal; raises
if anything that should be refused is accepted.
"""
import os
import sys
import shutil
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import city_labels as cl
import city_patches as cp
import bigg_building as bb
import bigg_ground as bgd
import room_names as rn
import gfx_views as gv
from nitro import nclr
from choice_strips import Idlocal, rom_file


def must_raise(name, fn, expect):
    """fn must raise; its message must contain `expect` (so a test meant for one guard cannot pass because another
    guard fired first)."""
    try:
        fn()
    except (cl.CityError, bgd.GroundError, cp.PatchError, SystemExit) as e:
        if expect not in str(e):
            raise SystemExit('FAILED: %s raised for another reason (wanted %r): %s' % (name, expect, e))
        print('  RAISED  %-52s %s' % (name, str(e)[:110]))
        return
    raise SystemExit('FAILED: %s was accepted' % name)


def main():
    files = [a for a in sys.argv[1:] if os.path.isfile(a)]
    rest = [a for a in sys.argv[1:] if not os.path.isfile(a)]
    if not files:
        raise SystemExit('usage: test_city_labels.py <fan rom> [dump folder]')
    fan = open(files[-1], 'rb').read()
    if len(files) > 1:
        print('note: %s is not read; the pre-7f state is built from the fan ROM %s' % (files[0], files[-1]))
    dump = rest[0] if rest else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dump')
    rom, _changed = rn.apply_to_rom(fan, dump)
    rom, changed = bb.apply_to_rom(rom, dump)
    if not changed:
        raise SystemExit('FAILED: could not build the state before step 7f (room names + Bigg Building)')
    up, fan_up = rom_file(rom, 'jpn/upcut_local.bin'), rom_file(fan, 'jpn/upcut_local.bin')
    idb, fan_id = rom_file(rom, 'jpn/idlocal.bin'), rom_file(fan, 'jpn/idlocal.bin')
    face = bb.map_face_fixed()
    V1, V2 = bgd.load_textures(dump, 1), bgd.load_textures(dump, 2)
    V = {264: V1, 280: V2}
    print('clean run')
    new_up, info = cl.patch_upcut(up, fan_up, dump, face, V)
    new_up2, _ = cl.patch_upcut(up, fan_up, dump, face, V)
    new_id, iinfo = cl.patch_idlocal(idb, fan_id)
    new_id2, _ = cl.patch_idlocal(idb, fan_id)
    if new_up != new_up2 or new_id != new_id2:
        raise SystemExit('FAILED: two runs differ')
    print('  deterministic; written px %s; stored %s' % (info['written'], {e: v for e, v in info['stored'].items()}))
    old, newi = Idlocal(up), Idlocal(new_up)
    for e in range(old.n):
        same = old.blob(e) == newi.blob(e)
        if same == (e in info['written']):
            raise SystemExit('FAILED: upcut_local entry %d %s' % (e, 'unchanged but expected to change' if same else 'changed'))
    for e in info['map']:
        gi = info['map'][e]['ground']
        print('  map %d: erase mask %d px, %d changed; registration error %.1f (one pixel shifts %.1f to %.1f); %d visible px share a grown Capcom pixel (at most %.2f of their footprint), %d bridged'
              % (e, info['map'][e]['mask'], info['map'][e]['changed'], gi['mean_err'], min(gi['shifts'].values()), max(gi['shifts'].values()),
                 gi['n_grown_touching'], max(gi['grown_share'] or [0]), gi['bridged']))
    # lettering that stays is the picture's: Sunshine Harbor / Coliseum and the tower label
    for e in cl.MAP_ENTRIES:
        a, b = gv.raw_grid(old.blob(e)), gv.raw_grid(newi.blob(e))
        for window, n, name, on in cl.KEPT:
            if e not in on:
                continue
            x0, x1, y0, y1 = window
            if not (a[y0:y1 + 1, x0:x1 + 1] == b[y0:y1 + 1, x0:x1 + 1]).all():
                raise SystemExit('FAILED: %s changed on map %d' % (name, e))
        if not (a[96:128, 70:130] == b[96:128, 70:130]).all():
            raise SystemExit('FAILED: the tower label changed on map %d' % e)
    print('  Sunshine Harbor, Sunshine Coliseum and the tower label are the fan\'s / step 7d\'s, pixel for pixel')
    # strip: only entry 328, only the tail
    oi, ni = Idlocal(idb), Idlocal(new_id)
    ch = [e for e in range(oi.n) if oi.blob(e) != ni.blob(e)]
    if ch != [328]:
        raise SystemExit('FAILED: idlocal entries changed: %s' % ch)
    print('  idlocal: only entry 328 changed; tail %s -> %s' % (iinfo[328]['old'], iinfo[328]['new']))

    # the highlight patches (cutobj_local 18)
    co = rom_file(rom, 'jpn/cutobj_local.bin')
    fan_idl = Idlocal(fan_up)
    fan_maps = {e: gv.raw_grid(fan_idl.blob(e)) for e in cl.MAP_ENTRIES}
    ground = {e: (info['map'][e]['ground_only'], info['map'][e]['pal']) for e in cl.MAP_ENTRIES}
    new_co, cinfo, (c0, c1, cpal) = cp.patch_cutobj(co, dump, face, ground, fan_maps)
    new_co2, _i, _c = cp.patch_cutobj(co, dump, face, ground, fan_maps)
    if new_co != new_co2:
        raise SystemExit('FAILED: two patch runs differ')
    oc, nc = Idlocal(co), Idlocal(new_co)
    chc = [e for e in range(oc.n) if oc.blob(e) != nc.blob(e)]
    if chc != [18]:
        raise SystemExit('FAILED: cutobj_local entries changed: %s' % chc)
    print('  cutobj_local: only entry 18 changed (%d tile pixels, %d cells differ by %d pixels, stored %s)' % (
        cinfo['written'], cinfo['cells'], cinfo['cell_pixels'], cinfo['stored'][18]))
    for k, v in cinfo['patches'].items():
        print('  patch %-24s erase mask %d (%d soft pixels outside the ring), label %d px, exemplars by mismatch %s' % (
            k, v['mask'], v['specks'], v['label'], v['reconstruct']['exemplar']))

    print('refusals')
    e = 264
    blob = old.blob(e)
    g0 = gv.raw_grid(blob)
    pal = nclr(old.blob(e + 1))
    pal = pal + [(255, 0, 255)] * (256 - len(pal))
    g = g0.copy()
    ys, xs = np.nonzero(g[28:52, 130:192] == 0)
    g[28 + ys[0], 130 + xs[0]] = 28
    must_raise('city hall label with one ink pixel gone', lambda: cl.relabel_map(g, pal, e, face, V1, {}), 'ink pixels in')
    g = g0.copy()
    ys, xs = np.nonzero(g[56:78, 183:243] == 28)
    g[56 + ys[0], 183 + xs[0]] = 33
    must_raise('a halo pixel of the old label is not the halo', lambda: cl.relabel_map(g, pal, e, face, V1, {}), 'are not the halo')
    must_raise('map textures upside down', lambda: cl.relabel_map(g0, pal, e, face, V1[:, ::-1], {}), 'does not register')
    must_raise('map textures shifted a pixel', lambda: cl.relabel_map(g0, pal, e, face, np.roll(V1, 8, axis=2), {}), 'does not register')
    f2 = bb.map_face_fixed()
    del f2.g['k']
    must_raise('face without a k ("Daybreak")', lambda: cl.relabel_map(g0, pal, e, f2, V1, {}), "the face has no 'k'")
    must_raise('picture of the wrong size', lambda: cl.relabel_map(g0[:190], pal, e, face, V1, {}), 'expected 192x256')
    # the patches
    fm = dict(fan_maps)
    g = fm[264].copy()
    ys, xs = np.nonzero(g[56:78, 183:243] == 0)
    g[56 + ys[0], 183 + xs[0]] = 28
    fm[264] = g
    must_raise('the fan map label under a patch with one ink pixel gone', lambda: cp.patch_cutobj(co, dump, face, ground, fm),
               'ink pixels in')
    fm = dict(fan_maps)
    g = fm[264].copy()
    L = [l for l in cl.MAP_LABELS if l['name'] == 'waste center'][0]
    ink = cl._old_ink(g, L)
    bx0, bx1, by0, by1 = L['box']
    p = next((x, y) for (x, y) in sorted(ink) if bx0 < x < bx1 and by0 < y < by1)
    q = next((x, y) for y in range(by0 + 1, by1) for x in range(bx0 + 1, bx1) if (x, y) not in ink)
    g[p[1], p[0]], g[q[1], q[0]] = cl.HALO, cl.INK          # same ink count and box, one pixel moved
    fm[264] = g
    must_raise('patch label is not the map label (a map pixel moved)', lambda: cp.patch_cutobj(co, dump, face, ground, fm),
               "the patch's old label is not the map's old label")
    must_raise('map ground missing', lambda: cp.patch_cutobj(co, dump, face, {}, fan_maps), 'no map ground')
    # the cross-section band
    e = 244
    gr = gv.raw_grid(old.blob(e))
    g = gr.copy()
    g[100, 100] = 6
    must_raise('room band with a stray pixel', lambda: cl.relabel_room(g, e, face, {}), 'is not flat')
    g = gr.copy()
    ys, xs = np.nonzero(g[86:102, 78:178] == 1)
    g[86 + ys[0], 78 + xs[0]] = 3
    must_raise('room label with one ink pixel gone', lambda: cl.relabel_room(g, e, face, {}), 'ink pixels in')
    f3 = bb.map_face_fixed()
    del f3.g['C']
    must_raise('face without a C ("Committee")', lambda: cl.relabel_room(gr, e, f3, {}), "the face has no 'C'")
    # the strip
    f4 = bb.faces_for(rn.Source(Idlocal(fan_id)))['strip']
    del f4.g['p']
    must_raise('strip face without a p (no b)', lambda: cl.strip_face(f4), "the strip face has no 'p'")
    # the hash guards on what the step reads
    from choice_strips import rebuild
    odd = bytearray(old.blob(264))
    odd[-1] ^= 1
    must_raise('upcut_local 264 is not what step 7d leaves', lambda: cl.patch_upcut(rebuild(up, {264: bytes(odd)}, lz=(264,)), fan_up, dump, face, V),
               'is not what the Bigg Building step leaves')
    odd = bytearray(Idlocal(fan_up).blob(280))
    odd[-1] ^= 1
    must_raise("the fan's upcut_local 280 changed", lambda: cl.patch_upcut(up, rebuild(fan_up, {280: bytes(odd)}, lz=(280,)), dump, face, V),
               'is not the one this routine was proven on')
    odd = bytearray(Idlocal(idb).blob(328))
    odd[-1] ^= 1
    must_raise('idlocal 328 is not what step 7d leaves', lambda: cl.patch_idlocal(rebuild(idb, {328: bytes(odd)}, lz=(328,)), fan_id),
               'is not what the Bigg Building step leaves')
    odd = bytearray(Idlocal(co).blob(18))
    odd[-1] ^= 1
    must_raise("cutobj_local 18 is not the fan's", lambda: cp.patch_cutobj(rebuild(co, {18: bytes(odd)}, lz=(18,)), dump, face, ground, fan_maps),
               "is not the fan's")
    tmp = tempfile.mkdtemp(prefix='city_test_')
    try:
        from PIL import Image
        d0 = os.path.join(tmp, 'dump0')
        shutil.copytree(os.path.join(dump, 'title', 'bigg_map'), os.path.join(d0, 'title', 'bigg_map'))
        pth = os.path.join(d0, 'title', 'bigg_map', 'cut04_03e_kor.png')
        im = np.asarray(Image.open(pth).convert('RGB')).copy()
        im[500, 900, 1] ^= 1
        Image.fromarray(im).save(pth)
        must_raise('a map texture with one value changed', lambda: bgd.load_textures(d0, 2), 'is not the Collection picture')
        d = os.path.join(tmp, 'dump')
        shutil.copytree(os.path.join(dump, 'title', 'bigg_map'), os.path.join(d, 'title', 'bigg_map'))
        os.remove(os.path.join(d, 'title', 'bigg_map', 'cut04_010_fre.png'))
        os.makedirs(os.path.join(d, 'ds_fan', 'jpn'))
        shutil.copy(os.path.join(dump, 'ds_fan', 'jpn', 'upcut_local.bin'), os.path.join(d, 'ds_fan', 'jpn'))
        shutil.copy(os.path.join(dump, 'ds_fan', 'jpn', 'idlocal.bin'), os.path.join(d, 'ds_fan', 'jpn'))
        must_raise('one language texture missing', lambda: cl.apply_to_rom(rom, d), 'is missing')
        r2, changed = cl.apply_to_rom(rom, d, any_rom=True)
        if changed or r2 != rom:
            raise SystemExit('FAILED: --any-rom changed the ROM')
        print('  --any-rom: the missing texture leaves the ROM untouched')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('all refusals raised, clean run passed')


if __name__ == '__main__':
    main()
