# -*- coding: utf-8 -*-
"""Re-letter the close-up artwork that carries fan character names baked into
the picture (jpn/upcut_local.bin), using Capcom's own English versions of the
same pictures from the player's Collection.

Six designs in the fan patch have English lettering drawn into real artwork,
where txtcut.py (flat text screens) and cg_names.py (tables and the map) do not
apply: the two briefing diagrams (8, 18), the cake placards (118), the TV logo
(140, plus 138 and 141-199 which are the same screen zooming out), the movie
poster (260) and the magazine cover (268). For four of them the Collection has
its own English artwork (Texture2D cut02_01e_eng, cut02_037_eng, cut04_004_eng,
cut04_017_eng in the gk2_upcutlocal bundle), so the lettering is Capcom's,
scaled down onto the DS composition. The diagrams have no counterpart; there the
shorter official names are cut from the fan's own letters.

Each picture owns its 256-colour palette, so the result is quantised per entry
and both the RGCN tiles and the RLCN palette are replaced.

    extract(bundle_dir, dumpdir)   pull the four official pictures into dump/title/cut/
    build(src_upcut, dumpdir, outdir [, only])  -> (path, repl, log)
    python tools/cg_art.py IN_upcut_local.bin DUMPDIR OUTDIR [--only 118,8] [--rom in.nds out.nds]

Runs AFTER cg_names.py on the same container.
"""
import sys, os, struct, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nitro import ncgr, nclr, _sections
from title_text import repack
from txtcut import table, write_gfx, W, H
from PIL import Image, ImageFilter, ImageDraw

BUNDLE_PREFIX = 'gk2_upcutlocal_assets_all_'
OFFICIAL = {
    'cut02_01e_eng': 118,    # cake placards
    'cut02_037_eng': 140,    # TV logo
    'cut04_004_eng': 260,    # movie poster
    'cut04_017_eng': 268,    # magazine cover
    # the textless Japanese versions of the last three: a clean plate for the
    # DS composition once registered (see register())
    'cut02_037': 140,
    'cut04_004': 260,
    'cut04_017': 268,
}
ZOOM = list(range(141, 200))     # the TV logo zoom-out frames, plus 138 (in-room view)


def cut_dir(dumpdir):
    return os.path.join(dumpdir, 'title', 'cut')


def required(dumpdir):
    return [os.path.join(cut_dir(dumpdir), n + '.png') for n in OFFICIAL]


def extract(bdir, dumpdir):
    import UnityPy
    hits = [p for p in glob.glob(os.path.join(bdir, '*.bundle'))
            if os.path.basename(p).startswith(BUNDLE_PREFIX)]
    if not hits:
        raise SystemExit('no bundle starting with %r in %s' % (BUNDLE_PREFIX, bdir))
    os.makedirs(cut_dir(dumpdir), exist_ok=True)
    want = set(OFFICIAL)
    env = UnityPy.load(hits[0])
    for o in env.objects:
        if o.type.name == 'Texture2D':
            d = o.read()
            if d.m_Name in want:
                d.image.convert('RGBA').save(os.path.join(cut_dir(dumpdir), d.m_Name + '.png'))
                want.discard(d.m_Name)
    if want:
        raise SystemExit('not found in %s: %s' % (os.path.basename(hits[0]), sorted(want)))
    return cut_dir(dumpdir)


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


def encode(gfx, palb, rgb, keep0_black=True):
    """Quantise a 256x192 RGB picture to 256 colours and write it into the entry
    pair. Index 0 is kept black (the fan's convention on these screens)."""
    assert rgb.size == (W, H)
    n = 255 if keep0_black else 256
    q = rgb.quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    qpal = q.getpalette()[:n * 3]
    cols = [tuple(qpal[i:i + 3]) for i in range(0, len(qpal), 3)]
    # snap to what BGR555 can hold, so the preview equals the DS output
    cols = [((r >> 3) * 33 >> 2, (g >> 3) * 33 >> 2, (b >> 3) * 33 >> 2) for r, g, b in cols]
    idx = Image.new('P', (W, H))
    src, dst = q.load(), idx.load()
    shift = 1 if keep0_black else 0
    for y in range(H):
        for x in range(W):
            dst[x, y] = src[x, y] + shift
    pal = ([(0, 0, 0)] if keep0_black else []) + cols
    pal += [(0, 0, 0)] * (256 - len(pal))
    return write_gfx(gfx, idx), write_pal(palb, pal), pal


