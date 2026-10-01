# -*- coding: utf-8 -*-
"""Offline registration of the plan picture (jpn/upcut_local.bin entry 8) into
the bag model's paper texture (jpn/modelitemlocal.bin entry 1, `bag_01`).

Fits one transform, a separate scale and offset per axis, texel = offset +
scale * picture pixel, by maximising the normalised cross-correlation between
the texture and the fan's picture after the picture is area-averaged into the
texel grid (bag_tex.resample). The result goes to tools/bag_tex_reg.json:

    {"reg": [sx, sy, ox, oy], "ncc": ..., "texels": N}

This is a development tool run once, with the fan's two files; the build only
reads the json. It needs scipy, which the built tool does not bundle, and is
never imported by the build.

    python tools/bag_tex_register.py FAN_modelitemlocal.bin FAN_upcut_local.bin [--write] [--residual OUT.png]
"""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import bag_tex
from bag_tex import BagTexError


def fan_btx(modelitemlocal):
    import lz11
    d = open(modelitemlocal, 'rb').read()
    o, s = struct.unpack_from('<II', d, bag_tex.ENTRY * 8)
    nxt = min([struct.unpack_from('<I', d, i * 8)[0] for i in range(struct.unpack_from('<I', d, 0)[0] // 8)
               if struct.unpack_from('<I', d, i * 8)[0] > o] + [len(d)])
    return lz11.decompress(d[o:nxt])


def fan_picture(upcut_local, entry=8):
    import cg_art
    from txtcut import table
    E = table(open(upcut_local, 'rb').read())
    return cg_art.decode(E[entry], E[entry + 1])[0]


def texture_rgb(btx):
    _raw, cols = bag_tex.palette(btx, bag_tex.PALETTE)
    pal = np.array(cols + [(255, 0, 255)] * (256 - len(cols)), np.float64)
    return pal[bag_tex.texture(btx, bag_tex.TEXTURE)]


def ncc(reg, tex, pic, margin=1):
    """NCC over the texels whose whole footprint lies inside the picture."""
    res, vy, vx = bag_tex.resample(pic, reg, tex.shape[0])
    ys, xs = np.nonzero(vy)[0], np.nonzero(vx)[0]
    if len(ys) < 20 or len(xs) < 20:
        return -1.0, 0
    ys, xs = ys[margin:-margin], xs[margin:-margin]
    a = res[np.ix_(ys, xs)].reshape(-1)
    b = tex[np.ix_(ys, xs)].reshape(-1)
    a, b = a - a.mean(), b - b.mean()
    den = np.sqrt((a * a).sum() * (b * b).sum())
    return (float((a * b).sum() / den) if den else -1.0), len(ys) * len(xs)


def fit(tex, pic, start=(0.73, 0.66, 4.0, 0.0)):
    from scipy.optimize import minimize
    best = None
    # coarse grid around the start, then a simplex polish
    for sx in np.arange(start[0] - 0.06, start[0] + 0.0601, 0.02):
        for sy in np.arange(start[1] - 0.06, start[1] + 0.0601, 0.02):
            for ox in np.arange(start[2] - 4, start[2] + 4.01, 2):
                for oy in np.arange(start[3] - 4, start[3] + 4.01, 2):
                    n, _ = ncc((sx, sy, ox, oy), tex, pic)
                    if best is None or n > best[0]:
                        best = (n, (sx, sy, ox, oy))
    r = minimize(lambda p: -ncc(p, tex, pic)[0], best[1], method='Nelder-Mead',
                 options=dict(xatol=1e-5, fatol=1e-7, maxiter=800))
    n, cnt = ncc(r.x, tex, pic)
    return [float(v) for v in r.x], n, cnt


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    btx = fan_btx(argv[0])
    pic = np.asarray(fan_picture(argv[1]), np.float64)
    tex = texture_rgb(btx)
    reg, n, cnt = fit(tex, pic)
    print('registration sx %.5f sy %.5f ox %.4f oy %.4f  NCC %.4f over %d texels' % (tuple(reg) + (n, cnt)))
    if '--residual' in argv:
        res, vy, vx = bag_tex.resample(pic, reg, tex.shape[0])
        d = np.abs(res - tex).sum(2)
        d[~vy, :] = 0
        d[:, ~vx] = 0
        Image.fromarray(np.clip(d, 0, 255).astype(np.uint8)).resize((tex.shape[1] * 3, tex.shape[0] * 3), Image.NEAREST)\
            .save(argv[argv.index('--residual') + 1])
    if '--write' in argv:
        with open(bag_tex.REG_JSON, 'w') as f:
            json.dump({'reg': [round(v, 5) for v in reg], 'ncc': round(n, 4), 'texels': cnt}, f, indent=1)
            f.write('\n')
        print('wrote', bag_tex.REG_JSON)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
