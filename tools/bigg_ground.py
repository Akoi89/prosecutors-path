# -*- coding: utf-8 -*-
"""The map background under the fan's "Grand Tower" label, derived from Capcom's own city map.

The city map (jpn/upcut_local.bin 264 and 280, 256x192) has roads, blocks and the small arched
driveway of the tower running under the old two-line label, so the label cannot be erased to a flat
colour. Capcom's Collection has the same map as a 1920x1080 picture, cut04_010 (Japanese) and
cut04_010_eng, _fre, _ger, _kor, _sim, _tra, in the bundle gk2_upcutlocal. Their background is
identical; only the labels differ. The DS map is the central 1440x1080 of that picture scaled to
256x192 (scale 5.625, no offset; the registration is measured again on every build and the build
stops if it does not hold).

At build time, from the user's own Collection install (extract() puts the seven textures under
dump/title/bigg_map/):
  1. each language's lettering (neutral near-black ink, and a disc of DISC px around it, which takes
     its white halo) is cut out; a background pixel is the colour most of the languages that show no
     lettering there agree on;
  2. the pixels that all seven hide are filled from their row or column neighbours when those agree;
     the driveway arch (two concentric half rings fitted to the road edge lines that are visible, over
     a pink road) is drawn where it was hidden; whatever is left is grown from the nearest known pixel
     and counted;
  3. the window is scaled to DS size (Lanczos); a per-channel linear fit on the unmasked pixels around
     the label proves that the two pictures register (the build stops if not), and each masked pixel
     takes the palette index the DS picture itself uses, near the label, for pixels that Capcom's
     picture shows in the same colour (a vote of the twelve nearest in colour).
Nothing derived from the game is stored in the repository; the module needs numpy and Pillow only.

    new, info = derive(g, pal, mask, keep, dumpdir)

`keep` is the set of masked pixels that the new label will not cover; the build raises if any of them
depends on a pixel that was grown from the nearest known pixel.
"""
import os, glob, collections
import numpy as np
from PIL import Image
import input_hashes as ih


class GroundError(ValueError):
    pass


BUNDLE_PREFIX = 'gk2_upcutlocal_assets'
TEXTURE = 'cut04_010'
TEXTURE2 = 'cut04_03e'            # the same map with the "Sunshine Depot" blocks drawn: Capcom's picture for the DS map 280 (tools/city_labels.py)
SUFFIXES = ('', '_eng', '_fre', '_ger', '_kor', '_sim', '_tra')
SCALE = 1440 / 256.0            # Capcom pixels per DS pixel (the DS map is the central 4:3 of 16:9)
CROP_X = 240
MARGIN = 16                     # Capcom pixels of context kept around the window
INK, HALO = 0, 28               # the fan's label: ink and halo palette indices on the city map
LABEL_BOX = (80, 117, 102, 124)  # x0 x1 y0 y1: both lines of the old label, nothing else
DILATE = 3                      # passes of a 3x3 dilation of (ink + halo)
DISC = 9                        # Capcom pixels: the halo around Capcom's lettering is 7 to 8
PAD = 32                        # DS pixels of context around the mask
K_NEAREST = 12                  # ring pixels that vote for a masked pixel's palette index
LAMBDA = 0.05                   # colour distance squared that one pixel squared of distance in the picture is worth
RING = (2, 12)                  # calibration ring around the mask (DS pixels)
ARCH_BOX = (80, 98, 118, 122)   # DS pixels: the arched driveway under the tower, a half ring with straight stems
ARCH_OUT = (203, 202, 207)      # colour of the road edge line in Capcom's picture
OUTER_REACH = 14                # Capcom pixels beyond the outer edge line that are also painted with the block colour
ARCH_FIT_MAX = 1.6              # mean distance (Capcom pixels) of the visible edge pixels from the fitted ring
REG_MAX_ERR = 9.0               # mean |scaled Capcom - DS| on the ring, after the fit
REG_MARGIN = 1.0                # the fit must be this much better than any one-pixel shift


