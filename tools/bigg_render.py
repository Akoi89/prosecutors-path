# -*- coding: utf-8 -*-
"""Before / after renders of the Bigg Building pictures, with the pictures' own palettes.

    python tools/bigg_render.py --rom NEW.nds --fan-rom FAN.nds --out DIR [--layouts]

For every picture tools/bigg_building.py changes: fan on the left, new on the right, at 1x and 4x,
cropped to the lettering with a margin; contact sheets at 2x (about ten pictures to a sheet) and the
city map in full; with --layouts the three city-map layouts (A two lines, B one line under the icon,
C one line centred in the old block) side by side with their widths and their free space.
Nothing here ships with the ROM: the images are written under --out only.
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw
import gfx_views as gv
import room_names as rn
import bigg_building as bb
from choice_strips import Idlocal, rom_file
from nitro import nclr

# (container, entry, view, [(label, crop x0, y0, x1, y1)], palette side)
ITEMS = [
    ('jpn/upcut_local.bin', 264, 'raw', [('city map', 50, 92, 150, 132)], 'after'),
    ('jpn/upcut_local.bin', 280, 'raw', [('city map (Sunshine Warehouse)', 50, 92, 150, 132)], 'after'),
    ('jpn/upcut_local.bin', 208, 'raw', [('cross-section title', 30, 0, 230, 26)], 'after'),
    ('jpn/upcut_local.bin', 244, 'raw', [('cross-section title', 30, 0, 230, 26)], 'after'),
    ('jpn/upcut_local.bin', 246, 'raw', [('cross-section title', 30, 0, 230, 26)], 'after'),
    ('jpn/upcut_local.bin', 278, 'raw', [('cross-section title', 30, 0, 230, 26)], 'after'),
    ('jpn/upcut_local.bin', 282, 'raw', [('cross-section title, two lines', 110, 0, 256, 30)], 'after'),
    ('jpn/cutobj_local.bin', 26, 'c41', [('sprite picture, title piece 1', 90, 46, 170, 68), ('sprite picture, title piece 2', 140, 0, 250, 12)], 'after'),
    ('jpn/idlocal.bin', 328, 'c1', [('place strip', 0, 0, 160, 16)], 'before'),
    ('jpn/idlocal.bin', 331, 'c1', [('place strip', 0, 0, 160, 16)], 'before'),
    ('jpn/idlocal.bin', 334, 'c1', [('place strip', 0, 0, 160, 16)], 'before'),
    ('jpn/idlocal.bin', 337, 'c1', [('place strip', 0, 0, 160, 16)], 'before'),
    ('jpn/idlocal.bin', 340, 'c1', [('place strip, two lines', 0, 0, 96, 32)], 'before'),
    ('jpn/idlocal.bin', 337, 'c0', [('map piece label', 40, 10, 110, 50)], 'before'),
    ('jpn/idlocal.bin', 340, 'c0', [('map piece label', 40, 10, 110, 50)], 'before'),
    ('jpn/idlocal.bin', 343, 'c0', [('map piece label', 40, 10, 150, 40)], 'before'),
]
# jpn/cutobj_local.bin 26 draws its picture in palette bank 15, which the file does not hold. Stand-in
# colours for the four indices the title uses (taken from the same title in jpn/upcut_local.bin 282).
STAND_IN = {1: (255, 255, 255), 15: (74, 57, 57), 12: (140, 120, 120), 8: (107, 107, 107)}


def load(rom, path):
    idl = Idlocal(rom_file(rom, path))
    return [idl.blob(e) if idl.ents[e][0] else b'' for e in range(idl.n)]


def picture(blobs, e, view, side):
    """-> (RGB array, index grid) of one view with its palette."""
    for lab, g, info in gv.entry_views(blobs, e):
        if lab == view:
            break
    else:
        raise SystemExit('entry %d has no view %s' % (e, view))
    pe, pal = gv.palette_of(blobs, e, side)
    if view == 'raw':
        pal = nclr(blobs[e + 1])
        rgb = gv.to_rgb(g, pal + [(255, 0, 255)] * (256 - len(pal)))
    else:
        rgb = gv.to_rgb(g, pal, info.get('bank'))
        if info.get('bank') is not None and (info['bank'] == 15).any() and pe is not None and len(pal) < 256:
            m = (info['bank'] == 15) & (g >= 0)
            for v in np.unique(g[m]):
                rgb[m & (g == v)] = STAND_IN.get(int(v), (int(v) * 16,) * 3)
    return rgb, g


def pair(fan_rgb, new_rgb, crop, scale, label):
    x0, y0, x1, y1 = crop
    a = fan_rgb[max(0, y0):y1, x0:x1]
    b = new_rgb[max(0, y0):y1, x0:x1]
    sep = np.full((a.shape[0], 3, 3), 255, np.uint8)
    S = np.concatenate([a, sep, b], 1)
    im = Image.fromarray(S).resize((S.shape[1] * scale, S.shape[0] * scale), Image.NEAREST)
    out = Image.new('RGB', (im.width, im.height + 16), (255, 255, 255))
    ImageDraw.Draw(out).text((2, 2), label + '   [fan | new]  %dx' % scale, fill=(0, 0, 0))
    out.paste(im, (0, 16))
    return out


def sheet(images, path, width=1500):
    x = y = rh = 0
    pos = []
    for im in images:
        if x + im.width > width:
            x, y, rh = 0, y + rh + 6, 0
        pos.append((x, y)); x += im.width + 6; rh = max(rh, im.height)
    S = Image.new('RGB', (width, y + rh), (205, 205, 205))
    for im, p in zip(images, pos):
        S.paste(im, p)
    S.save(path)


def layouts(fan_rom, new_rom_layouts, out):
    """The three city-map layouts of entry 264 with numbers."""
    face = bb.map_face_fixed()
    idl = Idlocal(rom_file(fan_rom, 'jpn/upcut_local.bin'))
    blob = idl.blob(264)
    pal = nclr(idl.blob(265)); pal = pal + [(255, 0, 255)] * (256 - len(pal))
    tex = bb.bigg_ground.load_textures(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dump'))
    g0 = gv.raw_grid(blob)
    crop = (40, 92, 160, 130)
    imgs, notes = [], []
    rgb0 = gv.to_rgb(g0, pal)
    for name in ('A', 'B', 'C'):
        info = {}
        out_blob, new = bb.patch_city_map(blob, pal, 264, face, name, info, None, tex)
        rgb = gv.to_rgb(new, pal)
        m = info['map'][264]
        # free space: columns between the label's halo and the yellow road on the left, the next dark
        # label ink on the right; rows above: the icon's white outline
        lo = min(a for _t, a, _z, _b in m['lines']) - 1
        hi = max(z for _t, _a, z, _b in m['lines']) + 1
        rows = range(min(b for _t, _a, _z, b in m['lines']) - 7, max(b for _t, _a, _z, b in m['lines']) + 3)
        road = [x for x in range(0, lo) if any(tuple(rgb0[y, x]) == tuple(pal[int(g0[y, x])]) and
                                               pal[int(g0[y, x])][0] > 230 and pal[int(g0[y, x])][1] > 200 and pal[int(g0[y, x])][2] < 90 for y in rows)]
        left = lo - (max(road) if road else 0) - 1
        dark = [x for x in range(hi + 1, 256) if any(g0[y, x] == 0 for y in rows)]
        right = (min(dark) if dark else 256) - hi - 1
        notes.append('%s: ink %d px wide (%s); %d px between its halo and the yellow road on the left, %d px to the next label on the right'
                     % (name, m['ink_width'], ', '.join('%s %d-%d' % (t, a, z) for t, a, z, b in m['lines']), left, right))
        imgs.append((name, rgb))
    parts = [('fan: Grand / Tower', rgb0)] + [('%s' % n, r) for n, r in imgs]
    x0, y0, x1, y1 = crop
    cells = []
    for lab, r in parts:
        im = Image.fromarray(r[y0:y1, x0:x1]).resize(((x1 - x0) * 4, (y1 - y0) * 4), Image.NEAREST)
        c = Image.new('RGB', (im.width, im.height + 16), (255, 255, 255))
        ImageDraw.Draw(c).text((2, 2), lab, fill=(0, 0, 0)); c.paste(im, (0, 16)); cells.append(c)
    sheet(cells, os.path.join(out, 'citymap_264_layouts_ABC_4x.png'), 980)
    open(os.path.join(out, 'citymap_264_layouts.txt'), 'w', encoding='utf-8', newline='\n').write(
        'A: two lines Bigg / Building centred where Grand / Tower sat (default)\n'
        'B: one line under the icon, at the old first line\n'
        'C: one line centred in the old two-line block\n' + '\n'.join(notes) + '\n')
    return notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', required=True)
    ap.add_argument('--fan-rom', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--layouts', action='store_true')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rom, fan = open(a.rom, 'rb').read(), open(a.fan_rom, 'rb').read()
    cache = {}
    two_x, n = [], 0
    for path, e, view, crops, side in ITEMS:
        if path not in cache:
            cache[path] = (load(fan, path), load(rom, path))
        fb, nb = cache[path]
        fr, _ = picture(fb, e, view, side)
        nr, _ = picture(nb, e, view, side)
        tag = '%s_%d_%s' % (os.path.basename(path).replace('.bin', ''), e, view)
        for k, (lab, x0, y0, x1, y1) in enumerate(crops):
            suffix = '' if len(crops) == 1 else '_%d' % (k + 1)
            for sc in (1, 4):
                pair(fr, nr, (x0, y0, x1, y1), sc, '%s %d %s' % (os.path.basename(path), e, lab)).save(
                    os.path.join(a.out, '%s%s_%dx.png' % (tag, suffix, sc)))
            two_x.append(pair(fr, nr, (x0, y0, x1, y1), 2, '%s %d %s' % (os.path.basename(path), e, lab)))
        if path == 'jpn/upcut_local.bin' and e in (264, 280):
            pair(fr, nr, (0, 0, 256, 192), 2, '%s %d city map, whole picture' % (os.path.basename(path), e)).save(
                os.path.join(a.out, '%s_whole_2x.png' % tag))
    for i in range(0, len(two_x), 8):
        sheet(two_x[i:i + 8], os.path.join(a.out, 'sheet_%02d_2x.png' % (i // 8 + 1)), 1500)
    if a.layouts:
        for n_ in layouts(fan, None, a.out):
            print(n_)


if __name__ == '__main__':
    main()