def preview(gfx, palb, path, scale=3):
    im, _ = decode(gfx, palb)
    im.resize((W * scale, H * scale), Image.NEAREST).save(path)
    return im


# ---------------------------------------------------------------- helpers

def official(dumpdir, name):
    return Image.open(os.path.join(cut_dir(dumpdir), name + '.png')).convert('RGBA')


def fit_crop(src, box, size):
    """Crop box from src (in src pixels) and Lanczos-scale to size."""
    return src.crop(box).resize(size, Image.LANCZOS)


def paste_rgba(base, layer, xy):
    base.paste(layer, xy, layer)


def patch_from(dst, src, box, offset=(0, 0)):
    """Copy box from src to dst (same-size pictures), optionally shifted."""
    x0, y0, x1, y1 = box
    dst.paste(src.crop(box), (x0 + offset[0], y0 + offset[1]))


# ---------------------------------------------------------------- pieces
# Each compose_NNN(fan_rgb, jp_rgb, dumpdir, log) -> RGB 256x192. They are
# written one at a time and reviewed in game; see G:/Claude/GK2/cg_art/.

PIECES = {}


def piece(entry):
    def reg(fn):
        PIECES[entry] = fn
        return fn
    return reg


import numpy as np
import math


def red_mask(a, thr=20):
    return (a[:, :, 0] - np.maximum(a[:, :, 1], a[:, :, 2])) > thr


def grow(m, r=1):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def diffuse(arr, holes, iters=200):
    """Fill `holes` of an HxWx3 float array from the neighbours, iteratively."""
    out = arr.copy(); known = ~holes; holes = holes.copy()
    for _ in range(iters):
        if not holes.any():
            break
        acc = np.zeros_like(out); cnt = np.zeros(holes.shape)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            k = np.roll(known, (dy, dx), (0, 1)); v = np.roll(out, (dy, dx), (0, 1))
            acc[k] += v[k]; cnt += k
        fill = holes & (cnt > 0)
        out[fill] = acc[fill] / cnt[fill][:, None]
        known |= fill; holes &= ~fill
    return out


def clean_plate(fan, jp):
    """Background with every red handwriting stroke removed: the Japanese
    original where the fan wrote and Capcom's artist did not, and a diffusion
    fill where both wrote in the same place."""
    fa, ja = np.array(fan).astype(float), np.array(jp).astype(float)
    fr, jr = grow(red_mask(fa.astype(int)), 1), grow(red_mask(ja.astype(int)), 1)
    out = fa.copy()
    use_jp = fr & ~jr
    out[use_jp] = ja[use_jp]
    holes = fr & jr
    known = ~holes
    for _ in range(64):
        if not holes.any():
            break
        acc = np.zeros_like(out); cnt = np.zeros(holes.shape)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            k = np.roll(known, (dy, dx), (0, 1)); v = np.roll(out, (dy, dx), (0, 1))
            acc[k] += v[k]; cnt += k
        fill = holes & (cnt > 0)
        out[fill] = acc[fill] / cnt[fill][:, None]
        known |= fill; holes &= ~fill
    return out


def uv(shape, deg):
    """Baseline-aligned coordinates for handwriting written at `deg` degrees
    (positive = running down to the right)."""
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return xx * c + yy * s, -xx * s + yy * c, (c, s)


class Handwriting(object):
    """Erase and slide fragments of a red handwritten line on one picture."""

    def __init__(self, fan, jp, deg):
        self.fa = np.array(fan).astype(int)
        self.out = self.fa.astype(float).copy()
        # a build has only the fan ROM: the plate under the strokes is a
        # diffusion fill from the paper around them (jp, when given, is used
        # only for the rig's own comparisons)
        self.plate = clean_plate(fan, jp) if jp is not None else diffuse(self.out, grow(red_mask(self.fa, 20), 1))
        self.U, self.V, (self.c, self.s) = uv(self.fa.shape, deg)
        self.red = grow(red_mask(self.fa, 20), 1)

    def box(self, u0, u1, v0, v1):
        return (self.U >= u0) & (self.U < u1) & (self.V >= v0) & (self.V < v1)

    def erase(self, u0, u1, v0, v1):
        m = self.box(u0, u1, v0, v1) & self.red
        self.out[m] = self.plate[m]

    def erase_xy(self, x0, y0, x1, y1):
        m = np.zeros(self.red.shape, bool); m[y0:y1 + 1, x0:x1 + 1] = True
        m &= self.red
        self.out[m] = self.plate[m]

    def slide(self, u0, u1, v0, v1, along):
        """Move the strokes inside the box `along` units down the baseline
        (negative = towards the line start)."""
        m = self.box(u0, u1, v0, v1) & self.red
        dx, dy = int(round(along * self.c)), int(round(along * self.s))
        src = self.fa[m].astype(float)
        ys, xs = np.where(m)
        self.out[m] = self.plate[m]
        self.out[ys + dy, xs + dx] = src
        return dx, dy

    def image(self):
        return Image.fromarray(np.clip(self.out + 0.5, 0, 255).astype(np.uint8), 'RGB')