def cache_dir(dumpdir):
    return os.path.join(dumpdir, 'title', 'bigg_map')


def textures(which=1):
    return [(TEXTURE if which == 1 else TEXTURE2) + s for s in SUFFIXES]


def required(dumpdir):
    return [os.path.join(cache_dir(dumpdir), n + '.png') for n in textures(1) + textures(2)]


def extract(bdir, dumpdir):
    """Save the fourteen city-map textures of the Collection (gk2_upcutlocal bundle: cut04_010 and cut04_03e, seven languages each) as RGB PNGs under
    dump/title/bigg_map/. Raises SystemExit if the bundle or a texture is missing."""
    hits = [p for p in glob.glob(os.path.join(bdir, '*.bundle'))
            if os.path.basename(p).lower().startswith(BUNDLE_PREFIX)
            and '_classic' not in os.path.basename(p).lower() and '_trial' not in os.path.basename(p).lower()]
    if not hits:
        raise SystemExit('city map: no bundle starting with %r in %s' % (BUNDLE_PREFIX, bdir))
    import UnityPy
    env = UnityPy.load(hits[0])
    want, found = set(textures(1)) | set(textures(2)), {}
    for obj in env.objects:
        if obj.type.name != 'Texture2D':
            continue
        d = obj.read()
        if d.m_Name in want:
            found[d.m_Name] = d.image.copy()
    missing = sorted(want - set(found))
    if missing:
        raise SystemExit('city map: texture(s) %s not found in %s' % (', '.join(missing), os.path.basename(hits[0])))
    out = cache_dir(dumpdir)
    os.makedirs(out, exist_ok=True)
    for name, im in found.items():
        if im.size != (1920, 1080):
            raise SystemExit('city map: texture %s is %dx%d, expected 1920x1080' % ((name,) + im.size))
        im.convert('RGB').save(os.path.join(out, name + '.png'))
    return out


def load_textures(dumpdir, which=1):
    out = []
    for n in textures(which):
        p = os.path.join(cache_dir(dumpdir), n + '.png')
        if not os.path.isfile(p):
            raise GroundError('texture %s is missing (%s); run the build once without --skip-extract' % (n, p))
        im = Image.open(p).convert('RGB')
        if im.size != (1920, 1080):
            raise GroundError('texture %s is %dx%d, expected 1920x1080' % ((n,) + im.size))
        a = np.asarray(im, np.int16)
        if ih.GUARD_INPUTS and ih.sha(a.tobytes()) != ih.MAP_TEXTURE_SHA256.get(n):
            raise GroundError('texture %s is not the Collection picture this routine was proven on' % n)
        out.append(a)
    return np.stack(out)


# ---------------------------------------------------------------------------
# the old label's mask on the DS picture
# ---------------------------------------------------------------------------
def dilate3(mask, passes):
    m = mask.copy()
    for _ in range(passes):
        p = np.pad(m, 1)
        m = np.zeros_like(m)
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                m |= p[dy:dy + mask.shape[0], dx:dx + mask.shape[1]]
    return m


def label_mask(g):
    """Boolean mask of the old label: ink, its halo, then DILATE passes of 3x3 growth."""
    import room_names as rn
    m = rn.ink_mask(g, INK, LABEL_BOX)
    orth, _diag = rn.ring_of(m)
    mask = np.zeros(g.shape, bool)
    for (x, y) in m:
        mask[y, x] = True
    for (x, y) in orth:
        if g[y, x] == HALO:
            mask[y, x] = True
    return dilate3(mask, DILATE)


