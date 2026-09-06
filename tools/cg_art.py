# -*- coding: utf-8 -*-
"""Ship the six close-up artworks that carry lettering baked into the picture
(jpn/upcut_local.bin) with Capcom's official English names on them.

Six designs in the fan patch have English drawn into real artwork, where
txtcut.py (flat text screens) and cg_names.py (tables and the map) do not
apply: the two briefing diagrams (entries 8, 18), the cake placards (118), the
TV logo (140, plus 138 and 141-199: the same screen as the camera pulls back),
the movie poster (260) and the magazine cover (268).

Unlike every other graphic in this port, these are not composed at build time.
They were prepared once, outside the build (2026-09-05), from Capcom's own
Collection pictures and the fan patch's DS pictures, reviewed at DS size, and
ship as finished 256x192 pictures in tools/cg_art_final/. The build pastes
them verbatim. The 60 zoom frames are derived here from the TV master: each
frame's screen glass is the master scaled into the rectangle the frame's
registration gives (tools/cg_art_reg.json, from rig/cg_register.py), pasted
over the fan frame, and softened to match the fan frame's own sharpness.

Each picture owns its 256-colour palette, so every entry is re-quantised and
both the RGCN tiles and the RLCN palette are replaced. Index 0 is kept black
(the fan's convention); the 61 TV entries share one palette slot (139) and are
quantised together.

    build(src_upcut, dumpdir, outdir [, only])  -> (path, repl, log)
    python tools/cg_art.py IN_upcut_local.bin DUMPDIR OUTDIR [--only 118,8] [--rom in.nds out.nds]

Runs AFTER cg_names.py on the same container. Needs nothing from the
Collection (required() is empty); extract() is a no-op kept for the caller.
"""
import sys, os, struct, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nitro import ncgr, nclr, _sections
from title_text import repack
from txtcut import table, write_gfx, W, H
from PIL import Image, ImageFilter, ImageDraw
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FINAL_DIR = os.path.join(HERE, 'cg_art_final')
REG_JSON = os.path.join(HERE, 'cg_art_reg.json')
FINAL = {8: '008.png', 18: '018.png', 118: '118.png', 140: '140.png', 260: '260.png', 268: '268.png'}
TV_MASTER = 140
TV_FRAMES = [138] + list(range(141, 200))
# The TV's screen glass in Capcom's 1920x1080 picture: exactly the window
# frame 140 shows (its registration), confirmed on the in-room frame 138
# where the glass edge sits at DS (36,27)-(219,163).
SCREEN = (449, 154, 1478, 926)


def required(dumpdir):
    return []


def extract(bdir, dumpdir):
    return None


def final_files():
    return [os.path.join(FINAL_DIR, f) for f in FINAL.values()]


# ---------------------------------------------------------------- containers