LEGEND_BG = (247, 247, 247)


def legend(im, log, entry):
    """The printed legend box: Rooke -> Rook, Knightley -> Knight by erasing
    the trailing letters to the box's paper colour (same layout on 8 and 18)."""
    d = ImageDraw.Draw(im)
    d.rectangle([41, 29, 46, 37], fill=LEGEND_BG)
    d.rectangle([85, 29, 95, 38], fill=LEGEND_BG)
    log.append('entry %d: legend Rook / Knight' % entry)
    return im


@piece(8)
def compose_8(fan, jp, dumpdir, log):
    """Briefing diagram with two handwritten lines naming the agents."""
    hw = Handwriting(fan, jp, 25.4)
    # "Rooke takes / Knightley's place."  (upper right, 25 degrees)
    # letter bounds come from a red-pixel histogram along the baseline
    hw.erase(155.6, 161.5, -48, -35)                   # the e of Rooke (156-160)
    hw.slide(163, 195, -48, -35, -4.5)                  # "takes" (166-190) closes the gap
    hw.erase(157, 168, -38, -19)                        # "ley" of Knightley's (157-167)
    hw.slide(168, 206, -38, -19, -11)                   # "'s place." (169-202) closes the gap
    # "... Knightley / will lead ..." (lower line, almost level): ley is at line end
    hw.erase_xy(209, 113, 223, 127)
    im = hw.image()
    log.append('entry 8: handwriting Rook takes Knight\'s place; Knight')
    return legend(im, log, 8)


@piece(18)
def compose_18(fan, jp, dumpdir, log):
    return legend(fan.copy(), log, 18)


@piece(118)
def compose_118(fan, jp, dumpdir, log):
    """Cake placards: Capcom's three plaques (plain sans, surname only) scaled
    onto the fan's plaque rectangles. Boxes are the dark frame outlines,
    measured by dark-row/column counts on both pictures."""
    off = official(dumpdir, 'cut02_01e_eng').convert('RGB')
    out = fan.copy()
    for (fx0, fy0, fx1, fy1), (ox0, oy0, ox1, oy1), name in (
            ((27, 147, 82, 164), (395, 832, 671, 927), 'Frost'),
            ((100, 114, 154, 129), (822, 640, 1098, 728), 'Scone'),
            ((180, 149, 233, 164), (1261, 837, 1537, 925), 'Gusto')):
        w, h = fx1 - fx0 + 1, fy1 - fy0 + 1
        out.paste(off.crop((ox0, oy0, ox1 + 1, oy1 + 1)).resize((w, h), Image.LANCZOS), (fx0, fy0))
        log.append('entry 118: %s plaque %dx%d at (%d,%d)' % (name, w, h, fx0, fy0))
    return out


# Registration of the DS framing inside Capcom's 1920x1080 pictures, found by
# normalised cross-correlation of the Japanese DS picture against the textless
# official one (G:/Claude/GK2/cg_art/register_fine.json): DS pixel (x, y) sits
# at official (ox + s*x, oy + s*y). The poster is recomposed art and only
# registers approximately (ncc 0.57), so it is used there for sky fills only.
REG = {
    140: (4.02, 449, 154),   # ncc 0.95
    260: (5.60, 124, 0),     # ncc 0.57, approximate
    268: (5.63, 239, 0),     # ncc 0.91
}


def warp(off, entry):
    s, ox, oy = REG[entry]
    return off.crop((ox, oy, ox + W * s, oy + H * s)).resize((W, H), Image.LANCZOS)


