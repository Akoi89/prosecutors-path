# -*- coding: utf-8 -*-
"""Shared machinery for the background signs and props redrawn from Capcom's Collection pictures
(tools/props.py drives it; numpy and Pillow only).

The DS backgrounds in com/mapbg.bin, com/upcut.bin, com/logicbg.bin and jpn/upcut_local.bin are
8bpp (or 4bpp) rasters with one palette. The Collection ships the same art redrawn at 5.625 times
the size, once per language: the Japanese picture and _eng, _fre, _ger, _kor, _sim, _tra, whose
backgrounds are pixel for pixel the same and whose lettering differs. From those, at build time:

  background(V)   the picture with no lettering: for each Capcom pixel, the colour that the
                  languages showing no lettering there agree on (lettering = dark ink and a few
                  pixels round it); pixels no language shows are filled from their row or column
                  when both sides agree, the rest from the nearest known pixel (counted)
  downscale(a)    Capcom pixels -> DS pixels for a registered window (area average)
  vote(...)       the palette index a DS pixel takes: the index the DS picture itself uses, near the
                  sign, for pixels that Capcom's picture shows in the closest colour (twelve nearest
                  in colour vote; the same rule as tools/bigg_ground.py)
  register(...)   proof on every build that the window registers: a per-channel linear fit of the
                  scaled Capcom colours onto the DS colours on the pixels round the sign, and the same
                  moved by one pixel each way, which must be worse

Nothing derived from the game is stored in the repository.
"""
import collections
import numpy as np
from PIL import Image


class PropsError(ValueError):
    pass


K_NEAREST = 12
LAMBDA = 0.05