# ---------------------------------------------------------------------------
# Capcom's background
# ---------------------------------------------------------------------------
def disc_dilate(m, r):
    """Dilation of a boolean grid by a disc of radius r (numpy only)."""
    h, w = m.shape
    horiz = {}
    for hw in sorted(set(int((r * r - dy * dy) ** 0.5) for dy in range(-r, r + 1))):
        pad = np.pad(m.astype(np.int32), ((0, 0), (hw, hw)))
        cs = np.concatenate([np.zeros((h, 1), np.int32), np.cumsum(pad, axis=1)], axis=1)
        horiz[hw] = (cs[:, 2 * hw + 1:2 * hw + 1 + w] - cs[:, :w]) > 0
    out = np.zeros((h, w), bool)
    for dy in range(-r, r + 1):
        a = horiz[int((r * r - dy * dy) ** 0.5)]
        if dy >= 0:
            out[dy:] |= a[:h - dy]
        else:
            out[:h + dy] |= a[-dy:]
    return out


def lettering_free(V):
    """V: (languages, h, w, 3). -> bool (languages, h, w): True where that language has no lettering
    (neutral near-black ink, or within DISC pixels of it, which covers its white halo)."""
    ok = np.zeros(V.shape[:3], bool)
    for i in range(V.shape[0]):
        ink = (V[i].max(-1) < 80) & ((V[i].max(-1) - V[i].min(-1)) < 24)
        ok[i] = ~disc_dilate(ink, DISC)
    return ok


def consensus(V, free):
    """The background pixel: among the languages that show no lettering there, the colour most of them agree
    on. A pixel stays hidden (seen False) when no language is free there, or when the best colour is tied
    with a different one, or when it is white and only one language shows it (a halo left over from a
    thin stroke). -> (bg uint8, seen bool)."""
    L, h, w = V.shape[:3]
    key = (V[..., 0].astype(np.int32) << 16) | (V[..., 1].astype(np.int32) << 8) | V[..., 2].astype(np.int32)
    cnt = np.zeros((L, h, w), np.int32)
    for i in range(L):
        for j in range(L):
            cnt[i] += free[i] & free[j] & (key[i] == key[j])
    cnt[~free] = 0
    m = cnt.max(axis=0)
    arg = cnt.argmax(axis=0)
    kmax = np.take_along_axis(key, arg[None], 0)[0]
    tie = (free & (cnt == m[None]) & (key != kmax[None])).any(axis=0)
    seen = (m > 0) & ~tie & ~((kmax == 0xFFFFFF) & (m < 2))
    bg = np.stack([(kmax >> 16) & 255, (kmax >> 8) & 255, kmax & 255], -1).astype(np.uint8)
    return bg, seen


def _arch_cost(P, cx, cy, r1, r2):
    """Distance of each point to the nearer of two concentric half rings (centre cx, cy) that continue as
    vertical stems below cy. r1, r2 may be arrays (broadcast over a trailing point axis)."""
    up = P[:, 1] < cy
    d = np.where(up, np.hypot(P[:, 0] - cx, P[:, 1] - cy), np.abs(P[:, 0] - cx))
    return np.minimum(np.abs(d - np.asarray(r1)[..., None]), np.abs(d - np.asarray(r2)[..., None]))