def text_layer(eng, jp, box, thr=24, soft=48, close=3):
    """Capcom's lettering as an RGBA layer: the English picture where it differs
    from the textless Japanese one, alpha ramping with the difference so the
    anti-aliased edges come along."""
    e = np.array(eng.convert('RGB').crop(box)).astype(int)
    j = np.array(jp.convert('RGB').crop(box)).astype(int)
    d = np.abs(e - j).max(axis=2)
    a = np.clip((d - thr) * 255 / float(soft - thr), 0, 255).astype(np.uint8)
    # close small holes where a letter's fill happens to match the background
    a = Image.fromarray(a).filter(ImageFilter.MaxFilter(close)).filter(ImageFilter.MinFilter(max(1, close - 2)))
    out = np.dstack([e.astype(np.uint8), np.array(a)])
    return Image.fromarray(out, 'RGBA')


def fit(layer, width=None, height=None):
    """Scale an RGBA layer. Colour is premultiplied by alpha before the
    resample and divided out after, otherwise the source picture's background
    colour bleeds into the shrunk letter edges as fringing."""
    w, h = layer.size
    s = width / float(w) if width is not None else height / float(h)
    size = (max(1, int(round(w * s))), max(1, int(round(h * s))))
    a = np.array(layer).astype(float)
    al = a[:, :, 3:4] / 255.0
    pre = np.dstack([a[:, :, :3] * al, a[:, :, 3:4]])
    small = np.array(Image.fromarray(np.clip(pre + 0.5, 0, 255).astype(np.uint8), 'RGBA').resize(size, Image.LANCZOS)).astype(float)
    al2 = small[:, :, 3:4] / 255.0
    rgb = np.where(al2 > 0.002, small[:, :, :3] / np.maximum(al2, 0.002), 0)
    out = np.dstack([np.clip(rgb + 0.5, 0, 255), small[:, :, 3:4]]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')


def feather_paste(base, src, box, r=3):
    """Replace box of base with the same box of src, feathered r px inward."""
    x0, y0, x1, y1 = box
    m = Image.new('L', (W, H), 0)
    ImageDraw.Draw(m).rectangle([x0, y0, x1 - 1, y1 - 1], fill=255)
    if r:
        m = m.filter(ImageFilter.GaussianBlur(r))
    base.paste(src, (0, 0), m)


BAND_SCALE = 1.25


@piece(268)
def compose_268(fan, jp, dumpdir, log):
    """Magazine cover: the fan art keeps everything except the headline band
    and the poster thumbnail, which come from Capcom's English cover through
    the registered warp (same composition, ncc 0.91)."""
    full = official(dumpdir, 'cut04_017_eng').convert('RGB')
    eng = warp(full, 268)
    out = fan.copy()
    # first clear the fan's own headline and its red star: their ink (dark
    # text, red star) inside the headline area, refilled from Capcom's page,
    # which is plain white there. The hair below right is left alone.
    fa = np.array(fan).astype(int)
    ink = (fa.max(axis=2) < 120) | (fa[:, :, 0] - np.minimum(fa[:, :, 1], fa[:, :, 2]) > 30)   # dark text, red star and its pink rim
    area = np.zeros(ink.shape, bool); area[1:64, 28:186] = True; area[38:64, 148:186] = False
    m0 = grow(ink & area, 1)
    out.paste(eng, (0, 0), Image.fromarray((m0 * 255).astype(np.uint8)))
    # red band: Capcom's headline band is set for 1080p and its sub-headline
    # is unreadable at a straight 5.6x reduction, so the band is enlarged by
    # BAND_SCALE about its own centre (it stays on the page) and pasted through
    # a hard-edged mask of its own red pixels (+2 px for the white lettering
    # and the rim); a feathered rectangle blurred the hair next to it
    s_, ox, oy = REG[268]
    bx0, by0, bx1, by1 = 48, 8, 180, 50                     # band bbox in DS px
    crop = full.crop((ox + bx0 * s_, oy + by0 * s_, ox + bx1 * s_, oy + by1 * s_))
    bw, bh = int(round((bx1 - bx0) * BAND_SCALE)), int(round((by1 - by0) * BAND_SCALE))
    band = crop.resize((bw, bh), Image.LANCZOS)
    cx, cy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
    px, py = int(round(cx - bw / 2.0)), int(round(cy - bh / 2.0))
    layer = Image.new('RGB', (W, H)); layer.paste(band, (px, py))
    a = np.array(layer).astype(int)
    red = (a[:, :, 0] > 150) & (a[:, :, 1] < 110) & (a[:, :, 2] < 110)
    m = ~grow(~grow(red, 7), 6)        # closing: fills the white letters, net +1 px rim
    bg = np.abs(fa - np.array(fa[2, 2])).max(axis=2) < 10      # the flat grey backdrop behind the page
    m &= ~bg                           # never over the backdrop, only on the page
    out.paste(layer, (0, 0), Image.fromarray((m * 255).astype(np.uint8)))
    feather_paste(out, eng, (46, 108, 120, 152), 1)    # poster thumbnail
    log.append('entry 268: official headline band and thumbnail')
    return out


def clean_official(dumpdir, entry, eng_name, jp_name, tol=12):
    """The registered official picture as a plate, plus a mask of where it is
    clean: Capcom's English and Japanese versions agree there, so neither
    carries lettering at that spot."""
    e = warp(official(dumpdir, eng_name).convert('RGB'), entry)
    j = warp(official(dumpdir, jp_name).convert('RGB'), entry)
    d = np.abs(np.array(e).astype(int) - np.array(j).astype(int)).max(axis=2)
    clean = ~grow(d > tol, 2)
    return j, clean


def fill_boxes(base, plate, clean, boxes, feather=3):
    """Replace the boxes of base with plate where plate is clean, and a
    diffusion fill from the surroundings where it is not."""
    m = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(m)
    for x0, y0, x1, y1 in boxes:
        d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=255)
    region = np.array(m) > 0
    b = np.array(base).astype(float); p = np.array(plate).astype(float)
    src = b.copy()
    src[region & clean] = p[region & clean]
    src = diffuse(src, region & ~clean)
    filled = Image.fromarray(np.clip(src + 0.5, 0, 255).astype(np.uint8), 'RGB')
    mask = m.filter(ImageFilter.GaussianBlur(feather)) if feather else m
    out = base.copy()
    out.paste(filled, (0, 0), mask)
    return out


