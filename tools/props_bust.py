# -*- coding: utf-8 -*-
"""The nurse's cap on her character sprites: Capcom's SAFETY [pill] FIRST for the fan's Safety [pill] 1st!.

The nurse's bustup sprites (com/bustup.bin entries 252, 253, 254, 255 and 264, each an OAM cell bank
with its 256-colour tile bank, palettes 251 and 263) carry the fan's cap lettering in every frame.
The Collection draws the same sprites as packed atlases (gk2_bustup chrBust21b_000/001/008/009,
chrBust21d_000; the English textures read SAFETY [pill] FIRST), traced from the same art: each head
pose of the DS sprite is one part of an atlas, at the DS scale x 5.625.

GROUPS lists, per entry, the head poses: the cells showing that head, the atlas, its orientation
(6 = the texture upside down, as Unity stores it), the offset (ox, oy) that puts the atlas part on the
frame (frame pixel (x, y) = oriented atlas pixel (x + ox, y + oy) at DS scale, fitted offline with
template matching and a 0.2-pixel search against the head round the cap), and the frame box holding the
cap. Frame coordinates start at the entry's OAM bounds (the top-left of all its cells).

At build time, per cell: Capcom's English atlas part is area-averaged onto the frame grid; the cap band
is Capcom's light opaque region with its letters and pill filled in; Capcom's colours are mapped onto
the fan's by a robust linear fit over the head round the cap and the cap (from the group's first cell,
used for all its cells); every band pixel whose colour is not Capcom's takes the nearest of the colours
the fan's band uses; a hand in front of the cap (a large skin-coloured region) is kept; where the fan's
band reaches past Capcom's (the frontal pose), the fan's old letters there take the band's plain colour
round them. The changed pixels are written into the tile bytes that draw them; a tile byte two cells
would set differently keeps the first (logged). Only tile data changes; each entry is LZ11 again and
written in place, no larger than the fan's stored entry (com/bustup.bin was not traced).

The nurse's portrait icons (com/idcom.bin 951, 64x64, and 953, 40x40, 4 bpp, palettes 950 and 952) carry
the same cap: the Collection's icon cast21d_00_l_eng (300x300, stored upside down) is the same drawing;
ICONS gives its registration (texel = o + s * icon pixel per axis, fitted offline against the Japanese
twin cast21d_00_l) and the icon's cap is redrawn the same way, in the icon's own 16 colours.

No game pixels are stored in the repository: the atlases and the icon texture are read from the player's
own Collection install at extraction time (dump/title/props/bust/, crops of the parts only).
"""
import os, sys, glob, struct, hashlib
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import props
import props_core as pc
import lz11
from props import PropsError

S = 5.625
CONT = 'com/bustup.bin'
BUNDLE = 'gk2_bustup_assets_all'
CACHE = ('title', 'props', 'bust')
PALS = {252: 251, 253: 251, 254: 251, 255: 251, 264: 263}
THR = 40.0
MARGIN = 3                      # DS pixels of atlas kept round each box at extraction