def fit_arch(bg, seen, win, off=0):
    """The driveway arch: two concentric half rings (the road edge lines) over a pink road. Fit the centre and
    the two radii to the visible edge-line pixels. -> dict in the array's Capcom pixel coordinates."""
    x0, y0, x1, y1 = win
    ax0, ay0, ax1, ay1 = ARCH_BOX
    bx0, bx1 = int((ax0 - x0) * SCALE) + off, int((ax1 - x0) * SCALE) + off
    by0, by1 = int((ay0 - y0) * SCALE) + off, int((ay1 - y0) * SCALE) + off
    out = seen & (np.abs(bg.astype(int) - np.array(ARCH_OUT)).sum(-1) <= 4)
    sub = out[by0:by1, bx0:bx1]
    long_rows = np.nonzero(sub.sum(1) > 0.6 * sub.shape[1])[0]
    if not len(long_rows):
        raise GroundError('arch: the block edge line under the driveway was not found')
    stem_end = by0 + int(long_rows[0])
    ys, xs = np.nonzero(out[by0:stem_end - 2, bx0:bx1])
    P = np.stack([xs + bx0, ys + by0], 1).astype(float)
    if len(P) < 200:
        raise GroundError('arch: only %d edge pixels visible' % len(P))
    cx_mid = (P[:, 0].min() + P[:, 0].max()) / 2
    best = None
    r1s = np.arange(26, 80, 2.0)
    r2s = r1s[:, None] + np.arange(8, 40, 2.0)[None, :]
    r1g = np.repeat(r1s[:, None], r2s.shape[1], 1)
    for cx in np.arange(cx_mid - 12, cx_mid + 12.1, 2.0):
        for cy in np.arange(stem_end - 30, stem_end + 2, 2.0):
            cost = np.minimum(_arch_cost(P, cx, cy, r1g, r2s), 6).sum(-1)
            i, j = np.unravel_index(cost.argmin(), cost.shape)
            if best is None or cost[i, j] < best[0]:
                best = (cost[i, j], cx, cy, r1s[i], r2s[i, j])
    _, cx, cy, r1, r2 = best
    for step in (1.0, 0.5):
        for _ in range(3):
            cand = [(cx + a, cy + b, r1 + c, r2 + d) for a in (-step, 0, step) for b in (-step, 0, step)
                    for c in (-step, 0, step) for d in (-step, 0, step)]
            costs = [np.minimum(_arch_cost(P, q[0], q[1], q[2], q[3]), 6).sum() for q in cand]
            cx, cy, r1, r2 = cand[int(np.argmin(costs))]
    res = _arch_cost(P, cx, cy, r1, r2)
    if res.mean() > ARCH_FIT_MAX or r2 - r1 < 12:
        raise GroundError('arch: the ring does not fit the road edge lines (mean distance %.2f, radii %.1f and %.1f)'
                          % (res.mean(), r1, r2))
    # edge line thickness: horizontal runs of edge pixels on the stems, just above the block line
    th = []
    for y in range(int(stem_end) - 12, int(stem_end) - 3):
        xs_ = np.nonzero(out[y, bx0:bx1])[0]
        if len(xs_):
            th += [len(r) for r in np.split(xs_, np.nonzero(np.diff(xs_) > 1)[0] + 1)]
    t = float(np.median(th)) if th else 6.0
    # colours of the three classes, from the visible pixels at the right distances
    yy, xx = np.mgrid[by0:stem_end - 2, bx0:bx1]
    d = np.hypot(xx - cx, yy - cy)
    ok = seen[by0:stem_end - 2, bx0:bx1] & (yy < cy)

    def mode(sel):
        v = bg[by0:stem_end - 2, bx0:bx1][sel & ok]
        if len(v) < 50:
            raise GroundError('arch: too few visible pixels to take a colour from')
        return collections.Counter(map(tuple, v.tolist())).most_common(1)[0][0]
    cols = dict(inner=mode(d < r1 - t), road=mode((d > r1 + t) & (d < r2 - t)), edge=ARCH_OUT,
                outer=mode((d > r2 + t) & (d < r2 + 4 * t)))
    return dict(cx=cx, cy=cy, r1=r1, r2=r2, t=t, colours=cols, residual=float(res.mean()),
                box=(bx0, by0, bx1, stem_end))


def paint_arch(bg, stage, arch):
    """Hidden pixels (stage > 0) inside the arch's outer ring, and OUTER_REACH beyond it, take the class
    colour of the ring (inner block, edge line, road, outer block). -> pixels painted."""
    cx, cy, r1, r2, t = arch['cx'], arch['cy'], arch['r1'], arch['r2'], arch['t']
    bx0, by0, bx1, by1 = arch['box']
    c = arch['colours']
    n = 0
    for y in range(by0, by1):
        for x in range(bx0, bx1):
            if stage[y, x] == 0 or y >= cy:
                continue
            d = np.hypot(x - cx, y - cy)
            if d > r2 + t + OUTER_REACH:
                continue
            if abs(d - r1) <= t / 2 or abs(d - r2) <= t / 2:
                v = c['edge']
            elif r1 < d < r2:
                v = c['road']
            elif d < r1:
                v = c['inner']
            else:
                v = c['outer']
            bg[y, x] = v
            stage[y, x] = 3
            n += 1
    return n