@piece(260)
def compose_260(fan, jp, dumpdir, log):
    """Movie poster: the DS composition with Capcom's three text elements
    (tagline, title logo, studio credit) lifted from the English picture and
    set into the fan's slots. The fan's four text blocks are filled from the
    registered official art where that is clean of text in both languages,
    and diffused from the surroundings where it is not."""
    eng_full = official(dumpdir, 'cut04_004_eng').convert('RGB')
    jp_full = official(dumpdir, 'cut04_004').convert('RGB')
    plate, clean = clean_official(dumpdir, 260, 'cut04_004_eng', 'cut04_004')
    out = fan.copy()
    # boxes run past the picture edge so the feather never thins at the border
    out = fill_boxes(out, plate, clean, [
        (-8, -8, 264, 33),      # THE BATTLE OF THE CENTURY! band
        (14, 33, 110, 98),      # Now... It meets its greatest rival!
        (-8, 126, 82, 176),     # A GLOBAL STUDIOS PICTURE
        (106, 101, 255, 190),   # MIGHTY MOOZILLA vs GOURDY: the fan ink's own extent, so
                                # the new logo and credit cover nearly all of the fill
    ], 2)
    tag = fit(text_layer(eng_full, jp_full, (50, 35, 1225, 150), thr=14, soft=40, close=7), width=246)
    out.paste(tag, (5, 5), tag)
    logo = fit(text_layer(eng_full, jp_full, (870, 550, 1840, 995), thr=14, soft=40, close=7), width=148)
    out.paste(logo, (105, 99), logo)
    credit = fit(text_layer(eng_full, jp_full, (1050, 995, 1670, 1060)), width=122)
    out.paste(credit, (120, 169), credit)
    log.append('entry 260: tagline %s, logo %s, credit %s' % (tag.size, logo.size, credit.size))
    return out


REG_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cg_art_reg.json')
_TV = {}


def tv_reg(entry):
    """Registration of the TV frames (138, 140-199) against cut02_037, from
    rig/cg_register.py: [s, ox, oy, blur, ncc]."""
    if not _TV:
        _TV.update(json.load(open(REG_JSON)))
    return _TV[str(entry)]


# The TV's screen glass in Capcom's picture: exactly the window frame 140 shows
# (its registration), confirmed on the in-room frame 138 where the glass edge
# sits at DS (36,27)-(219,163) = official (449,153)-(1474,915).
SCREEN = (449, 154, 1478, 926)


