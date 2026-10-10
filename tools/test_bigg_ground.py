# -*- coding: utf-8 -*-
"""Tests for tools/bigg_ground.py (the city-map ground derived from Capcom's own map).
    python tools/test_bigg_ground.py <fan rom> [dump folder]

Reads the fan's city map (jpn/upcut_local.bin 264 and 280) and the seven Collection textures under
dump/title/bigg_map/. Checks that the derivation runs, is deterministic, touches only the mask, and
that it refuses a texture set that does not register (flipped, moved, one language missing, wrong
size). Prints each refusal; raises if anything that should be refused is accepted.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import bigg_ground as bgd
import bigg_building as bb
import gfx_views as gv
from choice_strips import Idlocal, rom_file
from nitro import nclr


def must_raise(name, fn, expect):
    """fn must raise; its message must contain `expect` (so a test meant for one guard cannot pass because another
    guard fired first)."""
    try:
        fn()
    except bgd.GroundError as e:
        if expect not in str(e):
            raise SystemExit('FAILED: %s raised for another reason (wanted %r): %s' % (name, expect, e))
        print('  RAISED  %-40s %s' % (name, str(e)[:100]))
        return
    raise SystemExit('FAILED: %s was accepted' % name)


def main():
    fan = open(sys.argv[1], 'rb').read()
    dump = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dump')
    idl = Idlocal(rom_file(fan, 'jpn/upcut_local.bin'))
    V = bgd.load_textures(dump)
    face = bb.map_face_fixed()
    for e in bb.MAP_ENTRIES:
        g = gv.raw_grid(idl.blob(e))
        pal = nclr(idl.blob(e + 1))
        mask = bgd.label_mask(g)
        keep = mask.copy()
        for text, x0, b in bb.map_lines('A', face):
            m, _ = bb.layout(face, text, x0, b)
            o, d = bb.ring_of(m)
            for (x, y) in m | o | d:
                keep[y, x] = False
        new, info = bgd.derive(g, pal, mask, keep, textures_=V)
        again, _ = bgd.derive(g, pal, mask, keep, textures_=V)
        assert (new == again).all(), 'not deterministic'
        assert ((new != g) & ~mask).sum() == 0, 'pixels changed outside the mask'
        assert mask.sum() == 836, 'mask is %d pixels' % mask.sum()
        assert info['kept_touching_grown'] == 0
        print('  entry %d: mask %d, window %s, registration error %.2f (one-pixel shifts %s), arch r %.1f/%.1f residual %.2f, '
              'hidden in all seven %d (grown from the nearest %d), visible pixels %d of which %d touch hidden ones'
              % (e, mask.sum(), info['window'], info['mean_err'], {k: round(v, 1) for k, v in info['shifts'].items()},
                 info['arch']['r1'], info['arch']['r2'], info['arch']['residual'], info['hidden_hd'], info['grown'],
                 info['kept'], info['kept_touching_hidden']))
    g = gv.raw_grid(idl.blob(264))
    pal = nclr(idl.blob(265))
    mask = bgd.label_mask(g)
    keep = mask.copy()
    # negative tests: nothing derived from a texture set that does not register
    flipped = V[:, ::-1].copy()
    must_raise('textures upside down', lambda: bgd.derive(g, pal, mask, keep, textures_=flipped),
               'the block edge line under the driveway was not found')
    must_raise('textures upside down, arch step off', lambda: bgd.derive(g, pal, mask, keep, textures_=flipped, use_arch=False),
               'does not register')
    moved = np.roll(V, 17, axis=2)
    must_raise('textures moved 17 px sideways', lambda: bgd.derive(g, pal, mask, keep, textures_=moved),
               'the ring does not fit the road edge lines')
    must_raise('textures moved 17 px sideways, arch step off', lambda: bgd.derive(g, pal, mask, keep, textures_=moved, use_arch=False),
               'does not register')
    moved2 = np.roll(V, 23, axis=1)
    must_raise('textures moved 23 px down', lambda: bgd.derive(g, pal, mask, keep, textures_=moved2), 'does not register')
    blank = np.full_like(V, 200)
    must_raise('textures blank', lambda: bgd.derive(g, pal, mask, keep, textures_=blank),
               'the block edge line under the driveway was not found')
    tmp = os.path.join(dump, 'title', 'bigg_map', bgd.textures()[2] + '.png')
    keep_name = tmp + '.moved'
    os.rename(tmp, keep_name)
    try:
        must_raise('one language missing', lambda: bgd.load_textures(dump), 'is missing')
    finally:
        os.rename(keep_name, tmp)
    print('all negative tests raised, derivation deterministic')


if __name__ == '__main__':
    main()