def fill_hidden(bg, seen, tol=6):
    """Pixels no language shows: the row neighbours' colour when the nearest seen pixel on each side
    agrees, else the column neighbours', else (stage 2) left for the nearest-pixel growth below.
    -> (bg, stage): stage 0 seen, 1 row/column fill, 2 to grow."""
    h, w = seen.shape
    out = bg.copy()
    stage = np.zeros((h, w), np.uint8)
    for y, x in zip(*np.nonzero(~seen)):
        row = seen[y]
        l = x - 1
        while l >= 0 and not row[l]:
            l -= 1
        r = x + 1
        while r < w and not row[r]:
            r += 1
        if l >= 0 and r < w and np.abs(bg[y, l].astype(int) - bg[y, r].astype(int)).max() <= tol:
            out[y, x] = bg[y, l]; stage[y, x] = 1; continue
        col = seen[:, x]
        u = y - 1
        while u >= 0 and not col[u]:
            u -= 1
        d = y + 1
        while d < h and not col[d]:
            d += 1
        if u >= 0 and d < h and np.abs(bg[u, x].astype(int) - bg[d, x].astype(int)).max() <= tol:
            out[y, x] = bg[u, x]; stage[y, x] = 1; continue
        stage[y, x] = 2
    return out, stage


def grow_nearest(bg, stage):
    """Stage 2 pixels (and nothing else) take the colour of the nearest known pixel, grown one ring at a time."""
    h, w = stage.shape
    out = bg.copy()
    known = stage != 2
    todo = ~known
    while todo.any():
        nk, o2, got = known.copy(), out.copy(), False
        for y, x in zip(*np.nonzero(todo)):
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w and known[yy, xx]:
                    o2[y, x] = out[yy, xx]; nk[y, x] = True; got = True
                    break
        if not got:
            raise GroundError('no known pixel to grow from')
        out, known = o2, nk
        todo = ~known
    return out