# entry -> [(cells, atlas, orientation, ox, oy, box (x0, y0, x1, y1) in frame pixels)]
GROUPS = {
    252: [
        (tuple(range(0, 8)) + tuple(range(24, 77)) + (78,) + tuple(range(82, 110)), 'chrBust21b_000', 6, 0.0, -0.2, (84, 0, 152, 55)),
        (tuple(range(8, 24)), 'chrBust21b_000', 6, 71.8, -0.2, (77, 0, 147, 54)),
        ((77,), 'chrBust21b_000', 6, 96.6, 255.8, (82, 0, 151, 55)),
        ((79, 80, 81), 'chrBust21b_000', 6, 112.0, 327.2, (68, 0, 136, 55)),
    ],
    253: [
        (tuple(range(0, 27)), 'chrBust21d_000', 6, 34.6, 2.6, (80, 0, 149, 52)),
        ((27, 30, 31, 32, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46), 'chrBust21b_001', 6, -23.6, 455.8, (71, 6, 135, 55)),
        ((28, 29, 33, 34, 47, 48, 49, 50, 51), 'chrBust21b_001', 6, 79.8, 455.6, (73, 7, 141, 57)),
    ],
    254: [
        ((0, 1), 'chrBust21b_008', 6, -8.0, -0.2, (92, 0, 160, 55)),
        ((2, 3, 4), 'chrBust21b_008', 6, 0.6, 184.2, (95, 0, 162, 58)),
        ((5, 6, 7), 'chrBust21b_008', 6, -31.4, 352.0, (100, 0, 175, 57)),
    ],
    255: [
        (tuple(range(0, 9)), 'chrBust21b_009', 6, -64.0, -0.2, (124, 0, 192, 55)),
        ((9,), 'chrBust21b_009', 6, -56.6, 400.0, (152, 11, 207, 56)),
        ((10,), 'chrBust21b_009', 6, -64.6, 392.0, (160, 19, 215, 64)),
        ((11, 15), 'chrBust21b_009', 6, -72.6, 376.0, (168, 35, 223, 80)),
        ((12,), 'chrBust21b_009', 6, -88.6, 336.0, (184, 75, 239, 120)),
        ((13,), 'chrBust21b_009', 6, -104.6, 256.0, (200, 155, 255, 200)),
    ],
    264: [
        (tuple(range(0, 8)), 'chrBust21b_000', 6, 40.0, -0.2, (44, 0, 112, 55)),
        (tuple(range(8, 17)), 'chrBust21d_000', 6, 87.8, -0.4, (26, 0, 96, 56)),
    ],
}
# the portrait icons: entry -> (palette entry, texture, (sx, sy, ox, oy))
ICON_CONT = 'com/idcom.bin'
ICON_BUNDLE = 'gk2_idcom_assets_all'
ICONS = {
    951: (950, 'cast21d_00_l', (4.6975, 4.6975, -0.3, -0.1)),
    953: (952, 'cast21d_00_l', (7.52, 7.53, -0.6, -0.1)),
}
ICON_SHA = {
    951: ('a718fb0dd21db3c8671c6cfff3fe33a0a35b798f9510ef2812e135b5f5e0831c',
          '4c12baa6dba7667d1434f6585c1195f25502c2a1b8b33efe8e956921a30278da'),
    953: ('c0aa28e7a6b5196835cc678971bb3a6da368b1eb1eab130e92bc0dc90690aa43',
          '4c12baa6dba7667d1434f6585c1195f25502c2a1b8b33efe8e956921a30278da'),
}
ICON_PAD = 40

# cells that show no cap (empty, or the doctor alone): left as they are
NO_CAP = {254: (8,), 255: (14,)}

# sha256 of the fan's decoded entries (the sprite and its palette): nothing else is redrawn
FAN_SHA = {
    252: ('89dc5d1742609a539780de0b3e03d06f48ad4494bbc7b2b8eafebe3fdfe7f642',
          '80b9ffb007ea15991ca3238e591f3539e843c458435bcf3efcd6479f109cbc3a'),
    253: ('aa28fa7fffade195bdd6e62616b9f075923b230d83c7c569d0c1392d5a76545e',
          '80b9ffb007ea15991ca3238e591f3539e843c458435bcf3efcd6479f109cbc3a'),
    254: ('a658934c35f862b48fdcbc8ae4610eb95ca9129107f86943693ce27bda89f05d',
          '80b9ffb007ea15991ca3238e591f3539e843c458435bcf3efcd6479f109cbc3a'),
    255: ('0deccd76c9e6f1c7f2f3e285255301a7a4e05794a62b5392cd2aca642c40622f',
          '80b9ffb007ea15991ca3238e591f3539e843c458435bcf3efcd6479f109cbc3a'),
    264: ('96d7ef699aa049f8e75b55d83e3b519947f46ccbfa88768fe61f1e140a2e2f6b',
          '80b9ffb007ea15991ca3238e591f3539e843c458435bcf3efcd6479f109cbc3a'),
}


class BustError(PropsError):
    pass


# ---------------------------------------------------------------- the sprite entry

