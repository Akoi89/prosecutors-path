# -*- coding: utf-8 -*-
"""Offline registration of the Collection's item textures onto the fan's evidence icons
(com/idcom.bin).

Fits one transform per icon, a separate scale and offset per axis, texel = offset +
scale * icon pixel, between the JAPANESE twin texture (the art the fan's icon was drawn from)
and the fan's icon, after the texture is area-averaged into the icon grid
(idcom_icons.resample). The English texture's frame is the same (tools/idcom_icons.py says
how the result is used).

Two fits exist:

  ncc         maximise the normalised cross-correlation of the grey pictures. Used for the business
              card and the victim's letter (281, 573, 575), whose art the fan left alone but for the
              lettering. It drifts when the fan redrew much of an icon.
  silhouette  maximise the overlap (intersection over union) of the object's silhouette, the icon's
              pixels that are not its background against the texture's pixels that are not its flat
              grey. It does not care what is written on the object, so it holds on icons whose label
              the fan redrew (bottles, tickets, covers).

An entry already in tools/idcom_icons_reg.json keeps its method (the json's "ncc" key means the
first, "iou" the second); a new entry gets the silhouette fit.

The result goes to tools/idcom_icons_reg.json:

    {"281": {"reg": [sx, sy, ox, oy], "ncc": ..., "size": 64, "texture": "..."},
     "485": {"reg": [...], "iou": ..., "size": 64, "texture": "..."}, ...}

This is a development tool run once; the build only reads the json. It needs scipy,
which the built tool does not bundle, and is never imported by the build.

    python tools/idcom_icons_register.py FAN_idcom.bin DUMPDIR [--write] [--check] [--only 485,487]

--only fits just those entries; --write then merges them into the stored json.

--check recomputes the fit and fails if it disagrees with the stored json by more than
0.25 texels (or by 0.01 in the score).
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import idcom_icons as I
from PIL import Image


def ncc(a, b):
    a = a - a.mean()
    b = b - b.mean()
    return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))


def resampled(g, reg, size):
    sx, sy, ox, oy = reg
    box = (ox + I.PAD, oy + I.PAD, ox + I.PAD + sx * size, oy + I.PAD + sy * size)
    p = np.pad(g, ((I.PAD, I.PAD), (I.PAD, I.PAD)), mode='edge')
    im = Image.fromarray(p.astype(np.float32), mode='F')
    return np.asarray(im.resize((size, size), Image.BOX, box=box)).astype(np.float64)


def fit_ncc(ds, tex, size):
    from scipy.optimize import minimize
    g = I.tone(tex).mean(2)
    s = I.TEX_SIZE / size

    def f(p):
        try:
            return -ncc(ds, resampled(g, p, size))
        except ValueError:
            return 0.0
    best = (0.0, None)
    for sx in np.arange(s * 0.97, s * 1.04, s * 0.005):
        for sy in np.arange(s * 0.97, s * 1.04, s * 0.005):
            for ox in np.arange(-8, 14.1, 1.0):
                for oy in np.arange(-8, 14.1, 1.0):
                    v = -f([sx, sy, ox, oy])
                    if v > best[0]:
                        best = (v, [sx, sy, ox, oy])
    res = minimize(f, best[1], method='Powell', options=dict(xtol=1e-4, ftol=1e-10))
    return [float(x) for x in res.x], float(-res.fun)


def icon_mask(fan, e):
    """The fan icon's object: pixels whose colour is not the corner colour."""
    import choice_strips as cs
    from nitro import nclr
    spec = I.ICONS[e]
    ent, _ = I.entry_decoded(fan, e)
    g = np.array(cs.grid(ent), np.uint8)
    pal_e, _ = I.entry_decoded(fan, spec['pal'])
    pal = np.array(nclr(pal_e), int)
    rgb = pal[g]
    return (np.abs(rgb - pal[g[0, 0]]).sum(2) > 6).astype(np.float64)


def tex_mask(tex):
    return (np.abs(np.asarray(tex, np.float64) - float(I.TEX_BG)).sum(2) > 24).astype(np.float64)


def iou(fm, tm, reg, size):
    try:
        r = resampled(tm, reg, size)
    except ValueError:
        return 0.0
    return float(np.minimum(fm, r).sum() / max(np.maximum(fm, r).sum(), 1e-9))


def fit_silhouette(fm, tm, size):
    from scipy.optimize import minimize
    s0 = I.TEX_SIZE / size
    best = (0.0, None)
    for sx in np.arange(s0 * 0.95, s0 * 1.10, s0 * 0.02):
        for sy in np.arange(s0 * 0.95, s0 * 1.10, s0 * 0.02):
            for ox in np.arange(-14, 14.1, 1.0):
                for oy in np.arange(-14, 14.1, 1.0):
                    v = iou(fm, tm, [sx, sy, ox, oy], size)
                    if v > best[0]:
                        best = (v, [sx, sy, ox, oy])
    res = minimize(lambda p: -iou(fm, tm, list(p), size), best[1], method='Powell',
                   options=dict(xtol=1e-3, ftol=1e-9))
    return [float(x) for x in res.x], float(-res.fun)


def _fit_entry(args):
    fan_path, dump, e, method = args
    spec = I.ICONS[e]
    fan = open(fan_path, 'rb').read()
    tex = I.load_texture(dump, spec['jp'])
    if method == 'ncc':
        ds = I.fan_render(fan, e).astype(np.float64).mean(2)
        reg, c = fit_ncc(ds, tex, spec['size'])
        return e, dict(reg=[round(x, 4) for x in reg], ncc=round(c, 4), size=spec['size'], texture=spec['jp'])
    reg, c = fit_silhouette(icon_mask(fan, e), tex_mask(tex), spec['size'])
    return e, dict(reg=[round(x, 4) for x in reg], iou=round(c, 4), size=spec['size'], texture=spec['jp'])


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    dump = argv[2]
    out = {}
    only = None
    if '--only' in argv:
        only = {int(x) for x in argv[argv.index('--only') + 1].split(',')}
    try:
        stored = I.load_reg()
    except (OSError, ValueError):
        stored = {}
    todo = []
    for e in I.ICONS:
        if only is not None and e not in only:
            continue
        method = 'ncc' if 'ncc' in stored.get(str(e), {}) else 'silhouette'
        todo.append((argv[1], dump, e, method))
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor() as pool:
        for e, r in pool.map(_fit_entry, todo):
            out[str(e)] = r
            print(e, r['texture'], r, flush=True)
    if '--check' in argv:
        bad = []
        for k, v in out.items():
            key = 'ncc' if 'ncc' in v else 'iou'
            d = np.abs(np.array(v['reg']) - np.array(stored[k]['reg']))
            if d.max() > 0.25 or abs(v[key] - stored[k].get(key, -9)) > 0.01:
                bad.append(k)
        if bad:
            raise SystemExit('registration differs from the stored one for icon(s) %s' % ', '.join(bad))
        print('stored registration reproduced')
    if '--write' in argv:
        merged = dict(stored) if only is not None else {}
        merged.update(out)
        with open(I.REG_JSON, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(dict(sorted(merged.items(), key=lambda kv: int(kv[0]))), f, indent=1)
            f.write('\n')
        print('wrote', I.REG_JSON)


if __name__ == '__main__':
    main(sys.argv)