def dilate(m, r):
    """Binary dilation of bool array m by a disc of radius r (pixels)."""
    m = np.asarray(m, bool)
    if r <= 0:
        return m.copy()
    out = m.copy()
    h, w = m.shape
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy > r * r:
                continue
            ys0, ys1 = max(0, dy), h + min(0, dy)
            xs0, xs1 = max(0, dx), w + min(0, dx)
            out[ys0:ys1, xs0:xs1] |= m[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
    return out


def ink_of(img, dark=90, neutral=40, light=None):
    """Dark, nearly neutral pixels of an (h, w, 3) uint8 picture: printed lettering (with light=v: pixels
    whose darkest channel is above v instead, white lettering on a dark sign)."""
    a = img.astype(np.int32)
    if light is not None:
        return (a.min(-1) > light) & ((a.max(-1) - a.min(-1)) < neutral)
    return (a.max(-1) < dark) & ((a.max(-1) - a.min(-1)) < neutral)


def lettering_masks(V, ink='dark', median=False, tol=40):
    """(L, h, w) bool: each language's lettering in the stack V. ink 'dark' or 'light'; median=True
    also counts any pixel where a language differs from the median of the languages by more than tol
    (lettering of any colour)."""
    kw = dict(dark=110, neutral=50) if ink == 'dark' else dict(light=150, neutral=60)
    let = np.stack([ink_of(V[i], **kw) for i in range(len(V))])
    if median:
        med = np.median(V.astype(np.float64), axis=0)
        let |= np.abs(V.astype(np.float64) - med[None]).max(-1) > tol
    return let


def background(V, lettering, halo=4):
    """V: (L, h, w, 3) uint8 window of every language, lettering: (L, h, w) bool (that language's lettering).
    -> (bg uint8 (h, w, 3), stage int8 (h, w): 0 seen, 1 filled from row/column, 2 grown)."""
    L, h, w = V.shape[:3]
    free = np.stack([~dilate(lettering[i], halo) for i in range(L)])
    key = (V[..., 0].astype(np.int64) << 16) | (V[..., 1].astype(np.int64) << 8) | V[..., 2].astype(np.int64)
    cnt = np.zeros((L, h, w), np.int32)
    for i in range(L):
        for j in range(L):
            cnt[i] += free[i] & free[j] & (key[i] == key[j])
    cnt[~free] = 0
    m = cnt.max(0)
    arg = cnt.argmax(0)
    kmax = np.take_along_axis(key, arg[None], 0)[0]
    seen = m > 0
    bg = np.stack([(kmax >> 16) & 255, (kmax >> 8) & 255, kmax & 255], -1).astype(np.float64)
    stage = np.where(seen, 0, 3).astype(np.int8)
    # row / column bridging: a hidden run whose two ends agree within tol takes the linear blend
    tol = 10.0
    for axis in (1, 0):
        for k in range(h if axis == 1 else w):
            line_seen = seen[k] if axis == 1 else seen[:, k]
            if line_seen.all():
                continue
            idx = np.nonzero(line_seen)[0]
            if len(idx) < 2:
                continue
            for a_, b_ in zip(idx[:-1], idx[1:]):
                if b_ - a_ < 2:
                    continue
                ca = bg[k, a_] if axis == 1 else bg[a_, k]
                cb = bg[k, b_] if axis == 1 else bg[b_, k]
                if np.abs(ca - cb).max() > tol:
                    continue
                for t in range(a_ + 1, b_):
                    s = stage[k, t] if axis == 1 else stage[t, k]
                    if s != 3:
                        continue
                    f = (t - a_) / float(b_ - a_)
                    c = ca * (1 - f) + cb * f
                    if axis == 1:
                        bg[k, t] = c; stage[k, t] = 1
                    else:
                        bg[t, k] = c; stage[t, k] = 1
    # what is left: grown from the nearest known pixel, ring by ring
    known = stage != 3
    guard = 0
    while not known.all():
        guard += 1
        if guard > 400:
            raise PropsError('background: %d pixels could not be reached' % int((~known).sum()))
        acc = np.zeros_like(bg)
        n = np.zeros((h, w))
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            sh_k = np.zeros_like(known)
            sh_c = np.zeros_like(bg)
            ys0, ys1 = max(0, dy), h + min(0, dy)
            xs0, xs1 = max(0, dx), w + min(0, dx)
            sh_k[ys0:ys1, xs0:xs1] = known[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
            sh_c[ys0:ys1, xs0:xs1] = bg[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
            acc += sh_c * sh_k[..., None]
            n += sh_k
        new = (~known) & (n > 0)
        bg[new] = acc[new] / n[new][:, None]
        stage[new] = 2
        known = known | new
    return np.clip(np.rint(bg), 0, 255).astype(np.uint8), stage


def downscale(a, box_hd, size):
    """Area-average the Capcom window box_hd = (x0, y0, x1, y1) (floats allowed) of a (h, w[, 3]) array
    to size = (w, h) DS pixels. -> float64 array."""
    a = np.asarray(a)
    if a.ndim == 3:
        return np.stack([downscale(a[..., c], box_hd, size) for c in range(a.shape[2])], -1)
    im = Image.fromarray(a.astype(np.float32), mode='F')
    return np.asarray(im.resize(size, Image.BOX, box=tuple(float(v) for v in box_hd)), np.float64)


def fit_linear(D, ds, cal):
    """Per-channel robust linear map of D (scaled Capcom colours) onto ds (DS colours) on the bool mask cal.
    -> (fitted D, mean abs error)."""
    out = D.copy()
    for c in range(3):
        xs, ys = D[..., c][cal], ds[..., c][cal]
        a, b = np.polyfit(xs, ys, 1)
        for _ in range(4):
            r = np.abs(a * xs + b - ys)
            k = r < max(6.0, 2.5 * np.median(r))
            a, b = np.polyfit(xs[k], ys[k], 1)
        out[..., c] = a * D[..., c] + b
    return out, float(np.abs(out - ds).mean(-1)[cal].mean())


def register_check(D, ds, cal, max_err, margin=0.3, what='picture'):
    """Raise unless the scaled Capcom window D registers onto the DS colours ds on the pixels cal:
    mean error <= max_err and every one-pixel shift worse by at least margin. -> info dict."""
    fitted, base = fit_linear(D, ds, cal)
    shifts = {}
    for name, (dy, dx) in {'up': (-1, 0), 'down': (1, 0), 'left': (0, -1), 'right': (0, 1)}.items():
        sh = np.roll(np.roll(fitted, dy, 0), dx, 1)
        c2 = cal.copy()
        c2[:1] = c2[-1:] = False
        c2[:, :1] = c2[:, -1:] = False
        shifts[name] = float(np.abs(sh - ds).mean(-1)[c2].mean())
    if base > max_err or min(shifts.values()) < base + margin:
        raise PropsError("%s: Capcom's picture does not register onto the DS picture (mean error %.2f, "
                         "one-pixel shifts %s)" % (what, base, {k: round(v, 2) for k, v in shifts.items()}))
    return dict(err=round(base, 2), shifts={k: round(v, 2) for k, v in shifts.items()})


def vote(D, grid, targets, examples, k=K_NEAREST, lam=LAMBDA):
    """D: (h, w, 3) scaled Capcom colours over a window, grid: the DS index grid of the window,
    targets: bool (h, w) pixels that get a new index, examples: bool (h, w) pixels whose DS index is
    taken as an example of what Capcom's colour there looks like on the DS. -> new grid."""
    ry, rx = np.nonzero(examples)
    if len(ry) < k:
        raise PropsError('only %d example pixels for the colour vote' % len(ry))
    RF, RI = D[ry, rx], grid[ry, rx]
    new = grid.copy()
    for y, x in zip(*np.nonzero(targets)):
        cost = ((RF - D[y, x]) ** 2).sum(1) + lam * ((ry - y) ** 2 + (rx - x) ** 2)
        order = np.argsort(cost, kind='stable')[:k]
        votes = collections.Counter(RI[order].tolist())
        top = max(votes.values())
        first = [i for i in order if votes[int(RI[i])] == top][0]
        new[y, x] = int(RI[first])
    return new


def nearest_index(rgb, pal, allowed):
    """Nearest palette index (weighted RGB) among `allowed` for each colour of rgb (..., 3)."""
    P = np.array(pal, np.float64)[list(allowed)]
    w = np.array([3.0, 4.0, 2.0])
    d = (((rgb[..., None, :] - P) * w) ** 2).sum(-1)
    return np.array(list(allowed))[d.argmin(-1)]


def polygon_mask(shape, pts):
    """bool mask (h, w) of a polygon given in DS pixel coordinates (pixel centres inside)."""
    from PIL import ImageDraw
    h, w = shape
    im = Image.new('L', (w, h), 0)
    ImageDraw.Draw(im).polygon([tuple(p) for p in pts], fill=1)
    return np.asarray(im, bool)