def window_for(mask):
    ys, xs = np.nonzero(mask)
    x0 = max(0, (xs.min() - PAD) // 8 * 8)
    x1 = min(256, -(-(xs.max() + 1 + PAD) // 8) * 8)
    y0 = max(0, (ys.min() - PAD) // 8 * 8)
    y1 = min(192, -(-(ys.max() + 1 + PAD) // 8) * 8)
    return int(x0), int(y0), int(x1), int(y1)


def hd_box(win, crop_x=None):
    x0, y0, x1, y1 = win
    cx = CROP_X if crop_x is None else crop_x
    return int(round(cx + x0 * SCALE)), int(round(y0 * SCALE)), int(round(cx + x1 * SCALE)), int(round(y1 * SCALE))


def scaled(a, win):
    """Capcom pixels of the window plus MARGIN on every side (h, w[, 3]) -> DS size of the window, Lanczos,
    float."""
    x0, y0, x1, y1 = win
    a = np.asarray(a)
    if a.ndim == 3:
        return np.stack([scaled(a[..., c], win) for c in range(a.shape[2])], -1)
    hw, hh = a.shape[1] - 2 * MARGIN, a.shape[0] - 2 * MARGIN
    box = (MARGIN, MARGIN, MARGIN + hw, MARGIN + hh)
    return np.asarray(Image.fromarray(a.astype(np.float32)).resize((x1 - x0, y1 - y0), Image.LANCZOS, box=box), np.float64)


def derive(g, pal, mask, keep, dumpdir=None, textures_=None, cands_ink=(INK,), strict=True, use_arch=True, check_reg=True,
           ring_exclude=None, bridge=False, far_tol=0.02, crop_x=None, cal_exclude=None, cal_region=None):
    """g: DS index grid, pal: list of (r, g, b), mask: bool grid of the pixels to fill, keep: bool grid of
    the masked pixels that stay visible after the new label, ring_exclude: bool grid of pixels (other lettering
    that stays) that must not serve as calibration or as a colour example, bridge: a visible pixel that depends on
    a grown Capcom pixel takes, if the picture has the same value on both sides of it in its column (or row) beyond
    the erased label, that value (a block edge or a road that runs through the label); far_tol: the share of a visible
    pixel's footprint that may be grown (0.02: one Capcom pixel); crop_x: where the picture starts in the texture
    (the city map: CROP_X; a sprite sheet drawn at SCALE times the size: 0), cal_exclude: pixels that do not
    take part in the registration proof (a transparent patch pixel has no colour of its own), cal_region: the
    pixels it is measured on instead of the ring round the mask (a patch has no flat ring). -> (new grid, info)."""
    V = textures_ if textures_ is not None else load_textures(dumpdir)
    win = window_for(mask)
    x0, y0, x1, y1 = win
    hx0, hy0, hx1, hy1 = hd_box(win, crop_x)
    if hx0 < 0 or hy0 < 0 or hx1 > V.shape[2] or hy1 > V.shape[1]:
        raise GroundError('window %r is outside the texture' % (win,))
    # a window on an edge of the texture gets its context (MARGIN pixels, only there for the resampling) by
    # repeating the edge row or column (the city map is the full height of its texture)
    pad_l, pad_r = max(0, MARGIN - hx0), max(0, hx1 + MARGIN - V.shape[2])
    pad_t, pad_b = max(0, MARGIN - hy0), max(0, hy1 + MARGIN - V.shape[1])
    if pad_l or pad_r or pad_t or pad_b:
        V = np.pad(V, ((0, 0), (pad_t, pad_b), (pad_l, pad_r), (0, 0)), mode='edge')
        hx0, hx1, hy0, hy1 = hx0 + pad_l, hx1 + pad_l, hy0 + pad_t, hy1 + pad_t
    Vw = V[:, hy0 - MARGIN:hy1 + MARGIN, hx0 - MARGIN:hx1 + MARGIN]
    free = lettering_free(Vw)
    bg0, seen = consensus(Vw, free)
    bg, stage = fill_hidden(bg0, seen)
    arch = fit_arch(bg0, seen, win, MARGIN) if use_arch else dict(cx=0, cy=0, r1=0, r2=0, t=0, residual=0)
    n_arch = paint_arch(bg, stage, arch) if use_arch else 0
    bg = grow_nearest(bg, stage)
    D = scaled(bg, win)
    # share of each DS pixel's footprint that was hidden in all seven (any fill; the nearest-pixel growth)
    T_any = scaled((stage > 0).astype(np.float32), win)
    T_far = scaled((stage == 2).astype(np.float32), win)
    gm, gg = mask[y0:y1, x0:x1], g[y0:y1, x0:x1]
    P = np.array(list(pal) + [(255, 0, 255)] * (256 - len(pal)), np.float64)
    d_in, d_out = dilate3(gm, RING[0]), dilate3(gm, RING[1])
    cal = d_out & ~d_in & (T_any < 0.01)
    if ring_exclude is not None:
        cal &= ~ring_exclude[y0:y1, x0:x1]
    if cal_region is not None:
        cal = cal_region[y0:y1, x0:x1] & ~d_in & (T_any < 0.01)
    if cal_exclude is not None:
        cal &= ~cal_exclude[y0:y1, x0:x1]
    # registration proof: a per-channel linear fit of the scaled Capcom colours onto the DS colours, and the
    # same with the picture moved by one pixel
    ds = P[gg]
    fitted = D.copy()
    for c in range(3):
        xs_, ys_ = D[..., c][cal], ds[..., c][cal]
        a, b = np.polyfit(xs_, ys_, 1)
        for _ in range(4):
            r = np.abs(a * xs_ + b - ys_)
            k = r < max(6.0, 2.5 * np.median(r))
            a, b = np.polyfit(xs_[k], ys_[k], 1)
        fitted[..., c] = a * D[..., c] + b
    base = float(np.abs(fitted - ds).mean(-1)[cal].mean())
    shifts = {}
    for name, (dy, dx) in {'up': (-1, 0), 'down': (1, 0), 'left': (0, -1), 'right': (0, 1)}.items():
        sh = np.roll(np.roll(fitted, dy, 0), dx, 1)
        shifts[name] = float(np.abs(sh - ds).mean(-1)[cal].mean())
    if check_reg and (base > REG_MAX_ERR or min(shifts.values()) < base + REG_MARGIN):
        raise GroundError("Capcom's city map does not register onto the DS map (mean error %.1f, one-pixel shifts %s)"
                          % (base, {k: round(v, 1) for k, v in shifts.items()}))
    # each masked pixel takes the palette index the DS picture itself uses, near the label, for pixels that
    # Capcom's picture shows in the same colour: the K ring pixels closest in colour (a small penalty on
    # distance in the picture), most frequent index wins, the nearest in colour breaking a tie
    ring_ok = d_out & ~d_in & (T_any < 0.01) & ~np.isin(gg, list(cands_ink))
    if ring_exclude is not None:
        ring_ok &= ~ring_exclude[y0:y1, x0:x1]
    ry, rx = np.nonzero(ring_ok)
    RF, RI = D[ry, rx], gg[ry, rx]
    ys, xs = np.nonzero(gm)
    new = g.copy()
    for y, x in zip(ys, xs):
        cost = ((RF - D[y, x]) ** 2).sum(1) + LAMBDA * ((ry - y) ** 2 + (rx - x) ** 2)
        order = np.argsort(cost, kind='stable')[:K_NEAREST]
        votes = collections.Counter(RI[order].tolist())
        top = max(votes.values())
        first = [i for i in order if votes[int(RI[i])] == top][0]
        new[y0 + y, x0 + x] = int(RI[first])
    kw = keep[y0:y1, x0:x1] & gm
    bad = (T_far > 0.02) & kw
    bridged = 0
    if bridge and bad.any():
        known = ~mask if ring_exclude is None else (~mask & ~ring_exclude)
        H, W = g.shape
        for y, x in zip(*np.nonzero(bad)):
            Y, X = y0 + y, x0 + x
            val = None
            u = Y - 1
            while u >= 0 and not known[u, X]:
                u -= 1
            d = Y + 1
            while d < H and not known[d, X]:
                d += 1
            if u >= 0 and d < H and g[u, X] == g[d, X]:
                val = int(g[u, X])
            else:
                l = X - 1
                while l >= 0 and not known[Y, l]:
                    l -= 1
                r = X + 1
                while r < W and not known[Y, r]:
                    r += 1
                if l >= 0 and r < W and g[Y, l] == g[Y, r]:
                    val = int(g[Y, l])
            if val is not None:
                new[Y, X] = val
                bad[y, x] = False
                bridged += 1
    left = bad.copy()
    far = int((bad & (T_far > far_tol)).sum())
    info = dict(window=win, ring=int(cal.sum()), mean_err=base, shifts=shifts,
                hidden_hd=int((stage > 0).sum()), filled_row_col=int((stage == 1).sum()),
                arch=dict(cx=float(arch['cx']), cy=float(arch['cy']), r1=float(arch['r1']), r2=float(arch['r2']),
                          t=arch['t'], residual=arch['residual'], painted=n_arch),
                grown=int((stage == 2).sum()), kept=int(kw.sum()), bridged=bridged,
                unresolved=[(int(x0 + x), int(y0 + y)) for y, x in zip(*np.nonzero(left))],
                grown_share=sorted(float(T_far[y, x]) for y, x in zip(*np.nonzero(left)))[-5:],
                n_grown_touching=int(left.sum()),
                kept_touching_hidden=int(((T_any > 0.02) & kw).sum()), kept_touching_grown=far,
                stage_ds=(T_any, T_far))
    if far and strict:
        raise GroundError('%d visible pixels depend on Capcom pixels that no language shows and that were grown from the '
                          'nearest known pixel' % far)
    return new, info