def parts(dec):
    """-> (cells, mapping, tile byte offset in dec, tile bytes)"""
    from ncer import ncer
    o = struct.unpack_from('<3I', dec, 0)
    if dec[o[2]:o[2] + 4] != b'RGCN' or dec[o[2] + 16:o[2] + 20] != b'RAHC':
        raise BustError('bustup entry: no RGCN at the third offset')
    cells, mapping = ncer(dec[o[0]:])
    body = o[2] + 24
    h, w, fmt = struct.unpack_from('<HHI', dec, body)
    if fmt != 4:
        raise BustError('bustup entry: expected an 8 bpp tile bank')
    dsize, doff = struct.unpack_from('<II', dec, body + 16)
    start = body + doff
    return cells, mapping, start, np.frombuffer(dec[start:start + dsize], np.uint8)


def bounds(cells):
    objs = [ob for c in cells for ob in c]
    return (min(ob['x'] for ob in objs), min(ob['y'] for ob in objs),
            max(ob['x'] + ob['w'] for ob in objs), max(ob['y'] + ob['h'] for ob in objs))


def cell_map(cell, mapping, tiles, bnd):
    """frame (H, W) of tile byte offsets of the topmost opaque pixel (-1: none)."""
    bx0, by0, bx1, by1 = bnd
    H, W = by1 - by0, bx1 - bx0
    boundary = max(1, (32 << (mapping & 3)) // 64)
    src = np.full((H, W), -1, np.int64)
    for ob in reversed(cell):
        tw, th = ob['w'] // 8, ob['h'] // 8
        start = ob['tile'] * boundary
        for ty in range(th):
            for tx in range(tw):
                off = (start + ty * tw + tx) * 64
                if off + 64 > len(tiles):
                    continue
                blk = tiles[off:off + 64].reshape(8, 8)
                yy, xx = np.nonzero(blk)
                sx = (tw * 8 - 1) - (tx * 8 + xx) if ob['hflip'] else tx * 8 + xx
                sy = (th * 8 - 1) - (ty * 8 + yy) if ob['vflip'] else ty * 8 + yy
                X, Y = ob['x'] - bx0 + sx, ob['y'] - by0 + sy
                ok = (X >= 0) & (X < W) & (Y >= 0) & (Y < H)
                src[Y[ok], X[ok]] = off + yy[ok] * 8 + xx[ok]
    return src


# ---------------------------------------------------------------- Capcom's atlases

# sha256 of each extracted atlas part and icon texture's decoded pixels ("(h, w, 4):" + RGBA bytes)
CROP_SHA = {
    'chrBust21b_000_eng_o6_455_-18_872_326.png': '3fae01b72d8c98b5d4343fcdc75782046bc4080992c7d503a8e8ff4de1106b28',
    'chrBust21b_000_eng_o6_820_-18_1248_320.png': '388ccabb6de79e8b2576b7093d3201b1ce1abc7de6fa216ce1a1075f0c252ab4',
    'chrBust21b_000_eng_o6_987_1422_1410_1766.png': '3cebac4a0e6abd05dea1382ff91147b587cbe70a892ec7566bfdef88e1723b31',
    'chrBust21b_000_eng_o6_995_1823_1412_2167.png': '1bf3ba7f377c0f89e09e798c8e73c17476461f4fa5ada698b7de6f80b90208c7',
    'chrBust21b_001_eng_o6_249_2580_644_2891.png': 'c0cadc103e48b053400a7172e1dae8acf51125e6fa09397a4439e4cecb30ab8e',
    'chrBust21b_001_eng_o6_842_2585_1259_2901.png': '60903cd5faf26cc11c482a761106eea0bb20d9ff2bbadb46554cc2cec3db4f5f',
    'chrBust21b_008_eng_o6_368_1963_825_2318.png': '29367cfcbc2960e8f0f2982e178792adf215bb30c3a9ea0878a894ccdcd108d5',
    'chrBust21b_008_eng_o6_455_-18_872_326.png': '0da2a4f6145f492e36f5fd18355030f51bd037fd445ba00aca82176ca6592ecc',
    'chrBust21b_008_eng_o6_520_1019_932_1380.png': 'd55d39dfd83901a0559183bbf52a965eaa6c7bcecc0a2baa0244e13935cc6815',
    'chrBust21b_009_eng_o6_320_-18_737_326.png': 'e9d5cd1c1220aaacfc34f246ede6aaa36503d6acb822a81f6f34fe3e01e08779',
    'chrBust21b_009_eng_o6_519_2295_863_2582.png': '69feee6dda8c8dd58beb62fd7681003a13299854d5de71308e3e8d11b86521f9',
    'chrBust21d_000_eng_o6_623_-20_1051_330.png': 'a8919a340c9cc71578426f9b35a90c7c246b04992c10b16d037196069f4b450d',
    'chrBust21d_000_eng_o6_627_-3_1050_324.png': '2527be06d3c55144acb6fa2487cae03298a555774b5b4b4c77813b6229aa2875',
    'cast21d_00_l_eng_flipped.png': '1272e14c7d0213e3d5ea38aa2d13edeb837d1552ad592fef049c44c6200cb681',
}


def load_crop(path):
    """the extracted RGBA crop as float64, refused unless its pixels are the ones the offsets were fitted to."""
    if not os.path.exists(path):
        raise BustError('%s is missing; run the build once without --skip-extract' % path)
    a = np.asarray(Image.open(path).convert('RGBA'))
    want = CROP_SHA.get(os.path.basename(path))
    if want is None:
        raise BustError('%s: no recorded hash for this Collection crop' % path)
    if props.pixel_sha(a) != want:
        raise BustError('%s is not the Collection picture the cap was fitted to (pixel hash differs)' % path)
    return a.astype(np.float64)


def cache_dir(dumpdir):
    return os.path.join(dumpdir, *CACHE)


def hd_box(group):
    """the oriented atlas box (Capcom pixels, ints) a group reads, with MARGIN DS pixels round it."""
    cells, atlas, o, ox, oy, (x0, y0, x1, y1) = group
    return (int(np.floor((x0 - MARGIN + ox) * S)), int(np.floor((y0 - MARGIN + oy) * S)),
            int(np.ceil((x1 + MARGIN + ox) * S)), int(np.ceil((y1 + MARGIN + oy) * S)))


def crop_name(atlas, o, box):
    return '%s_eng_o%d_%d_%d_%d_%d.png' % ((atlas, o) + tuple(box))


def wanted():
    return sorted({(g[1], g[2], hd_box(g)) for gs in GROUPS.values() for g in gs})


def icon_name(tex):
    return '%s_eng_flipped.png' % tex


def required(dumpdir):
    return ([os.path.join(cache_dir(dumpdir), crop_name(a, o, b)) for a, o, b in wanted()]
            + [os.path.join(cache_dir(dumpdir), icon_name(t)) for t in sorted({v[1] for v in ICONS.values()})])


def orient(a, o):
    t = np.rot90(a, o % 4)
    return t[:, ::-1] if o >= 4 else t


def extract(bdir, dumpdir):
    """Save the atlas parts the groups read (English textures, oriented, RGBA) under dump/title/props/bust/."""
    import UnityPy
    names = {a + '_eng' for a, _o, _b in wanted()}
    hits = [p for p in glob.glob(os.path.join(bdir, '*.bundle')) if os.path.basename(p).lower().startswith(BUNDLE)]
    if not hits:
        raise SystemExit('props_bust: no bundle starting with %r in %s' % (BUNDLE, bdir))
    env = UnityPy.load(hits[0])
    tex = {}
    for obj in env.objects:
        if obj.type.name != 'Texture2D':
            continue
        d = obj.read()
        if d.m_Name in names:
            tex[d.m_Name] = np.asarray(d.image.convert('RGBA'))
    out = cache_dir(dumpdir)
    os.makedirs(out, exist_ok=True)
    for a, o, box in wanted():
        if a + '_eng' not in tex:
            raise SystemExit('props_bust: texture %s_eng not found in the bustup bundle' % a)
        t = orient(tex[a + '_eng'], o)
        x0, y0, x1, y1 = box
        H, W = t.shape[:2]
        canvas = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
        sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        if sx1 > sx0 and sy1 > sy0:
            canvas[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = t[sy0:sy1, sx0:sx1]
        Image.fromarray(canvas, 'RGBA').save(os.path.join(out, crop_name(a, o, box)))
    # the portrait icon texture, turned the right way up
    inames = {v[1] + '_eng' for v in ICONS.values()}
    hits = [p for p in glob.glob(os.path.join(bdir, '*.bundle')) if os.path.basename(p).lower().startswith(ICON_BUNDLE)]
    if not hits:
        raise SystemExit('props_bust: no bundle starting with %r in %s' % (ICON_BUNDLE, bdir))
    env = UnityPy.load(hits[0])
    itex = {}
    for obj in env.objects:
        if obj.type.name != 'Texture2D':
            continue
        d = obj.read()
        if d.m_Name in inames:
            itex[d.m_Name] = np.asarray(d.image.convert('RGBA'))
    for t in sorted({v[1] for v in ICONS.values()}):
        if t + '_eng' not in itex:
            raise SystemExit('props_bust: texture %s_eng not found in the idcom bundle' % t)
        Image.fromarray(np.ascontiguousarray(itex[t + '_eng'][::-1]), 'RGBA').save(os.path.join(out, icon_name(t)))
    return out


def capcom_view(group, dumpdir):
    """Capcom's English picture over the group's frame box: (rgb (h, w, 3), alpha (h, w))."""
    cells, atlas, o, ox, oy, (x0, y0, x1, y1) = group
    box = hd_box(group)
    a = load_crop(os.path.join(cache_dir(dumpdir), crop_name(atlas, o, box)))
    al = a[..., 3:4] / 255.0
    pm = np.concatenate([a[..., :3] * al, al], -1)
    hb = ((x0 + ox) * S - box[0], (y0 + oy) * S - box[1], (x1 + ox) * S - box[0], (y1 + oy) * S - box[1])
    D = pc.downscale(pm, hb, (x1 - x0, y1 - y0))
    alpha = np.clip(D[..., 3], 0, 1)
    rgb = np.where(alpha[..., None] > 1e-3, D[..., :3] / np.maximum(alpha[..., None], 1e-3), 0)
    return rgb, alpha


# ---------------------------------------------------------------- binary morphology (numpy only)
# 4-connected, the same results as SciPy's binary morphology defaults (cross structure, border 0 for dilation and
# erosion, labels numbered in raster order of each component's first pixel); SciPy is not a build
# dependency.

def _shift_or(m):
    out = m.copy()
    out[1:] |= m[:-1]
    out[:-1] |= m[1:]
    out[:, 1:] |= m[:, :-1]
    out[:, :-1] |= m[:, 1:]
    return out


def _shift_and(m):
    out = m.copy()
    out[1:] &= m[:-1]
    out[:-1] &= m[1:]
    out[:, 1:] &= m[:, :-1]
    out[:, :-1] &= m[:, 1:]
    out[0, :] = False
    out[-1, :] = False
    out[:, 0] = False
    out[:, -1] = False
    return out


def dilate4(m, iterations=1):
    m = np.asarray(m, bool)
    for _ in range(iterations):
        m = _shift_or(m)
    return m


def erode4(m, iterations=1):
    m = np.asarray(m, bool)
    for _ in range(iterations):
        m = _shift_and(m)
    return m


def closing4(m, iterations=1):
    return erode4(dilate4(m, iterations), iterations)


def label4(m):
    """-> (labels int array, count): 4-connected components, numbered in raster order of first pixel."""
    from collections import deque
    m = np.asarray(m, bool)
    H, W = m.shape
    lab = np.zeros((H, W), np.int32)
    n = 0
    for y0, x0 in zip(*np.nonzero(m)):
        if lab[y0, x0]:
            continue
        n += 1
        lab[y0, x0] = n
        q = deque([(y0, x0)])
        while q:
            y, x = q.popleft()
            for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= yy < H and 0 <= xx < W and m[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n
                    q.append((yy, xx))
    return lab, n


def fill_holes4(m):
    """m with every background region not 4-connected to the border filled."""
    m = np.asarray(m, bool)
    lab, n = label4(~m)
    edge = set(lab[0, :].tolist()) | set(lab[-1, :].tolist()) | set(lab[:, 0].tolist()) | set(lab[:, -1].tolist())
    edge.discard(0)
    outside = np.isin(lab, sorted(edge))
    return ~outside


# ---------------------------------------------------------------- one cell

def _skin(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return (r > g) & (g > b) & (r - b > 35) & (g > 105)


def cap_mask(crgb, ca):
    """Capcom's cap band: its large light opaque regions with the letters and pill between them."""
    light = (crgb.mean(-1) > 175) & (ca > 0.9) & ~_skin(crgb)
    lab, n = label4(light)
    keep = np.zeros_like(light)
    for i in range(1, n + 1):
        if (lab == i).sum() >= 40:
            keep |= lab == i
    closed = closing4(np.pad(keep, 4), iterations=3)[4:-4, 4:-4]
    return (fill_holes4(closed) | keep) & (ca > 0.9) & ~_skin(crgb)


def _red_center(fan, op):
    red = (fan[..., 0] > 150) & (fan[..., 1] < 90) & op
    lab, n = label4(dilate4(red, iterations=2))
    if n == 0:
        return None
    _t, i = min((np.nonzero(lab == i)[0].min(), i) for i in range(1, n + 1))
    ys, xs = np.nonzero(lab == i)
    return ys.mean(), xs.mean()


def redraw_cell(fan, idx, op, pal, crgb, ca, fixed=None):
    """fan: (h, w, 3) colours of the cell over the group box, idx its palette indices, op its opaque pixels.
    -> dict(tg: pixels changed, new: indices, coef: the colour fit, resid: fan letters filled past
    Capcom's band)."""
    cap = cap_mask(crgb, ca) & op
    # Capcom's cap component nearest the fan's own (its red pill); other atlas parts in the box are not it
    c = _red_center(fan, op)
    lab, n = label4(cap)
    if n == 0 or c is None:
        raise BustError('no cap found in the cell')
    best = None
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        if len(ys) < 60:
            continue
        dd = np.min((ys - c[0]) ** 2 + (xs - c[1]) ** 2)
        if best is None or dd < best[0]:
            best = (dd, i)
    if best is None:
        raise BustError('no cap found in the cell')
    cap = lab == best[1]
    ring = dilate4(cap, iterations=8) & op & (ca > 0.95) & ~dilate4(cap, iterations=1)
    if fixed is None:
        cal = ring | cap
        fit, err = pc.fit_linear(crgb, fan, cal)
        coef = [tuple(np.polyfit(crgb[..., k][cal], fit[..., k][cal], 1)) for k in range(3)]
    else:
        coef = fixed
    fit = np.stack([coef[k][0] * crgb[..., k] + coef[k][1] for k in range(3)], -1)
    diff = np.abs(fit - fan).max(-1)
    lum = fan.mean(-1)
    sk = _skin(fan) & op
    lab, n = label4(sk)
    big = np.zeros_like(sk)
    for i in range(1, n + 1):
        if (lab == i).sum() >= 25:
            big |= lab == i
    nonskin = ~big
    # the fan's band: its light parts near Capcom's cap, with the fan's letters between them
    light = (lum > 175) & nonskin & op
    lab, n = label4(light)
    keep = np.zeros_like(light)
    near_cap = dilate4(cap, iterations=6)
    for i in range(1, n + 1):
        if (lab == i).sum() >= 25 and ((lab == i) & near_cap).any():
            keep |= lab == i
    red = (fan[..., 0] > fan[..., 1] + 40) & (fan[..., 0] > fan[..., 2] + 25)

    def between(m, axis):
        lo = np.zeros_like(m)
        hi = np.zeros_like(m)
        for dd in (1, 2, 3):
            lo |= np.roll(m, dd, axis)
            hi |= np.roll(m, -dd, axis)
        return lo & hi
    fletters = op & nonskin & dilate4(keep, iterations=2) & (
        red | ((lum < 140) & (between(keep, 0) | between(keep, 1))))
    fband = keep | fletters
    capx = cap | (dilate4(fband, iterations=1) & op & nonskin & (ca > 0.9)
                  & (crgb.mean(-1) < 120) & ~_skin(crgb))
    core = capx & (diff > THR) & nonskin             # the fan's lettering (for the detector)
    tg = dilate4(core, iterations=1) & capx & nonskin
    P = np.array(pal, np.float64)
    # the band's own colours, less any skin tone (the old letters' peach halo is not a colour of the band)
    allowed = sorted(i for i in set(idx[capx & nonskin].tolist()) - {0} if not _skin(P[i][None])[0])
    new = idx.copy()
    ys, xs = np.nonzero(tg)
    if len(ys):
        new[ys, xs] = pc.nearest_index(fit[ys, xs], P, allowed)
    resid = fletters & ~capx & ~tg
    resid = (dilate4(resid, iterations=1) & fband & ~capx & ~tg & (lum < 225)) | resid
    plain = keep & ~resid
    py, px = np.nonzero(plain)
    for y, x in zip(*np.nonzero(resid)):
        dd = (py - y) ** 2 + (px - x) ** 2
        sel = dd <= 9 if (dd <= 9).any() else np.argsort(dd)[:6]
        v, cnt = np.unique(idx[py[sel], px[sel]], return_counts=True)
        new[y, x] = int(v[cnt.argmax()])
    tg = tg | resid
    if (new[tg] == 0).any():
        raise BustError('a cap pixel would become the transparent index 0')
    return dict(tg=tg, new=new, coef=coef, resid=int(resid.sum()), cap=capx, core=core | resid)


def redraw_entry(e, dec, pal, dumpdir, info=None):
    """-> the entry with the nurse's cap redrawn in every cell (only tile bytes change)."""
    cells, mapping, start, tiles = parts(dec)
    listed = sorted(c for g in GROUPS[e] for c in g[0]) + list(NO_CAP.get(e, ()))
    if sorted(listed) != list(range(len(cells))):
        raise BustError('bustup %d: the groups do not list each of its %d cells once' % (e, len(cells)))
    bnd = bounds([c for c in cells if c])
    P = np.array(list(pal) + [(0, 0, 0)] * (256 - len(pal)), np.float64)
    t2 = tiles.copy()
    written = {}
    cores = set()
    conflicts = changed = resid = 0
    for g in GROUPS[e]:
        crgb, ca = capcom_view(g, dumpdir)
        x0, y0, x1, y1 = g[5]
        coef = None
        for k in g[0]:
            src = cell_map(cells[k], mapping, tiles, bnd)[y0:y1, x0:x1]
            op = src >= 0
            idx = np.where(op, tiles[np.maximum(src, 0)], 0)
            fan = P[idx]
            try:
                r = redraw_cell(fan, idx, op, pal, crgb, ca, coef)
            except BustError as ex:
                raise BustError('bustup %d cell %d: %s' % (e, k, ex))
            coef = r['coef']
            cores.update(int(v) for v in src[r['core']])
            for y, x in zip(*np.nonzero(r['tg'])):
                off = int(src[y, x])
                v = int(r['new'][y, x])
                if off in written and written[off] != v:
                    conflicts += 1
                    continue
                written[off] = v
                t2[off] = v
            changed += int(r['tg'].sum())
            resid += r['resid']
    out = bytearray(dec)
    out[start:start + len(t2)] = t2.tobytes()
    if info is not None:
        info.update(tile_bytes=len(written), conflicts=conflicts, cell_pixels=changed, filled_past_band=resid,
                    written=sorted(written), core=sorted(cores), tile_start=start)
    return bytes(out)


# ---------------------------------------------------------------- the container

def patch_container(data, dumpdir, log=None):
    from nitro import nclr
    log = log or (lambda s: None)
    t = props.table(data)
    ext = props.extents(t, len(data))
    out = bytearray(data)
    for e in sorted(GROUPS):
        dec, stored, comp = props.entry_decoded(data, e)
        pdec = props.entry_decoded(data, PALS[e])[0]
        want = FAN_SHA.get(e)
        if want is None or hashlib.sha256(dec).hexdigest() != want[0] or hashlib.sha256(pdec).hexdigest() != want[1]:
            raise BustError('%s entry %d is not the fan\'s sprite (or its palette %d is not the fan\'s)' % (CONT, e, PALS[e]))
        if not comp:
            raise BustError('%s entry %d is expected to be an LZ11 stream' % (CONT, e))
        info = {}
        new = redraw_entry(e, dec, nclr(pdec), dumpdir, info)
        if len(new) != len(dec):
            raise BustError('entry changed size')
        st = lz11.compress(new)
        if lz11.decompress(st) != new:
            raise BustError('%s entry %d does not round-trip through LZ11' % (CONT, e))
        a, b = ext[e]
        if len(st) > b - a:
            raise BustError('%s entry %d would be stored in %d bytes, the fan\'s is %d; it must not be larger'
                            % (CONT, e, len(st), b - a))
        out[a:b] = st + b'\0' * (b - a - len(st))
        log('nurse cap (%s %d): %d tile bytes, %d cell pixels, %d old letter pixels filled past Capcom\'s band, '
            '%d tile bytes two cells would set differently (first kept), stored %d of the fan\'s %d'
            % (CONT, e, info['tile_bytes'], info['cell_pixels'], info['filled_past_band'], info['conflicts'], len(st), b - a))
    if len(out) != len(data):
        raise BustError('container changed size')
    return bytes(out)


def redraw_icon(e, dec, pal, dumpdir, info=None):
    """-> the icon entry with its cap redrawn (only tile data changes, through the cell layout)."""
    import choice_strips as cs
    pe, tex, (sx, sy, ox, oy) = ICONS[e]
    t = load_crop(os.path.join(cache_dir(dumpdir), icon_name(tex)))
    g = np.array(cs.grid(dec), np.int64)
    n_y, n_x = g.shape
    tp = np.pad(t, ((ICON_PAD, ICON_PAD), (ICON_PAD, ICON_PAD), (0, 0)), mode='edge')
    D = pc.downscale(tp, (ox + ICON_PAD, oy + ICON_PAD, ox + ICON_PAD + sx * n_x, oy + ICON_PAD + sy * n_y), (n_x, n_y))
    crgb, ca = D[..., :3], np.clip(D[..., 3] / 255.0, 0, 1)
    P = np.array(list(pal) + [(0, 0, 0)] * (256 - len(pal)), np.float64)
    try:
        r = redraw_cell(P[g], g, g > 0, pal, crgb, ca)
    except BustError as ex:
        raise BustError('idcom icon %d: %s' % (e, ex))
    new = cs.encode(dec, [list(map(int, row)) for row in r['new']])
    if len(new) != len(dec):
        raise BustError('idcom icon %d changed size' % e)
    if not np.array_equal(np.array(cs.grid(new), np.int64), r['new']):
        raise BustError('idcom icon %d does not read back as the picture written' % e)
    if info is not None:
        info.update(pixels=int(r['tg'].sum()), filled_past_band=r['resid'], core=r['core'])
    return new


def patch_icons(data, dumpdir, log=None):
    from nitro import nclr
    log = log or (lambda s: None)
    t = props.table(data)
    ext = props.extents(t, len(data))
    out = bytearray(data)
    for e in sorted(ICONS):
        pe = ICONS[e][0]
        dec, stored, comp = props.entry_decoded(data, e)
        pdec = props.entry_decoded(data, pe)[0]
        want = ICON_SHA[e]
        if hashlib.sha256(dec).hexdigest() != want[0] or hashlib.sha256(pdec).hexdigest() != want[1]:
            raise BustError('%s entry %d is not the fan\'s icon (or its palette %d is not the fan\'s)' % (ICON_CONT, e, pe))
        if not comp:
            raise BustError('%s entry %d is expected to be an LZ11 stream' % (ICON_CONT, e))
        info = {}
        new = redraw_icon(e, dec, nclr(pdec), dumpdir, info)
        st = lz11.compress(new)
        if lz11.decompress(st) != new:
            raise BustError('%s entry %d does not round-trip through LZ11' % (ICON_CONT, e))
        a, b = ext[e]
        if len(st) > b - a:
            raise BustError('%s entry %d would be stored in %d bytes, the fan\'s is %d; it must not be larger'
                            % (ICON_CONT, e, len(st), b - a))
        out[a:b] = st + b'\0' * (b - a - len(st))
        log('nurse cap (%s %d): %d pixels, %d old letter pixels filled past Capcom\'s band, stored %d of the fan\'s %d'
            % (ICON_CONT, e, info['pixels'], info['filled_past_band'], len(st), b - a))
    if len(out) != len(data):
        raise BustError('container changed size')
    return bytes(out)


def apply_to_rom(rom, dumpdir, log=None, any_rom=False):
    import title_logo
    from choice_strips import rom_file
    log = log or (lambda s: None)
    try:
        new = patch_container(rom_file(rom, CONT), dumpdir, log)
        icons = patch_icons(rom_file(rom, ICON_CONT), dumpdir, log)
    except PropsError as ex:
        if not any_rom:
            raise
        log('nurse cap: NOT redrawn, --any-rom given (%s)' % ex)
        return rom, False
    rom = title_logo.splice(rom, CONT, new)
    return title_logo.splice(rom, ICON_CONT, icons), True