def compose_tv(entry, dumpdir, log, fan=None):
    """One TV frame: Capcom's English picture cropped and scaled to the DS
    framing (ncc 0.89-0.96 on every frame), softened to the DS look, and
    pasted over the fan frame inside the screen glass only, so the room around
    the TV keeps the fan's (retail DS) pixels."""
    s, ox, oy, blur, ncc = tv_reg(entry)
    eng = official(dumpdir, 'cut02_037_eng').convert('RGB')
    pic = eng.crop((ox, oy, ox + W * s, oy + H * s)).resize((W, H), Image.LANCZOS)
    if blur:
        pic = pic.filter(ImageFilter.GaussianBlur(blur))
    x0, y0 = (SCREEN[0] - ox) / s, (SCREEN[1] - oy) / s
    x1, y1 = (SCREEN[2] - ox) / s, (SCREEN[3] - oy) / s
    if fan is None or (x0 <= 0 and y0 <= 0 and x1 >= W and y1 >= H):
        out = pic; how = 'whole frame'
    else:
        out = fan.copy()
        m = Image.new('L', (W, H), 0)
        ImageDraw.Draw(m).rectangle([int(round(x0)), int(round(y0)), int(round(x1)) - 1, int(round(y1)) - 1], fill=255)
        out.paste(pic, (0, 0), m)
        how = 'screen (%d,%d)-(%d,%d)' % (round(x0), round(y0), round(x1), round(y1))
    log.append('entry %d: TV frame s=%.2f (%d,%d) blur %.1f ncc %.2f, %s' % (entry, s, ox, oy, blur, ncc, how))
    return out


def _tv_piece(entry):
    @piece(entry)
    def compose(fan, jp, dumpdir, log, entry=entry):
        return compose_tv(entry, dumpdir, log, fan)


for _e in [138] + list(range(140, 200)):
    _tv_piece(_e)


# ---------------------------------------------------------------- build

def palette_of(E, entry):
    """Most entries carry their palette in the next slot; the TV zoom frames
    140-199 share the one after 138 (slot 139)."""
    return entry + 1 if E[entry + 1][:4] == b'RLCN' else 139


def encode_group(E, entries, images):
    """Quantise several pictures that share one palette slot together."""
    sheet = Image.new('RGB', (W, H * len(images)))
    for i, im in enumerate(images):
        sheet.paste(im, (0, H * i))
    q = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    qpal = q.getpalette()[:255 * 3]
    cols = [tuple(qpal[i:i + 3]) for i in range(0, len(qpal), 3)]
    cols = [((r >> 3) * 33 >> 2, (g >> 3) * 33 >> 2, (b >> 3) * 33 >> 2) for r, g, b in cols]
    pal = [(0, 0, 0)] + cols
    pal += [(0, 0, 0)] * (256 - len(pal))
    out = {}
    src = q.load()
    for i, entry in enumerate(entries):
        idx = Image.new('P', (W, H)); dst = idx.load()
        for y in range(H):
            for x in range(W):
                dst[x, y] = src[x, y + H * i] + 1
        out[entry] = write_gfx(E[entry], idx)
    pslot = palette_of(E, entries[0])
    out[pslot] = write_pal(E[pslot], pal)
    return out, pal


def build(src, dumpdir, outdir, only=None, jp_src=None):
    data = open(src, 'rb').read()
    E = table(data)
    JP = table(open(jp_src, 'rb').read()) if jp_src else None
    repl, log = {}, []
    os.makedirs(outdir, exist_ok=True)
    groups = {}          # palette slot -> [(entry, rgb)]
    for entry, fn in sorted(PIECES.items()):
        if only and entry not in only:
            continue
        gfx = E[entry]
        pslot = palette_of(E, entry)
        assert gfx[:4] == b'RGCN' and E[pslot][:4] == b'RLCN', entry
        fan, _ = decode(gfx, E[pslot])
        jp = decode(JP[entry], JP[palette_of(JP, entry)])[0] if JP else None
        rgb = fn(fan, jp, dumpdir, log)
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


if __name__ == '__main__':
    src, dumpdir, outdir = sys.argv[1:4]
    only = None
    if '--only' in sys.argv:
        only = {int(x) for x in sys.argv[sys.argv.index('--only') + 1].split(',')}
    jp = None
    if '--jp' in sys.argv:
        jp = sys.argv[sys.argv.index('--jp') + 1]
    out, repl, log = build(src, dumpdir, outdir, only, jp)
    print('\n'.join(log))
    if '--rom' in sys.argv:
        from title_logo import splice
        i = sys.argv.index('--rom')
        rom = splice(open(sys.argv[i + 1], 'rb').read(), 'jpn/upcut_local.bin', open(out, 'rb').read())
        open(sys.argv[i + 2], 'wb').write(rom)
        print('wrote', sys.argv[i + 2])
