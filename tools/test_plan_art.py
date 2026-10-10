# -*- coding: utf-8 -*-
"""Planted-fault tests for the picture routines of tools/plan_labels.py, gallery_art.py, board_temps.py and the
detectors of tools/plan_detect.py.
    python tools/test_plan_art.py <built rom> [dump folder]
Every fault below must be refused or reported; the script raises if one is accepted."""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import plan_labels as pl
import plan_detect as pd
import gallery_art
import board_temps
from nitro import nclr
from choice_strips import Idlocal, rebuild, rom_file


def must_raise(name, exc, fn):
    try:
        fn()
    except exc as e:
        print('  RAISED  %-58s %s' % (name, str(e)[:100]))
        return
    raise SystemExit('FAILED: %s was accepted' % name)


def must_report(name, problems):
    if not problems:
        raise SystemExit('FAILED: %s was not reported' % name)
    print('  REPORTED %-57s %s' % (name, problems[0][:90]))


def main(rom_path, dumpdir='dump'):
    rom = open(rom_path, 'rb').read()
    fan_up = open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'upcut_local.bin'), 'rb').read()
    fan_id = open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'idlocal.bin'), 'rb').read()
    built_up, built_id = rom_file(rom, 'jpn/upcut_local.bin'), rom_file(rom, 'jpn/idlocal.bin')
    tab, ftab = pl.up_table(built_up), pl.up_table(fan_up)

    def with_picture(container, e, fn):
        """The upcut_local container with picture e's index grid changed by fn(grid)."""
        t = pl.up_table(container)
        g = pl.up_grid(t[e])
        fn(g)
        return rebuild(container, {e: pl.up_set(t[e], g)}, lz=(e,))

    print('clean')
    pl.plan_faces(fan_up)
    print('  plan face built from the fan file')

    print('the slash and the derived letters')
    must_raise('slash of upcut_local 40 touched in the fan file', pl.PlanError,
               lambda: pl.plan_faces(with_picture(fan_up, 40, lambda g: g.__setitem__((10, 122), 0))))
    must_raise('a pixel next to the slash inked', pl.PlanError,
               lambda: pl.plan_faces(with_picture(fan_up, 40, lambda g: g.__setitem__((10, 124), 1))))

    print('the leaflet texture (upcut_local 114)')
    tmp = tempfile.mkdtemp()
    try:
        d = os.path.join(tmp, 'dump')
        shutil.copytree(os.path.join(dumpdir, 'title', 'gallery'), os.path.join(d, 'title', 'gallery'))
        from PIL import Image
        p = os.path.join(d, 'title', 'gallery', 'cut02_010_eng.png')
        im = np.asarray(Image.open(p).convert('RGBA')).copy()
        pal114 = nclr(tab[115])
        gallery_art.picture(os.path.join(dumpdir), pal114)
        print('  clean texture accepted')
        im[500, 900, 0] ^= 1
        Image.fromarray(im).save(p)
        must_raise('texture with one channel value changed', gallery_art.GalleryError, lambda: gallery_art.picture(d, pal114))
        must_raise('texture missing', gallery_art.GalleryError, lambda: gallery_art.picture(os.path.join(tmp, 'nowhere'), pal114))
        # through the routine: the change reaches the build as a refusal
        must_raise('patch_upcut with the changed texture', pl.PlanError, lambda: pl.patch_upcut(fan_up, fan_up, dumpdir=d))
    finally:
        shutil.rmtree(tmp)

    print('the board (upcut_local 116)')
    g116 = pl.up_grid(ftab[116])
    pal116 = nclr(ftab[117])
    board_temps.patch(g116, pal116)
    print('  fan picture accepted')
    blank = g116.copy()
    blank[72:136, 100:170] = 98
    must_raise('no temperature lines in the zone', board_temps.BoardError, lambda: board_temps.patch(blank, pal116))
    half = g116.copy()
    half[72:104, 100:170] = 98
    must_raise('upper cells empty', board_temps.BoardError, lambda: board_temps.patch(half, pal116))
    must_raise('patch_upcut on another 116', pl.PlanError,
               lambda: pl.patch_upcut(with_picture(fan_up, 116, lambda g: g.__setitem__((10, 10), 1)),
                                      fan_up))

    print('room names output (idlocal 321)')
    I = Idlocal(built_id)
    odd = bytearray(I.blob(321))
    odd[-1] ^= 1
    must_raise('idlocal 321 not what room_names writes', pl.PlanError,
               lambda: pl.patch_idlocal(rebuild(fan_id, {321: bytes(odd)}, lz=(321,)), fan_id))

    print('the detectors')
    must_report('board: the fan picture (79 F, Celsius)', pd.board_check(fan_up, fan_up))
    keep_celsius = with_picture(built_up, 116, lambda g: g.__setitem__((np.s_[92:101], np.s_[106:124]), pl.up_grid(ftab[116])[92:101, 106:124]))
    must_report('board: Celsius line put back', pd.board_check(keep_celsius, fan_up))
    nine = with_picture(built_up, 116, lambda g: g.__setitem__((np.s_[86:95], np.s_[110:115]), pl.up_grid(ftab[116])[80:89, 110:115]))
    must_report('board: the old 9 put back in 78', pd.board_check(nine, fan_up))
    if pd.board_check(built_up, fan_up):
        raise SystemExit('FAILED: board detector reports the built picture: %r' % pd.board_check(built_up, fan_up))
    print('  board detector silent on the built picture')
    must_report('leaflet: the fan picture', pd.gallery_check(fan_up, fan_up, dumpdir))
    mostly = with_picture(built_up, 114, lambda g: g.__setitem__((np.s_[0:192], np.s_[0:256]), pl.up_grid(ftab[114])))
    must_report('leaflet: the fan picture back in 114', pd.gallery_check(mostly, fan_up, dumpdir))
    tweaked = with_picture(built_up, 114, lambda g: g.__setitem__((100, 100), (g[100, 100] + 1) % 256))
    must_report('leaflet: one pixel of Capcom picture changed', pd.gallery_check(tweaked, fan_up, dumpdir))
    if pd.gallery_check(built_up, fan_up, dumpdir):
        raise SystemExit('FAILED: leaflet detector reports the built picture')
    print('  leaflet detector silent on the built picture')
    # the Autumn cloud: the Palace template must find the old label in the fan's sprite and not in the built one
    fan_co = open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'cutobj_local.bin'), 'rb').read()
    templates = pd.build_templates(Idlocal(fan_id), Idlocal(open(os.path.join(dumpdir, 'ds_jp', 'jpn', 'idlocal.bin'), 'rb').read()), None, fan_up)
    words = [w for w in pl.DETECT_WORDS if w[1] == 'Palace' and w[0] == 'plan']
    for label, co, expect in (('the fan sprite', fan_co, True), ('the built sprite', rom_file(rom, 'jpn/cutobj_local.bin'), False)):
        hits = pd.scan(built_id, templates, words, Idlocal(fan_id), None, pd.sprite_pictures(co, fan_co))
        got = [h for h in hits if h[0].startswith('cutobj_local 12')]
        if bool(got) != expect:
            raise SystemExit('FAILED: Palace template on %s: %s' % (label, got))
        print('  Palace template on %s: %s' % (label, 'found' if got else 'not found'))
    print('all faults refused or reported')


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:3]))