def decode(gfx, palb):
    """RGCN + RLCN -> RGB image and the palette list."""
    pal = nclr(palb)
    data, bpp, cnt, tw, th = ncgr(gfx)
    assert bpp == 8, 'expected 8bpp'
    im = Image.new('P', (W, H))
    px = im.load()
    for t in range(cnt):
        bx, by = (t % (W // 8)) * 8, (t // (W // 8)) * 8
        blk = data[t * 64:(t + 1) * 64]
        for y in range(8):
            for x in range(8):
                px[bx + x, by + y] = blk[y * 8 + x]
    flat = [c for rgb in pal for c in rgb]
    im.putpalette(flat + [0] * (768 - len(flat)))
    return im.convert('RGB'), pal


def write_pal(palb, colours):
    """Replace the TTLP colour data of an RLCN with the given RGB list (BGR555)."""
    p, size, body = _sections(palb)[b'TTLP']
    dsize = struct.unpack_from('<I', body, 8)[0]
    assert len(colours) * 2 <= dsize, (len(colours), dsize)
    raw = bytearray(dsize)
    for i, (r, g, b) in enumerate(colours):
        v = (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)
        struct.pack_into('<H', raw, i * 2, v)
    out = bytearray(palb)
    start = p + 8 + 16
    out[start:start + dsize] = raw
    return bytes(out)


def palette_of(E, entry):
    """Most entries carry their palette in the next slot; the TV zoom frames
    140-199 share the one after 138 (slot 139)."""
    return entry + 1 if E[entry + 1][:4] == b'RLCN' else 139


MASTER_WEIGHT = 8    # the shipped TV master counts this many times when its shared palette is chosen


def encode_group(E, entries, images):
    """Quantise pictures that share one palette slot together: 255 colours
    plus black at index 0, snapped to what BGR555 can hold. The palette is
    chosen on a sheet where the shipped TV master is repeated, so the picture
    a player looks at longest keeps its colours best."""
    reps = [MASTER_WEIGHT if e == TV_MASTER and len(entries) > 1 else 1 for e in entries]
    sheet = Image.new('RGB', (W, H * sum(reps)))
    y = 0
    for im, n in zip(images, reps):
        for _ in range(n):
            sheet.paste(im, (0, y)); y += H
    q = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    qpal = q.getpalette()[:255 * 3]
    cols = [tuple(qpal[i:i + 3]) for i in range(0, len(qpal), 3)]
    cols = [((r >> 3) * 33 >> 2, (g >> 3) * 33 >> 2, (b >> 3) * 33 >> 2) for r, g, b in cols]
    pal = [(0, 0, 0)] + cols
    pal += [(0, 0, 0)] * (256 - len(pal))
    # map every picture to the snapped palette by nearest colour
    plt = Image.new('P', (1, 1)); flat = [c for rgb in pal for c in rgb]; plt.putpalette(flat)
    out = {}
    for entry, im in zip(entries, images):
        idx = im.quantize(palette=plt, dither=Image.Dither.NONE)
        out[entry] = write_gfx(E[entry], idx)
    pslot = palette_of(E, entries[0])
    out[pslot] = write_pal(E[pslot], pal)
    return out, pal


def preview(gfx, palb, path, scale=3):
    im, _ = decode(gfx, palb)
    im.resize((W * scale, H * scale), Image.NEAREST).save(path)
    return im


# ---------------------------------------------------------------- pictures

def final_picture(entry):
    im = Image.open(os.path.join(FINAL_DIR, FINAL[entry])).convert('RGB')
    assert im.size == (W, H), (entry, im.size)
    return im


_TV = {}


def tv_reg(entry):
    """[s, ox, oy, blur, ncc]: DS pixel (x, y) of this frame sits at official
    (ox + s*x, oy + s*y) in cut02_037. From rig/cg_register.py."""
    if not _TV:
        _TV.update(json.load(open(REG_JSON)))
    return _TV[str(entry)]


def screen_box(entry):
    s, ox, oy, blur, ncc = tv_reg(entry)
    return ((SCREEN[0] - ox) / s, (SCREEN[1] - oy) / s, (SCREEN[2] - ox) / s, (SCREEN[3] - oy) / s)


def sharpness(im, box):
    a = np.array(im.convert('L').crop(box)).astype(float)
    return float(np.abs(np.diff(a, axis=1)).mean())


def tv_frame(entry, fan, master, log):
    """One zoom frame: the master scaled into this frame's screen glass over
    the fan frame; softened by the radius that brings the glass area closest
    to the fan frame's own sharpness there (the fan's frames are softer as
    the camera pulls back)."""
    x0, y0, x1, y1 = screen_box(entry)
    ix0, iy0 = int(round(x0)), int(round(y0))
    ix1, iy1 = int(round(x1)), int(round(y1))
    w, h = ix1 - ix0, iy1 - iy0
    glass = master.resize((w, h), Image.LANCZOS)
    box = (max(0, ix0), max(0, iy0), min(W, ix1), min(H, iy1))
    target = sharpness(fan, box)
    best = None
    for r in (0.0, 0.3, 0.5, 0.7, 0.9, 1.1, 1.3):
        pic = fan.copy()
        g = glass.filter(ImageFilter.GaussianBlur(r)) if r else glass
        pic.paste(g, (ix0, iy0))
        d = abs(sharpness(pic, box) - target)
        if best is None or d < best[0]:
            best = (d, r, pic)
    log.append('entry %d: TV frame, glass (%d,%d)-(%d,%d), blur %.1f (sharpness target %.1f)'
               % (entry, ix0, iy0, ix1, iy1, best[1], target))
    return best[2]


# ---------------------------------------------------------------- build

def build(src, dumpdir, outdir, only=None, jp_src=None):
    data = open(src, 'rb').read()
    E = table(data)
    repl, log = {}, []
    os.makedirs(outdir, exist_ok=True)
    groups = {}          # palette slot -> [(entry, rgb)]
    master = final_picture(TV_MASTER)
    for entry in sorted(list(FINAL) + TV_FRAMES):
        if only and entry not in only:
            continue
        gfx = E[entry]
        pslot = palette_of(E, entry)
        assert gfx[:4] == b'RGCN' and E[pslot][:4] == b'RLCN', entry
        if entry in FINAL:
            rgb = final_picture(entry)
            log.append('entry %d: shipped picture %s' % (entry, FINAL[entry]))
        else:
            fan, _ = decode(gfx, E[pslot])
            rgb = tv_frame(entry, fan, master, log)
        rgb.save(os.path.join(outdir, 'cg_art_%03d_rgb.png' % entry))
        groups.setdefault(pslot, []).append((entry, rgb))
    for pslot, items in sorted(groups.items()):
        entries = [e for e, _ in items]
        got, pal = encode_group(E, entries, [im for _, im in items])
        repl.update(got)
        for entry in entries:
            preview(got[entry], got[pslot], os.path.join(outdir, 'cg_art_%03d_preview3x.png' % entry))
        log.append('palette %d: %d colours for entries %s' % (pslot, len(set(pal)), entries))
    new = repack(data, repl)
    out = os.path.join(outdir, 'upcut_local.bin')
    open(out, 'wb').write(new)
    return out, repl, log


PIECES = {e: None for e in list(FINAL) + TV_FRAMES}   # what the build reports on


if __name__ == '__main__':
    src, dumpdir, outdir = sys.argv[1:4]
    only = None
    if '--only' in sys.argv:
        only = {int(x) for x in sys.argv[sys.argv.index('--only') + 1].split(',')}
    out, repl, log = build(src, dumpdir, outdir, only)
    print('\n'.join(log))
    if '--rom' in sys.argv:
        from title_logo import splice
        i = sys.argv.index('--rom')
        rom = splice(open(sys.argv[i + 1], 'rb').read(), 'jpn/upcut_local.bin', open(out, 'rb').read())
        open(sys.argv[i + 2], 'wb').write(rom)
        print('wrote', sys.argv[i + 2])
